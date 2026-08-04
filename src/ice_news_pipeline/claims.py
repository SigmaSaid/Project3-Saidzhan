from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from ice_news_pipeline.models import DocumentRecord, EventCandidate, PersonCandidate
from ice_news_pipeline.normalize import normalize_text

_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s+[A-Z“\"'])|$)", re.DOTALL)
_NUMBER = r"\d[\d,]*"
_QUALIFIER = r"more than|over|at least|nearly|approximately|about"
_COUNT_UNIT = (
    r"people|persons|individuals|aliens|nationals|suspects|defendants|offenders|"
    r"members|workers|fugitives"
)
_DESCRIPTOR = r"[^\W\d_][\w’'-]*"
_COUNTED_GROUP = rf"(?:{_DESCRIPTOR}\s+){{0,3}}(?:{_COUNT_UNIT})"

ACTION_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("sentence", "sentenced", r"\bsentenc(?:ed|ing)\b"),
    (
        "conviction",
        "convicted",
        r"\b(?:convicted|pleaded guilty|pleading guilty|pleads guilty|found guilty)\b",
    ),
    ("charge", "charged", r"\b(?:charged|indicted|indictment)\b"),
    ("arrest", "agency_claim", r"\b(?:arrested|arrests|apprehended|apprehends)\b"),
    ("removal", "agency_claim", r"\b(?:removed|removes|deported|deports|repatriated)\b"),
    ("detention", "agency_claim", r"\b(?:detained|detains|taken into custody)\b"),
    ("transfer", "agency_claim", r"\b(?:transferred|transfers)\b"),
)

_RANGE_AFTER_ACTION_RE = re.compile(
    rf"^\s+between\s+(?P<low>{_NUMBER})\s+and\s+(?P<high>{_NUMBER})\b"
    rf"(?=\s+{_COUNTED_GROUP}\b)",
    re.IGNORECASE,
)
_COUNT_AFTER_ACTION_RE = re.compile(
    rf"^\s+(?:(?P<qual>{_QUALIFIER})\s+)?(?P<count>{_NUMBER})\b"
    rf"(?=\s+{_COUNTED_GROUP}\b)",
    re.IGNORECASE,
)
_RANGE_BEFORE_ACTION_RE = re.compile(
    rf"\bbetween\s+(?P<low>{_NUMBER})\s+and\s+(?P<high>{_NUMBER})\s+"
    rf"{_COUNTED_GROUP}\b",
    re.IGNORECASE,
)
_COUNT_BEFORE_ACTION_RE = re.compile(
    rf"\b(?:(?P<qual>{_QUALIFIER})\s+)?(?P<count>{_NUMBER})\s+"
    rf"{_COUNTED_GROUP}\b",
    re.IGNORECASE,
)
_CLAUSE_BREAK_RE = re.compile(r"[;:]|\b(?:and|but|then|whereas|while)\b", re.IGNORECASE)

_NAME_TOKEN = r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ’'-]+"
_NAME_CONNECTOR = r"(?:de|del|de la|la|van|von|da|dos)"
_PERSON_RE = re.compile(
    rf"\b(?P<name>{_NAME_TOKEN}(?:\s+(?:{_NAME_TOKEN}|{_NAME_CONNECTOR})){{1,4}}),\s*"
    rf"(?P<age>\d{{1,3}})(?P<tail>,?[^.;\n]{{0,140}})",
)
_ORIGIN_RE = re.compile(
    r"\b(?:citizen|national|native)\s+of\s+(?P<place>[A-Z][^,.;\n]{1,60})",
    re.IGNORECASE,
)
_RESIDENCE_RE = re.compile(r"^\s*,?\s*of\s+(?P<place>[^,.;\n]{2,80})", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _Count:
    minimum: int | None
    maximum: int | None
    qualifier: str


def _integer(raw: str) -> int:
    return int(raw.replace(",", ""))


def _normalize_count(raw: str, qualifier: str | None) -> _Count:
    value = _integer(raw)
    normalized_qualifier = (qualifier or "exact").casefold().replace(" ", "_")
    if normalized_qualifier in {"more_than", "over", "at_least"}:
        return _Count(value, None, normalized_qualifier)
    if normalized_qualifier in {"nearly", "approximately", "about"}:
        return _Count(None, value, normalized_qualifier)
    return _Count(value, value, "exact")


def _range_count(match: re.Match[str]) -> _Count:
    low = _integer(match.group("low"))
    high = _integer(match.group("high"))
    return _Count(min(low, high), max(low, high), "range")


def _count_after_action(sentence: str, action_end: int) -> _Count | None:
    suffix = sentence[action_end:]
    if range_match := _RANGE_AFTER_ACTION_RE.match(suffix):
        return _range_count(range_match)
    if count_match := _COUNT_AFTER_ACTION_RE.match(suffix):
        return _normalize_count(count_match.group("count"), count_match.group("qual"))
    return None


def _count_before_action(
    sentence: str,
    action_start: int,
    previous_action_end: int,
) -> _Count | None:
    prefix = sentence[previous_action_end:action_start]
    matches: list[tuple[int, int, re.Match[str], bool]] = []
    matches.extend(
        (match.end(), 1, match, True) for match in _RANGE_BEFORE_ACTION_RE.finditer(prefix)
    )
    matches.extend(
        (match.end(), 0, match, False) for match in _COUNT_BEFORE_ACTION_RE.finditer(prefix)
    )
    if not matches:
        return None

    _, _, nearest, is_range = max(matches, key=lambda item: (item[0], item[1]))
    bridge = prefix[nearest.end() :]
    if len(bridge) > 60 or _CLAUSE_BREAK_RE.search(bridge):
        return None
    if is_range:
        return _range_count(nearest)
    return _normalize_count(nearest.group("count"), nearest.group("qual"))


def _count_for_action(
    sentence: str,
    action_match: re.Match[str],
    previous_action_end: int,
) -> _Count | None:
    if count := _count_after_action(sentence, action_match.end()):
        return count
    return _count_before_action(sentence, action_match.start(), previous_action_end)


def _action_mentions(sentence: str) -> list[tuple[str, str, re.Match[str]]]:
    mentions = [
        (action_type, legal_stage, match)
        for action_type, legal_stage, pattern in ACTION_PATTERNS
        for match in re.finditer(pattern, sentence, re.IGNORECASE)
    ]
    mentions.sort(key=lambda item: (item[2].start(), item[2].end(), item[0]))
    return mentions


def _paragraph_offsets(body: str, paragraphs: list[str]) -> Iterator[tuple[str, int, int]]:
    cursor = 0
    for paragraph in paragraphs:
        start = body.find(paragraph, cursor)
        if start < 0:
            start = body.find(paragraph)
        if start < 0:
            continue
        end = start + len(paragraph)
        yield paragraph, start, end
        cursor = end


def extract_event_candidates(document: DocumentRecord) -> list[EventCandidate]:
    body = document.body_text
    if not body:
        return []
    candidates: list[EventCandidate] = []
    seen: set[tuple[str, int, int]] = set()
    for paragraph, paragraph_start, _ in _paragraph_offsets(body, document.paragraphs):
        for sentence_match in _SENTENCE_RE.finditer(paragraph):
            raw_sentence = sentence_match.group()
            leading_space = len(raw_sentence) - len(raw_sentence.lstrip())
            stripped_sentence = raw_sentence.strip()
            sentence = normalize_text(stripped_sentence)
            if not sentence:
                continue
            relative_start = sentence_match.start() + leading_space
            absolute_start = paragraph_start + relative_start
            absolute_end = absolute_start + len(stripped_sentence)
            mentions = _action_mentions(sentence)
            for index, (action_type, legal_stage, action_match) in enumerate(mentions):
                action_start = absolute_start + action_match.start()
                action_end = absolute_start + action_match.end()
                identity = (action_type, action_start, action_end)
                if identity in seen:
                    continue
                seen.add(identity)
                previous_action_end = mentions[index - 1][2].end() if index else 0
                count = _count_for_action(sentence, action_match, previous_action_end)
                confidence = 0.86 if count else 0.72
                candidates.append(
                    EventCandidate(
                        event_id=f"{document.document_id}:event:{len(candidates):04d}",
                        document_id=document.document_id,
                        action_type=action_type,
                        legal_stage=legal_stage,
                        count_min=count.minimum if count else None,
                        count_max=count.maximum if count else None,
                        count_qualifier=count.qualifier if count else None,
                        evidence_text=sentence,
                        evidence_start=absolute_start,
                        evidence_end=absolute_end,
                        extraction_method="rule:action_mention_v2",
                        confidence=confidence,
                    )
                )
    return candidates


def extract_person_candidates(document: DocumentRecord) -> list[PersonCandidate]:
    body = document.body_text
    if not body:
        return []
    candidates: list[PersonCandidate] = []
    seen: set[tuple[str, int, int]] = set()
    for paragraph, paragraph_start, paragraph_end in _paragraph_offsets(body, document.paragraphs):
        for match in _PERSON_RE.finditer(paragraph):
            age = int(match.group("age"))
            if not 14 <= age <= 110:
                continue
            name = normalize_text(match.group("name"))
            if not name:
                continue
            identity = (name.casefold(), age, paragraph_start)
            if identity in seen:
                continue
            seen.add(identity)
            tail = match.group("tail")
            origin_match = _ORIGIN_RE.search(tail)
            residence_match = _RESIDENCE_RE.search(tail)
            origin = normalize_text(origin_match.group("place")) if origin_match else None
            residence = normalize_text(residence_match.group("place")) if residence_match else None
            candidates.append(
                PersonCandidate(
                    mention_id=f"{document.document_id}:person:{len(candidates):04d}",
                    document_id=document.document_id,
                    name_raw=name,
                    age=age,
                    residence_raw=residence,
                    origin_country_raw=origin,
                    evidence_text=paragraph,
                    evidence_start=paragraph_start,
                    evidence_end=paragraph_end,
                    extraction_method="rule:explicit_name_age_v1",
                    confidence=0.82 if (origin or residence) else 0.76,
                )
            )
    return candidates
