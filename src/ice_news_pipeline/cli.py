from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from ice_news_pipeline.constants import DATASET_ID, DEFAULT_REVISION, DEFAULT_SPLIT
from ice_news_pipeline.evaluation import evaluate_audit


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ice-news-pipeline",
        description="Extract and validate ICE press releases from the Big Local News dataset.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run extraction, validation, analysis, and reporting")
    run.add_argument("--dataset-id", default=DATASET_ID)
    run.add_argument("--revision", default=DEFAULT_REVISION)
    run.add_argument("--split", default=DEFAULT_SPLIT)
    run.add_argument("--limit", type=int)
    run.add_argument("--workers", type=int, default=1)
    run.add_argument("--cache-dir", type=Path, default=Path(".cache/huggingface"))
    run.add_argument("--output-dir", type=Path, default=Path("outputs/full"))
    run.add_argument("--report-dir", type=Path, default=Path("reports/generated"))
    run.add_argument("--raw-jsonl", type=Path)
    run.add_argument("--reference-jsonl", type=Path)
    run.add_argument("--skip-candidates", action="store_true")
    run.add_argument("--audit-size", type=int, default=30)
    run.add_argument("--audit-seed", type=int, default=20260729)
    run.add_argument("--no-figures", action="store_true")
    run.add_argument("--fail-on-warning", action="store_true")
    evaluate = subparsers.add_parser(
        "evaluate-audit",
        help="calculate precision/recall after the audit CSV has independent labels",
    )
    evaluate.add_argument("audit_csv", type=Path)
    evaluate.add_argument("--output-json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "evaluate-audit":
        try:
            result = evaluate_audit(args.audit_csv)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(rendered + "\n", encoding="utf-8")
        return 0
    if args.command != "run":
        raise AssertionError("unreachable command")
    from ice_news_pipeline.pipeline import exit_code, run_pipeline
    from ice_news_pipeline.source import load_huggingface_inputs, load_local_inputs

    if bool(args.raw_jsonl) != bool(args.reference_jsonl):
        raise SystemExit("--raw-jsonl and --reference-jsonl must be supplied together")
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")

    if args.raw_jsonl:
        print("Loading local JSONL inputs...")
        loaded = load_local_inputs(
            args.raw_jsonl,
            args.reference_jsonl,
            limit=args.limit,
        )
    else:
        print(
            f"Loading {args.dataset_id}@{args.revision[:12]} "
            f"(split={args.split}, limit={args.limit or 'all'})..."
        )
        loaded = load_huggingface_inputs(
            dataset_id=args.dataset_id,
            revision=args.revision,
            split=args.split,
            limit=args.limit,
            cache_dir=args.cache_dir,
        )

    print("Extracting DOM-scoped documents and running validation gates...")
    run = run_pipeline(
        loaded,
        output_dir=args.output_dir,
        report_dir=args.report_dir,
        workers=args.workers,
        extract_candidates=not args.skip_candidates,
        audit_size=args.audit_size,
        audit_seed=args.audit_seed,
        figures=not args.no_figures,
    )
    accounting = run.validation.row_accounting
    print(
        f"Result: {run.validation.status.value.upper()} | "
        f"{accounting['accepted']}/{accounting['input']} accepted | "
        f"{accounting['quarantined']} quarantined"
    )
    print(f"Validation report: {run.report_dir / 'VALIDATION_REPORT.md'}")
    print(f"Findings: {run.report_dir / 'FINDINGS.md'}")
    return exit_code(run, fail_on_warning=args.fail_on_warning)
