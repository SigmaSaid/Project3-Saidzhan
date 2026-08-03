# Project3: ICE HTML Extraction and Validation

[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-8C1515.svg)](LICENSE)

This is a data extraction pipeline for
[Big Local News' ICE press-release dataset](https://huggingface.co/datasets/stanforddams/biglocal).
The raw data is full ICE.gov HTML, so the main job is to extract the actual press-release content
instead of accidentally analyzing the page header, footer, navigation, or social links.

The pipeline builds a document table, keeps source/provenance fields for every value, compares
extracted values against the structured Big Local News companion data, and writes reports that show
what passed, what needs review, and what should not be overclaimed.

## Design: a five-stage pipeline, not `get_text()`

The Hugging Face dataset is treated as two linked sources:

- `html`: raw ICE.gov pages;
- `default` (or an equivalent structured config): the companion reference rows used for comparison.

| Stage | What it does | Why it matters |
|---|---|---|
| 1. Source loading | Loads the dataset at a pinned revision (`ice_news_pipeline.constants.DEFAULT_REVISION`) and joins rows by normalized URL | Makes the run reproducible and avoids assuming row order |
| 2. HTML parsing | Uses BeautifulSoup/lxml to parse the page DOM, not whole-page text | Keeps navigation, footer, and social links out of the dataset |
| 3. Field extraction | Extracts title, dates, topics, dateline, body text, tables, images, canonical URL, and a source SHA-256 | Produces a document dataset with provenance and a confidence score for every field |
| 4. Quarantine | Flags pages that look like release URLs but fail structural checks (missing title/body/date, wrong URL path, canonical mismatch, unexpected domain, non-`news_release` entity type) | Prevents bad rows from silently entering the analysis — nothing is dropped, only quarantined |
| 5. Validation and reporting | Runs automated gates against the structured companion data and writes CSV/JSON/Markdown outputs | Shows what is ready to use, what needs review, and what cannot be claimed yet |

## Validation gates

Every run evaluates a fixed set of automated gates (see `src/ice_news_pipeline/validate.py`):

| Gate | Question it answers | Threshold |
|---|---|---|
| `source_schema` | Do raw/reference rows have the required fields? | 0 errors |
| `url_uniqueness` | Are URLs unique within each config? | 100% unique |
| `one_to_one_join` | Do the HTML and reference configs describe the same document set? | identical URL sets |
| `row_accounting` | Does every input row end up accepted or quarantined — none silently dropped? | input = accepted + quarantined |
| `release_signature` | What share of rows pass structural extraction? | ≥ 99% accepted |
| `primary_body_selector` | What share of accepted body text came from the primary `.nr-body` selector rather than a fallback? | ≥ 99% |
| `title_reference_agreement`, `topics_reference_agreement`, `published_date_reference_agreement`, `dateline_city_reference_agreement` | Do extracted values exactly match the structured reference where both are present? | ≥ 99% exact match |
| `body_similarity` | How closely does extracted body text match the reference text (token F1)? | median ≥ 0.99, p05 ≥ 0.95 |
| `body_outlier_review` | Are there any low-similarity body pairs? | flagged for human review (warn, not fail) |
| `evidence_offsets` | Do event/person candidates point back to an exact span in the body text? | 0 invalid offsets |
| `silver_reference_validity` | Are the reference's own populated values actually valid (e.g. real dates)? | reported, not silently assumed valid |
| `candidate_layer_publication_readiness` | Are event/person candidates independently verified? | always **warn** until a human reviews the audit sample |

A run's overall status is `pass`, `pass with warnings`, or `fail` — `fail` withholds the descriptive
findings report entirely rather than publishing numbers built on a broken document layer.

This design deliberately separates four different quality questions:

1. **Completeness** — was a value produced at all?
2. **Validity** — does the value satisfy its type/domain contract (e.g. is `date_last_updated`
   actually a date, not just non-empty)?
3. **Silver agreement** — does it match the structured companion record?
4. **Accuracy** — does an independently labeled sample confirm event/person extraction?

Only the first three can be automated from this dataset alone. That's why the document layer can
pass its automated gates while the event/person candidate layer is still marked **candidate-only**
until a human completes `reports/generated/*_candidate_audit.csv`.

## Results

Fill in this table after your own `make reproduce` run against
[`stanforddams/biglocal`](https://huggingface.co/datasets/stanforddams/biglocal) — numbers will
depend on the pinned revision and split you run against.

| Result | Observed |
|---|---:|
| Raw HTML rows | _run pipeline to fill in_ |
| Accepted press releases | |
| Quarantined non-release pages | |
| URL join between configs | |
| Primary `.nr-body` selector coverage on accepted releases | |
| Title exact agreement among paired values | |
| Topic exact agreement among paired values | |
| Publication-date exact agreement among paired values | |
| Median body token F1 | |
| Body pairs below 0.90 F1, routed to review | |
| Multi-topic releases | |
| Event candidates with exact evidence spans | |
| Explicit name-and-age candidates with exact evidence spans | |
| Invalid evidence offsets | |

Read the generated [validation report](reports/generated/VALIDATION_REPORT.md) and
[descriptive findings](reports/generated/FINDINGS.md) after running the pipeline — `FINDINGS.md`
will only contain descriptive numbers if the overall status is not `fail`.

## Why more than the starter snippet

`soup.get_text(" ", strip=True)` is useful for orientation, but each raw record is a complete
ICE.gov page. Whole-page text would include the government banner, navigation, footer, media
contacts, and social links. This pipeline extracts from `.nr-body` first and only falls back (with
a recorded quality flag) when that expected section is missing.

It also handles source quirks that would otherwise distort analysis:

- missing values are tracked explicitly via `field_provenance`/`quality_flags`, not silently coerced;
- topic labels are multi-label, but individual labels (e.g. `Firearms, Ammunition and Explosives`)
  contain commas themselves, so naive comma-splitting is wrong;
- a press-release dateline is not necessarily an enforcement-event location;
- international datelines exist (e.g. `Lima, Peru`) — the geography model is not U.S.-only;
- publication date and last-modified date are different concepts and are validated separately;
- the structured reference config is useful as a silver comparison, not ground truth, and may itself
  contain invalid values (see `silver_reference_validity`).

## Extraction order

| Field | Primary source | Safe fallback |
|---|---|---|
| Document type | `dataLayer.entityBundle` | none; unexpected type is quarantined |
| Canonical URL | `link[rel=canonical]` | requested URL retained separately as `input_url` |
| Title | `.nr-title h1` | `og:title`, then `h1`, then `<title>` (suffix stripped) |
| Published / modified | `article:published_time` / `article:modified_time` meta tags | `.nr-meta` text for publication only |
| Topics | `dataLayer.entityTaxonomy.news_release_topics` | unsplit `.nr-meta` text, flagged `topics_fallback_unsplit` |
| Dateline | `.nr-meta` spans (city/region/country) plus the first body paragraph | nullable |
| Body | `.nr-body` | `article`, flagged `body_fallback` |
| Images | `.colorbox-image-grid` anchors and `.nr-body` images, resolved to absolute URLs | nullable |
| Tables | `.nr-body table` | preserved as `{table_index, headers, rows}` |

The pipeline does not execute page JavaScript. It only parses the JSON-like `dataLayer` metadata
already embedded in the page `<script>` tags.

## Quick start

Python 3.10–3.13.

```bash
git clone https://github.com/SigmaSaid/Project3-Saidzhan.git
cd Project3-Saidzhan
make setup
make check
make reproduce
```

`make reproduce` downloads the dataset at the pinned revision, processes every row, and rebuilds the
reports in `outputs/full/` and `reports/generated/`.

For a faster smoke run:

```bash
make sample
```

Direct CLI usage:

```bash
.venv/bin/ice-news-pipeline run \
  --revision 4e9cd487de2b4781bc40b39a92295b0ee6827034 \
  --workers 4 \
  --output-dir outputs/full \
  --report-dir reports/generated
```

Offline JSONL input is also supported:

```bash
.venv/bin/ice-news-pipeline run \
  --raw-jsonl path/to/raw.jsonl \
  --reference-jsonl path/to/reference.jsonl
```

## Outputs

| Artifact | Purpose |
|---|---|
| `outputs/full/documents.jsonl` / `documents.parquet` | Full structured document table, one row per press release |
| `outputs/full/validation.json` | Machine-readable gates, metrics, and review issues |
| `reports/generated/VALIDATION_REPORT.md` | Human-readable release decision (`PASS`, `PASS WITH WARNINGS`, or `NOT READY`) |
| `reports/generated/FINDINGS.md` | Descriptive patterns with denominator and scope caveats — withheld if validation fails |
| `reports/generated/audit_sample.csv` | Fixed purposive document-level QA queue |
| `reports/generated/event_candidate_audit.csv` | Row-level event candidate adjudication sheet |
| `reports/generated/person_candidate_audit.csv` | Row-level person candidate adjudication sheet |
| `reports/generated/figures/` | Monthly volume, top topics, and top dateline region charts (unless `--no-figures`) |

After a real run, check `reports/generated/VALIDATION_REPORT.md` for the overall decision before
treating the output as publishable.

## Scoring an audit

Once a human reviewer has labeled `audit_sample.csv` (or the event/person candidate audit CSVs):

```bash
.venv/bin/ice-news-pipeline evaluate-audit \
  reports/generated/audit_sample.csv \
  --output-json reports/generated/gold_evaluation.json
```

This reports sample-level precision, recall, and F1 for the labeled candidates. It does **not**
report a corpus-wide confidence interval, since the audit queue is a purposive sample, not a
probability sample.

## Development

```bash
make lint       # ruff check + format check
make typecheck  # mypy
make test       # pytest with coverage
make check      # lint + typecheck + test
```

## Responsible interpretation

This corpus contains ICE-authored public statements, not a random or complete sample of ICE
activity. A rise in press-release volume is not evidence of a rise in enforcement. A dateline may
identify the publishing office rather than the event. Charges and allegations are not convictions.
Country of origin, citizenship, and residence should be reported as separate fields and never
inferred from a name.

The descriptive findings report describes what the *dataset contains*, not population-level,
causal, or independently verified factual claims about the people ICE discusses in these releases.

## Project layout

```
src/ice_news_pipeline/
  extract.py     # HTML -> DocumentRecord
  utils.py       # low-level DOM/text parsing helpers
  normalize.py   # text/date/URL normalization
  validate.py    # automated validation gates
  analyze.py     # descriptive analysis tables
  report.py      # Markdown report generation
  claims.py      # event/person candidate extraction
  audit.py       # audit sample construction
  evaluation.py  # precision/recall scoring against labeled audits
  source.py      # loading raw/reference data (Hugging Face or local JSONL)
  pipeline.py    # orchestrates the full run
  cli.py         # command-line entry point
tests/           # pytest suite with offline HTML fixtures (release, international dateline, non-release quarantine)
```

## Source and license

- Dataset: [stanforddams/biglocal](https://huggingface.co/datasets/stanforddams/biglocal)
- Data creator: [Big Local News at Stanford University](https://biglocalnews.org/)
- Original pages: [ICE Newsroom](https://www.ice.gov/newsroom)
- Code is MIT-licensed (see `LICENSE`); source-page use remains subject to applicable terms.
