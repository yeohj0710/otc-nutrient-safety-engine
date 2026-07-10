from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from .dedup import dedup_retrieved_records
from .curation import generate_screening_outputs, write_rule_seed
from .embase_adapter import EmbaseAdapter
from .pubmed_adapter import PubMedAdapter
from .ris_parser import parse_ris_file
from .schemas import RETRIEVED_RECORD_COLUMNS
from .storage import (
    SYSTEMATIC_SEARCH_DIR,
    ensure_layout,
    upsert_csv_rows,
)


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        ensure_layout(Path(args.output_root))
        print(f"Initialized systematic search workspace: {args.output_root}")
        return

    if args.command == "pubmed":
        result = PubMedAdapter(output_root=Path(args.output_root)).run(
            target_id=args.target,
            query=args.query,
            filters=args.filters,
            max_records=args.max_records,
            sort=args.sort,
        )
        print(
            "PubMed search completed: "
            f"run={result.search_run.search_run_id}, "
            f"hit_count={result.search_run.hit_count}, "
            f"retrieved_records={len(result.records)}"
        )
        return

    if args.command == "embase":
        result = EmbaseAdapter(
            output_root=Path(args.output_root),
            profile_dir=Path(args.profile_dir) if args.profile_dir else None,
            headed=not args.headless,
        ).run(
            target_id=args.target,
            query=args.query,
            filters=args.filters,
            max_records=args.max_records,
            login_wait_seconds=args.login_wait_seconds,
        )
        print(
            "Embase search completed: "
            f"run={result.search_run.search_run_id}, "
            f"hit_count={result.search_run.hit_count}, "
            f"retrieved_records={len(result.records)}, "
            f"ris={result.ris_path}"
        )
        return

    if args.command == "parse-ris":
        ensure_layout(Path(args.output_root))
        records = parse_ris_file(
            Path(args.path),
            source=args.source,
            target_id=args.target,
            search_run_id=args.search_run_id,
        )
        upsert_csv_rows(
            Path(args.output_root) / "retrieved_records.csv",
            [record.csv_row(RETRIEVED_RECORD_COLUMNS) for record in records],
            RETRIEVED_RECORD_COLUMNS,
            key_column="record_id",
        )
        print(f"RIS parsed: records={len(records)}")
        return

    if args.command == "dedup":
        result = dedup_retrieved_records(Path(args.output_root))
        print(
            "Dedup completed: "
            f"total_records={result.total_records}, "
            f"duplicate_records={result.duplicate_records}"
        )
        return

    if args.command == "classify":
        generate_screening_outputs(
            Path(args.output_root),
            profile=args.profile,
            date_tag=args.date_tag,
        )
        print(f"Classification outputs written for profile={args.profile}")
        return

    if args.command == "seed-rules":
        path = write_rule_seed(
            Path(args.output_root),
            profile=args.profile,
            date_tag=args.date_tag,
        )
        print(f"Rule seed written: {path}")
        return

    parser.print_help()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.search_pipeline.cli",
        description="Systematic literature search pipeline for nutrition safety evidence.",
    )
    parser.add_argument(
        "--output-root",
        default=str(SYSTEMATIC_SEARCH_DIR),
        help="Directory containing search CSV outputs and raw responses.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create the systematic search output layout.")

    pubmed = subparsers.add_parser("pubmed", help="Run PubMed E-utilities search.")
    add_search_args(pubmed)

    embase = subparsers.add_parser("embase", help="Run Embase browser RIS export.")
    add_search_args(embase)
    embase.add_argument(
        "--profile-dir",
        default="",
        help="Playwright persistent browser profile directory for Embase login session.",
    )
    embase.add_argument(
        "--headless",
        action="store_true",
        help="Run browser without a visible window. Use only after login is already stored.",
    )
    embase.add_argument(
        "--login-wait-seconds",
        type=int,
        default=0,
        help="Wait this many seconds for interactive login before failing.",
    )

    parse_ris = subparsers.add_parser("parse-ris", help="Parse an existing RIS export.")
    parse_ris.add_argument("--path", required=True, help="Path to RIS file.")
    parse_ris.add_argument("--target", required=True, help="Target ID.")
    parse_ris.add_argument("--source", default="embase", help="Source label.")
    parse_ris.add_argument(
        "--search-run-id",
        default="manual_ris_import",
        help="Search run ID to attach to parsed records.",
    )

    subparsers.add_parser("dedup", help="Mark duplicates in retrieved_records.csv.")

    classify = subparsers.add_parser("classify", help="Create screening, extraction, and priority CSVs.")
    add_curation_args(classify)

    seed_rules = subparsers.add_parser("seed-rules", help="Create a safety rule seed CSV.")
    add_curation_args(seed_rules)
    return parser


def add_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", required=True, help="Target ID, e.g. anticoag.")
    parser.add_argument("--query", required=True, help="Database search query.")
    parser.add_argument("--filters", default="", help="Human-readable filter description.")
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help=(
            "Legacy capped debug mode. Omit for full retrieval; full queries over "
            "10,000 PubMed UIDs fail and require segmentation or EDirect."
        ),
    )
    parser.add_argument("--sort", default="", help="Optional source sort, e.g. relevance for PubMed.")


def add_curation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--profile",
        required=True,
        choices=["anticoag_renal", "otc_nutrients"],
        help="Curation profile used for target-specific keyword classification.",
    )
    parser.add_argument(
        "--date-tag",
        default="",
        help="Review date or YYYYMMDD suffix for generated files. Defaults to today.",
    )


if __name__ == "__main__":
    main()
