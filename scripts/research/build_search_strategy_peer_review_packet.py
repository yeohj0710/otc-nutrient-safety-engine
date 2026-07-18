from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


CRITERIA = (
    (1, "연구질문과 검색개념의 일치"),
    (2, "주제명(MeSH)과 자유어 누락"),
    (3, "철자·구문·괄호·필드 태그"),
    (4, "Boolean 연산자와 근접연산자 사용"),
    (5, "지나치게 넓거나 좁은 검색 블록"),
    (6, "알려진 핵심 문헌 회수"),
    (7, "불필요한 제한과 편향 위험"),
)

FIELDS = (
    "review_id", "strategy_id", "query_sha256", "reviewer_id",
    "review_date_utc", "question_number", "criterion", "rating",
    "comment", "required_change", "resolution", "status",
)


def build(query_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for query in sorted(query_dir.glob("K*.txt")):
        strategy_id = query.stem
        digest = hashlib.sha256(query.read_bytes()).hexdigest()
        for number, criterion in CRITERIA:
            rows.append({
                "review_id": f"PRESS-{strategy_id}-{number:02d}",
                "strategy_id": strategy_id,
                "query_sha256": digest,
                "reviewer_id": "",
                "review_date_utc": "",
                "question_number": str(number),
                "criterion": criterion,
                "rating": "",
                "comment": "",
                "required_change": "",
                "resolution": "",
                "status": "not_reviewed",
            })
    return rows


def write(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = build(args.query_dir.resolve())
    if len(rows) != 35:
        raise SystemExit(f"expected 35 review rows for five strategies; got {len(rows)}")
    write(rows, args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
