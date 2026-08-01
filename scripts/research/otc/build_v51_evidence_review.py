from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

try:
    from scripts.research.otc import audit_v51_boundaries as boundary_audit
except ModuleNotFoundError:  # Direct `python path/to/script.py` execution.
    import audit_v51_boundaries as boundary_audit


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "research_v51"
BASELINE_COMMIT = boundary_audit.EXPECTED_BASELINE_COMMIT

UNIT_FIELDS = [
    "evidence_unit_id",
    "candidate_id",
    "item_sequence",
    "product_id",
    "product_name",
    "ingredient_ids",
    "ingredient_names",
    "ingredient_scope",
    "document_type",
    "source_id",
    "source_url",
    "source_version",
    "document_revision_date",
    "document_revision_status",
    "document_revision_basis",
    "document_revision_reason",
    "source_pdf_sha256",
    "source_page_text_sha256",
    "retrieved_at",
    "retrieved_at_utc",
    "source_locator",
    "representative_evidence_text",
    "evidence_text_variant_count",
    "evidence_text_variants_json",
    "evidence_text_override_count",
    "candidate_link_count",
    "rule_types",
    "duplicate_flag",
    "duplicate_group",
    "duplicate_location",
    "duplicate_location_group_id",
    "duplicate_text",
    "duplicate_text_group_ids",
]

LINK_FIELDS = [
    "evidence_candidate_id",
    "evidence_unit_id",
    "rule_id",
    "rule_type",
    "referenced_rule_status",
    "severity",
    "candidate_id",
    "item_sequence",
    "product_id",
    "product_name",
    "ingredient_ids",
    "ingredient_names",
    "ingredient_scope",
    "document_type",
    "source_id",
    "source_url",
    "source_version",
    "document_revision_date",
    "document_revision_status",
    "document_revision_basis",
    "document_revision_reason",
    "source_pdf_sha256",
    "source_page_text_sha256",
    "retrieved_at",
    "retrieved_at_utc",
    "raw_candidate_source_locator",
    "raw_candidate_evidence_text",
    "official_source_locator",
    "official_source_text",
    "evidence_text_override",
    "evidence_text_override_reason",
    "shortlist_source_locator",
    "shortlist_evidence_text",
    "shortlist_changed_from_candidate",
    "reviewed_source_locator",
    "reviewed_evidence_text",
    "operational_source_locator",
    "operational_evidence_text",
    "rule_scope",
    "referenced_runtime_condition",
    "rule_message_ko",
    "next_action_ko",
    "referenced_code_link",
    "shortlist_rank",
    "recommendation",
    "evidence_status",
    "candidate_operational_status",
    "status_reason",
    "analysis_status",
    "analysis_exclusion_reason",
    "duplicate_flag",
    "duplicate_group",
    "duplicate_location",
    "duplicate_location_group_id",
    "duplicate_text",
    "duplicate_text_group_id",
    "reviewer_id",
    "reviewer_role",
    "reviewed_at",
]

QUEUE_FIELDS = [
    "evidence_candidate_id",
    "evidence_unit_id",
    "rule_id",
    "rule_type",
    "referenced_rule_status",
    "candidate_operational_status",
    "shortlist_rank",
    "recommendation",
    "product_name",
    "item_sequence",
    "ingredient_ids",
    "ingredient_names",
    "ingredient_scope",
    "current_rule_scope",
    "referenced_runtime_condition",
    "proposed_message_ko",
    "proposed_next_action_ko",
    "document_type",
    "source_id",
    "source_url",
    "source_version",
    "document_revision_date",
    "document_revision_status",
    "document_revision_basis",
    "document_revision_reason",
    "retrieved_at",
    "retrieved_at_utc",
    "raw_candidate_source_locator",
    "raw_candidate_evidence_text",
    "official_source_locator",
    "official_source_text",
    "proposed_review_source_locator",
    "proposed_review_evidence_text",
    "reviewed_source_locator",
    "reviewed_evidence_text",
    "operational_source_locator",
    "operational_evidence_text",
    "evidence_text_override",
    "evidence_text_override_reason",
    "referenced_code_link",
    "duplicate_flag",
    "duplicate_group",
    "review_status",
    "status_reason",
    "review_question",
    "adoption_options",
    "required_regression_tests",
    "review_decision",
    "review_comment",
    "reviewer_id",
    "reviewer_role",
    "reviewed_at",
]

QUEUE_HUMAN_REVIEW_FIELDS = [
    "review_decision",
    "review_comment",
    "reviewer_id",
    "reviewer_role",
    "reviewed_at",
]

INPUT_PATHS = [
    "scripts/research/otc/build_v51_evidence_review.py",
    "scripts/research/otc/audit_v51_boundaries.py",
    "research_v51/review/shortlist_semantic_triage.csv",
    "research_v3/otc/rules/official_evidence_candidates.csv",
    "research_v3/otc/rules/rule_evidence_shortlist.csv",
    "research_v3/otc/rules/evidence_text_overrides.csv",
    "research_v3/otc/rules/rules.csv",
    "research_v3/otc/rules/runtime_rule_bindings.csv",
    "research_v3/otc/review/expert_rule_review.csv",
    "research_v3/otc/normalized/product_master.csv",
    "research_v3/otc/normalized/products.json",
    "research_v3/otc/normalized/product_ingredient.csv",
    "research_v3/otc/normalized/ingredient_master.csv",
    "research_v3/otc/normalized/analysis_exclusions.csv",
    "research_v3/otc/extracted/nedrug/page_manifest.csv",
    "research_v3/otc/raw/nedrug/manifest.json",
    "src/lib/otc/engine.ts",
]
TRIAGE_RELATIVE = "research_v51/review/shortlist_semantic_triage.csv"
TRIAGE_REQUIRED_FIELDS = {
    "evidence_candidate_id",
    "rule_id",
    "rule_type",
    "product_name",
    "item_sequence",
    "current_scope",
    "semantic_relation",
    "recommended_status",
    "proposed_trigger",
    "expected_decision_ko",
    "decision_reason_ko",
    "expert_question_ko",
}
TRIAGE_ALLOWED_STATUSES = {"needs_expert_review", "provisional", "rejected"}
REVISION_STATUS_REPORTED = "reported_in_archived_mfds_change_history"
REVISION_STATUS_NOT_REPORTED = "not_reported_in_archived_mfds_change_history"
REVISION_DOCUMENT_TOKENS = {
    "UD": ("용법용량",),
    "NB": ("사용상주의사항", "사용상의주의사항"),
}


class MfdsChangeHistoryParser(HTMLParser):
    """Collect cells from the archived MFDS change-history table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found_table = False
        self.caption = ""
        self.rows: list[list[str]] = []
        self._capturing = False
        self._table_depth = 0
        self._caption_parts: list[str] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if self._capturing:
                self._table_depth += 1
                return
            if dict(attrs).get("id") == "tblChf":
                self.found_table = True
                self._capturing = True
                self._table_depth = 1
            return
        if not self._capturing:
            return
        if tag == "caption":
            self._caption_parts = []
        elif tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)
        if self._caption_parts is not None:
            self._caption_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._capturing:
            return
        if tag in {"th", "td"} and self._cell_parts is not None:
            if self._row is not None:
                self._row.append(" ".join("".join(self._cell_parts).split()))
            self._cell_parts = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        elif tag == "caption" and self._caption_parts is not None:
            self.caption = " ".join("".join(self._caption_parts).split())
            self._caption_parts = None
        elif tag == "table":
            self._table_depth -= 1
            if self._table_depth == 0:
                self._capturing = False


def document_revision_metadata(
    payload: bytes, relative: str, document_type: str
) -> dict[str, str]:
    if document_type not in REVISION_DOCUMENT_TOKENS:
        raise ValueError(f"unsupported revision document type: {document_type}")
    parser = MfdsChangeHistoryParser()
    parser.feed(payload.decode("utf-8-sig"))
    parser.close()
    if not parser.found_table:
        return {
            "document_revision_date": "",
            "document_revision_status": REVISION_STATUS_NOT_REPORTED,
            "document_revision_basis": "",
            "document_revision_reason": (
                "change_history_table_not_present_in_archived_mfds_detail"
            ),
        }
    if "변경이력" not in normalize_text(parser.caption):
        raise ValueError(f"MFDS change history caption mismatch: {relative}")
    if not parser.rows or [normalize_text(value) for value in parser.rows[0][:3]] != [
        "순번",
        "변경일자",
        "변경항목",
    ]:
        raise ValueError(f"MFDS change history columns mismatch: {relative}")

    matching: list[tuple[str, str]] = []
    for row in parser.rows[1:]:
        if len(row) < 3:
            continue
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", row[1])
        if not date_match:
            continue
        revision_date = date_match.group(0)
        try:
            date.fromisoformat(revision_date)
        except ValueError as exc:
            raise ValueError(
                f"invalid MFDS change history date: {relative} {revision_date}"
            ) from exc
        change_item = re.sub(r"^변경항목\s*", "", row[2]).strip()
        normalized_item = normalize_text(change_item)
        if any(
            token in normalized_item
            for token in REVISION_DOCUMENT_TOKENS[document_type]
        ):
            matching.append((revision_date, change_item))

    if not matching:
        return {
            "document_revision_date": "",
            "document_revision_status": REVISION_STATUS_NOT_REPORTED,
            "document_revision_basis": "",
            "document_revision_reason": (
                f"no_{document_type.lower()}_entry_in_archived_mfds_change_history"
            ),
        }
    revision_date, change_item = max(matching, key=lambda value: value[0])
    return {
        "document_revision_date": revision_date,
        "document_revision_status": REVISION_STATUS_REPORTED,
        "document_revision_basis": (
            f"baseline_git_blob:{relative}#tblChf; change_item={change_item}"
        ),
        "document_revision_reason": "",
    }


def read_csv_bytes(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline="")))


def read_protected_csv(root: Path, relative: str) -> list[dict[str, str]]:
    return read_csv_bytes(
        boundary_audit.git_blob_bytes(root, BASELINE_COMMIT, relative)
    )


def read_protected_json(root: Path, relative: str) -> dict[str, object]:
    payload = boundary_audit.git_blob_bytes(root, BASELINE_COMMIT, relative)
    return json.loads(payload.decode("utf-8-sig"))


def require_protected_boundary(root: Path) -> None:
    errors = boundary_audit.git_boundary_errors(
        root, boundary_audit.pinned_boundary_manifest()
    )
    if errors:
        raise ValueError("v5.0 protected boundary invalid: " + " | ".join(errors))


def protected_input_lineage(root: Path, relative: str) -> dict[str, object]:
    payload = boundary_audit.git_blob_bytes(root, BASELINE_COMMIT, relative)
    return {
        "basis": "baseline_git_blob",
        "baseline_commit": BASELINE_COMMIT,
        "git_blob_oid": boundary_audit.git_blob_oid(root, BASELINE_COMMIT, relative),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def require_git_blob_identity(root: Path, relative: str, payload: bytes) -> None:
    expected_oid = boundary_audit.git_blob_oid(root, BASELINE_COMMIT, relative)
    header = f"blob {len(payload)}\0".encode("ascii")
    actual_oid = hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()
    if actual_oid != expected_oid:
        raise ValueError(
            f"baseline Git blob identity mismatch: {relative} "
            f"expected={expected_oid} observed={actual_oid}"
        )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(character for character in normalized if character.isalnum())


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{sha256_bytes(value.encode('utf-8'))[:16]}"


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def unique_by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row[key]
        if value in output:
            raise ValueError(f"duplicate {key}: {value}")
        output[value] = row
    return output


def runtime_condition(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "scope_only_no_structured_binding"
    fields = [
        "item_sequence",
        "ingredient_id",
        "max_daily_amount",
        "minimum_interval_hours",
        "minimum_age_years",
        "maximum_continuous_days",
        "flags",
        "red_flag_terms",
    ]
    conditions = []
    for row in sorted(
        rows, key=lambda value: tuple(value.get(field, "") for field in fields)
    ):
        conditions.append(
            "|".join(f"{field}={row[field]}" for field in fields if row.get(field))
        )
    return " || ".join(conditions)


def source_page(source_locator: str) -> str:
    match = re.search(r"PDF p\.(\d+)", source_locator)
    if not match:
        raise ValueError(f"source page missing from locator: {source_locator}")
    return match.group(1)


def source_paragraph(source_locator: str) -> int:
    return source_paragraph_span(source_locator)[0]


def source_paragraph_span(source_locator: str) -> tuple[int, int]:
    match = re.search(r"문단\s+(\d+)(?:-(\d+))?", source_locator)
    if not match:
        raise ValueError(f"source paragraph missing from locator: {source_locator}")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if end < start:
        raise ValueError(f"source paragraph range is reversed: {source_locator}")
    return start, end


def candidate_page_paragraph(evidence_candidate_id: str) -> tuple[str, int]:
    match = re.search(r"-P(\d+)-B(\d+)-", evidence_candidate_id)
    if not match:
        raise ValueError(
            f"page/paragraph missing from candidate ID: {evidence_candidate_id}"
        )
    return match.group(1), int(match.group(2))


def extracted_paragraphs(page: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", value).strip()
        for value in re.split(r"(?:\r?\n){2,}", page)
        if value.strip()
    ]


def source_block_ends_sentence(value: str) -> bool:
    stripped = value.rstrip()
    bracket_pairs = (("(", ")"), ("[", "]"), ("{", "}"), ("（", "）"))
    if any(
        stripped.count(opening) != stripped.count(closing)
        for opening, closing in bracket_pairs
    ):
        return False
    return bool(re.search(r"[.!?。！？](?:[\"'”’\]}>）〉》」』】]*)$", stripped))


def official_source_for_locator(
    page_text_by_key: dict[tuple[str, str, str], str],
    *,
    item_sequence: str,
    document_type: str,
    source_locator: str,
) -> tuple[str, str]:
    page_key = (item_sequence, document_type, source_page(source_locator))
    page_text = page_text_by_key.get(page_key)
    if page_text is None:
        raise ValueError(f"official source page missing from page manifest: {page_key}")
    paragraphs = extracted_paragraphs(page_text)
    selected_start, selected_end = source_paragraph_span(source_locator)
    if selected_end > len(paragraphs):
        raise ValueError(
            "official source paragraph range missing from extracted page: "
            f"{item_sequence} {document_type} {source_locator}"
        )
    expanded_start = selected_start
    while expanded_start > 1 and not source_block_ends_sentence(
        paragraphs[expanded_start - 2]
    ):
        expanded_start -= 1
    expanded_end = selected_end
    while expanded_end < len(paragraphs) and not source_block_ends_sentence(
        paragraphs[expanded_end - 1]
    ):
        expanded_end += 1
    expanded_span = (
        str(expanded_start)
        if expanded_start == expanded_end
        else f"{expanded_start}-{expanded_end}"
    )
    expanded_locator = re.sub(
        r"(문단\s+)\d+(?:-\d+)?",
        lambda match: f"{match.group(1)}{expanded_span}",
        source_locator,
        count=1,
    )
    return expanded_locator, "\n\n".join(paragraphs[expanded_start - 1 : expanded_end])


def official_text_for_locator(
    page_text_by_key: dict[tuple[str, str, str], str],
    *,
    item_sequence: str,
    document_type: str,
    source_locator: str,
) -> str:
    return official_source_for_locator(
        page_text_by_key,
        item_sequence=item_sequence,
        document_type=document_type,
        source_locator=source_locator,
    )[1]


def non_target_product_fixture(
    link: dict[str, str],
    *,
    products: list[dict[str, str]],
    ingredient_pairs_by_product: dict[str, set[tuple[str, str]]],
) -> tuple[str, str, str]:
    candidate_ingredients = set(link["ingredient_ids"].split(";"))
    for product in sorted(products, key=lambda row: row["item_sequence"]):
        if (
            product["analysis_status"] != "included"
            or product["item_sequence"] == link["item_sequence"]
        ):
            continue
        ingredient_ids = {
            ingredient_id
            for ingredient_id, _ in ingredient_pairs_by_product[product["product_id"]]
        }
        if candidate_ingredients.isdisjoint(ingredient_ids):
            return (
                product["item_sequence"],
                product["product_name"],
                ";".join(sorted(ingredient_ids)),
            )
    raise ValueError(
        "candidate-specific regression test has no disjoint non-target product: "
        f"{link['evidence_candidate_id']}"
    )


def required_regression_tests(
    link: dict[str, str],
    triage: dict[str, str],
    *,
    non_target: tuple[str, str, str],
) -> str:
    identity = regression_field_text(
        f"후보={link['evidence_candidate_id']}; 제품={link['product_name']}; "
        f"품목기준코드={link['item_sequence']}; 성분ID={link['ingredient_ids']}; "
        f"규칙={link['rule_id']}/{link['rule_type']}"
    )
    condition = regression_field_text(triage["proposed_trigger"])
    expected = regression_field_text(triage["expected_decision_ko"])
    status = triage["recommended_status"]
    non_target_sequence, non_target_name, non_target_ingredients = non_target
    if status == "rejected":
        normal_expectation = (
            f"권고상태=rejected; 예상판정={expected}; 예상={link['rule_id']} 미발동"
        )
        boundary_expectation = (
            "양성 경계 승인 없음; 후보 문맥과 인접 입력 모두 "
            f"예상={link['rule_id']} 미발동"
        )
    else:
        normal_expectation = (
            f"사람 승인 전 예상={link['rule_id']} 미발동; "
            f"채택 후 예상판정={expected}"
        )
        boundary_expectation = (
            "경계내 fixture=후보조건의 모든 수치·열거·문자 조건 정확히 충족; "
            f"채택 후 예상판정={expected}; 경계밖 fixture=후보조건 중 정확히 한 조건을 "
            f"비발동 쪽 1단위 또는 불일치값으로 변경; 예상={link['rule_id']} 미발동"
        )
    return "|".join(
        (
            (
                f"normal={identity}; 후보조건={condition}; 입력 fixture=후보조건 정확히 충족; "
                f"{normal_expectation}"
            ),
            (
                f"boundary={identity}; 후보조건={condition}; {boundary_expectation}"
            ),
            (
                f"non_target=후보={link['evidence_candidate_id']}; 비대상제품={non_target_name}; "
                f"품목기준코드={non_target_sequence}; 성분ID={non_target_ingredients}; "
                f"후보조건={condition}; 예상={link['rule_id']} 미발동; 후보판정문 미표시"
            ),
            (
                f"false_positive={identity}; 후보조건={condition}; 오탐 fixture=동일 제품에서 "
                "제안조건의 첫 수치 비교값을 비발동 쪽 1단위로 바꾸거나 첫 열거·문자값에 "
                f"-유사를 붙여 정확히 한 조건을 불충족; 예상={link['rule_id']} 미발동; "
                "지원하지 않는 입력이면 coverage gap 표시"
            ),
        )
    )


def regression_field_text(value: str) -> str:
    without_alternatives = re.sub(r"\s*\|\|\s*", " OR ", value)
    return " ".join(without_alternatives.replace("|", " AND ").split())


def require_complete_revision_metadata(
    rows: list[dict[str, str]], *, artifact: str
) -> None:
    for row in rows:
        status = row["document_revision_status"]
        if status == REVISION_STATUS_REPORTED:
            try:
                date.fromisoformat(row["document_revision_date"])
            except ValueError as exc:
                raise ValueError(
                    f"{artifact} has invalid document revision date: "
                    f"{row.get('evidence_candidate_id') or row.get('evidence_unit_id')}"
                ) from exc
            valid = bool(
                row["document_revision_basis"] and not row["document_revision_reason"]
            )
        elif status == REVISION_STATUS_NOT_REPORTED:
            valid = bool(
                not row["document_revision_date"]
                and not row["document_revision_basis"]
                and row["document_revision_reason"]
            )
        else:
            valid = False
        if not valid:
            raise ValueError(
                f"{artifact} has incomplete document revision metadata: "
                f"{row.get('evidence_candidate_id') or row.get('evidence_unit_id')}"
            )


def engine_links(root: Path, rule_types: set[str]) -> dict[str, str]:
    relative = Path("src/lib/otc/engine.ts")
    lines = (root / relative).read_text(encoding="utf-8").splitlines()
    output = {}
    for rule_type in sorted(rule_types):
        direct = f'ruleType: "{rule_type}"'
        line_number = next(
            (index for index, line in enumerate(lines, 1) if direct in line), None
        )
        if line_number is None:
            line_number = next(
                (
                    index
                    for index, line in enumerate(lines, 1)
                    if f'"{rule_type}"' in line
                ),
                None,
            )
        if line_number is None:
            raise ValueError(f"rule type missing from OTC engine: {rule_type}")
        output[rule_type] = f"{relative.as_posix()}:{line_number}"
    return output


def build(root: Path = ROOT) -> dict[str, object]:
    require_protected_boundary(root)
    candidates = read_protected_csv(
        root, "research_v3/otc/rules/official_evidence_candidates.csv"
    )
    shortlist = read_protected_csv(
        root, "research_v3/otc/rules/rule_evidence_shortlist.csv"
    )
    overrides = read_protected_csv(
        root, "research_v3/otc/rules/evidence_text_overrides.csv"
    )
    rules = read_protected_csv(root, "research_v3/otc/rules/rules.csv")
    bindings = read_protected_csv(
        root, "research_v3/otc/rules/runtime_rule_bindings.csv"
    )
    reviews = read_protected_csv(root, "research_v3/otc/review/expert_rule_review.csv")
    products = read_protected_csv(root, "research_v3/otc/normalized/product_master.csv")
    normalized_products = read_protected_json(
        root, "research_v3/otc/normalized/products.json"
    )
    product_ingredients = read_protected_csv(
        root, "research_v3/otc/normalized/product_ingredient.csv"
    )
    ingredients = read_protected_csv(
        root, "research_v3/otc/normalized/ingredient_master.csv"
    )
    exclusions = read_protected_csv(
        root, "research_v3/otc/normalized/analysis_exclusions.csv"
    )
    pages = read_protected_csv(
        root, "research_v3/otc/extracted/nedrug/page_manifest.csv"
    )
    raw_manifest = read_protected_json(root, "research_v3/otc/raw/nedrug/manifest.json")
    triage = read_csv_bytes((root / TRIAGE_RELATIVE).read_bytes())

    if len(candidates) != 360:
        raise ValueError(f"expected 360 v5.0 candidates, found {len(candidates)}")
    candidate_by_id = unique_by_key(candidates, "evidence_candidate_id")
    if len(triage) != 33:
        raise ValueError(f"expected 33 semantic triage rows, found {len(triage)}")
    if set(triage[0]) != TRIAGE_REQUIRED_FIELDS:
        raise ValueError("semantic triage fields do not match the required contract")
    triage_by_id = unique_by_key(triage, "evidence_candidate_id")
    shortlist_by_id = unique_by_key(shortlist, "evidence_candidate_id")
    override_by_id = unique_by_key(overrides, "evidence_candidate_id")
    if len(shortlist) != 48 or not set(shortlist_by_id) <= set(candidate_by_id):
        raise ValueError(
            "v5.0 shortlist must contain 48 candidate IDs from the 360-row master"
        )
    if len(overrides) != 7 or not set(override_by_id) <= set(candidate_by_id):
        raise ValueError(
            "v5.0 evidence overrides must contain 7 candidate IDs from the master"
        )

    rule_by_type = unique_by_key(rules, "rule_type")
    review_by_rule = unique_by_key(reviews, "rule_id")
    product_by_item = unique_by_key(products, "item_sequence")
    normalized_product_by_item = {row["item_seq"]: row for row in normalized_products}
    if len(normalized_product_by_item) != len(normalized_products):
        raise ValueError("duplicate item_seq in normalized products")
    ingredient_by_id = unique_by_key(ingredients, "ingredient_id")
    excluded_items = {row["item_sequence"]: row for row in exclusions}

    bindings_by_rule: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in bindings:
        bindings_by_rule[row["rule_id"]].append(row)

    ingredient_pairs_by_product: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in product_ingredients:
        ingredient = ingredient_by_id.get(row["ingredient_id"])
        if ingredient is None:
            raise ValueError(f"ingredient missing from master: {row['ingredient_id']}")
        ingredient_pairs_by_product[row["product_id"]].add(
            (row["ingredient_id"], ingredient["preferred_name_ko"])
        )

    pdf_hashes: dict[tuple[str, str], set[str]] = defaultdict(set)
    page_text_hashes: dict[tuple[str, str, str], str] = {}
    page_text_by_key: dict[tuple[str, str, str], str] = {}
    actual_pdf_hashes: dict[str, str] = {}
    extracted_pages: dict[str, list[str]] = {}
    candidate_extracted_pages: dict[str, list[str]] = {}
    for row in pages:
        pdf_path = root / row["pdf_path"]
        if row["pdf_path"] not in actual_pdf_hashes:
            actual_pdf_hashes[row["pdf_path"]] = sha256_file(pdf_path)
        if actual_pdf_hashes[row["pdf_path"]] != row["pdf_sha256"]:
            raise ValueError(f"page manifest PDF byte hash mismatch: {row['pdf_path']}")
        text_path = root / row["text_path"]
        if row["text_path"] not in extracted_pages:
            # extract_nedrug_pdf_text.py hashed pdftotext output before Windows text-mode
            # writing. Undo one CRLF translation without universal-newline collapsing.
            stored_text = text_path.read_bytes().decode("utf-8").replace("\r\n", "\n")
            values = stored_text.split("\f")
            if values and not values[-1].strip():
                values.pop()
            extracted_pages[row["text_path"]] = [value.strip() for value in values]
            # Preserve the universal-newline behavior used by the v5.0 candidate
            # generator. The stored Windows file contains CRCRLF sequences, while
            # the page manifest hashes the pre-write CRLF representation above.
            candidate_extracted_pages[row["text_path"]] = text_path.read_text(
                encoding="utf-8"
            ).split("\f")
        page_index = int(row["page"]) - 1
        values = extracted_pages[row["text_path"]]
        if page_index >= len(values):
            raise ValueError(
                f"extracted page missing: {row['text_path']} p.{row['page']}"
            )
        normalized_page = values[page_index]
        if sha256_bytes(normalized_page.encode("utf-8")) != row["page_text_sha256"]:
            raise ValueError(
                f"page text byte hash mismatch: {row['text_path']} p.{row['page']}"
            )
        if len(normalized_page) != int(row["character_count"]):
            raise ValueError(
                f"page text character count mismatch: {row['text_path']} p.{row['page']}"
            )
        pdf_hashes[(row["item_sequence"], row["document_type"])].add(row["pdf_sha256"])
        page_key = (row["item_sequence"], row["document_type"], row["page"])
        if page_key in page_text_hashes:
            raise ValueError(f"duplicate page manifest row: {page_key}")
        page_text_hashes[page_key] = row["page_text_sha256"]
        candidate_values = candidate_extracted_pages[row["text_path"]]
        if page_index >= len(candidate_values):
            raise ValueError(
                f"candidate extraction page missing: {row['text_path']} p.{row['page']}"
            )
        page_text_by_key[page_key] = candidate_values[page_index]
    for key, hashes in pdf_hashes.items():
        if len(hashes) != 1:
            raise ValueError(f"multiple PDF hashes for {key}: {sorted(hashes)}")

    raw_hash_by_path = {
        item["path"].replace("\\", "/"): item["sha256"]
        for record in raw_manifest["records"]
        for item in record["files"]
    }
    detail_paths = sorted(
        {
            f"research_v3/otc/raw/nedrug/{row['item_sequence']}/detail.html"
            for row in candidates
        }
    )
    revision_by_document: dict[tuple[str, str], dict[str, str]] = {}
    document_types_by_item: dict[str, set[str]] = defaultdict(set)
    for candidate in candidates:
        document_types_by_item[candidate["item_sequence"]].add(
            candidate["document_type"]
        )
    for relative in detail_paths:
        item_sequence = Path(relative).parent.name
        payload = boundary_audit.git_blob_bytes(root, BASELINE_COMMIT, relative)
        require_git_blob_identity(root, relative, payload)
        if relative not in raw_hash_by_path:
            raise ValueError(f"raw manifest detail HTML entry missing: {relative}")
        for document_type in sorted(document_types_by_item[item_sequence]):
            revision_by_document[(item_sequence, document_type)] = (
                document_revision_metadata(payload, relative, document_type)
            )
    code_links = engine_links(root, set(rule_by_type))

    for candidate in candidates:
        product = product_by_item.get(candidate["item_sequence"])
        normalized_product = normalized_product_by_item.get(candidate["item_sequence"])
        if product is None or normalized_product is None:
            raise ValueError(
                f"candidate product missing: {candidate['evidence_candidate_id']}"
            )
        if (
            candidate["candidate_id"] != product["candidate_id"]
            or candidate["candidate_id"] != normalized_product["candidate_id"]
            or candidate["product_name"] != product["product_name"]
            or candidate["product_name"] != normalized_product["product_name"]
            or candidate["source_id"] != product["source_id"]
            or candidate["source_id"] != normalized_product["source_id"]
        ):
            raise ValueError(
                "candidate/product identity mismatch: "
                f"{candidate['evidence_candidate_id']}"
            )
        if candidate["document_type"] not in {"UD", "NB"}:
            raise ValueError(
                f"unsupported candidate document: {candidate['document_type']}"
            )
        document_url_field = (
            "dosage_pdf_url"
            if candidate["document_type"] == "UD"
            else "precautions_pdf_url"
        )
        if normalized_product[document_url_field] != candidate["source_url"]:
            raise ValueError(
                f"candidate/source URL mismatch: {candidate['evidence_candidate_id']}"
            )
        locator_page = source_page(candidate["source_locator"])
        locator_paragraph = source_paragraph(candidate["source_locator"])
        id_page, id_paragraph = candidate_page_paragraph(
            candidate["evidence_candidate_id"]
        )
        if (locator_page, locator_paragraph) != (id_page, id_paragraph):
            raise ValueError(
                "candidate ID/source locator mismatch: "
                f"{candidate['evidence_candidate_id']}"
            )
        expected_candidate_id = (
            f"{candidate['candidate_id']}-{candidate['document_type']}-"
            f"P{locator_page}-B{locator_paragraph}-{candidate['rule_type']}"
        )
        if candidate["evidence_candidate_id"] != expected_candidate_id:
            raise ValueError(
                "candidate ID/product or rule identity mismatch: "
                f"{candidate['evidence_candidate_id']}"
            )
        page_key = (
            candidate["item_sequence"],
            candidate["document_type"],
            locator_page,
        )
        page_text = page_text_by_key.get(page_key)
        if page_text is None:
            raise ValueError(
                f"candidate source page missing from page manifest: {page_key}"
            )
        paragraphs = extracted_paragraphs(page_text)
        if locator_paragraph > len(paragraphs):
            raise ValueError(
                "candidate source paragraph missing from extracted page: "
                f"{candidate['evidence_candidate_id']}"
            )
        if candidate["evidence_candidate_id"] not in override_by_id:
            expected_text = paragraphs[locator_paragraph - 1][:1200]
            if candidate["evidence_text"] != expected_text:
                raise ValueError(
                    "candidate evidence text mismatch with extracted paragraph: "
                    f"{candidate['evidence_candidate_id']}"
                )

    location_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for candidate in candidates:
        location_groups[(candidate["source_url"], candidate["source_locator"])].append(
            candidate
        )
    if len(location_groups) != 328:
        raise ValueError(f"expected 328 source locations, found {len(location_groups)}")

    unit_id_by_location = {
        key: stable_id("OTC-V51-EU", "\x1f".join(key)) for key in location_groups
    }
    if len(set(unit_id_by_location.values())) != len(unit_id_by_location):
        raise ValueError("evidence unit hash collision")

    normalized_text_units: dict[str, set[str]] = defaultdict(set)
    for location, rows in location_groups.items():
        unit_id = unit_id_by_location[location]
        for text in {row["evidence_text"] for row in rows}:
            normalized_text_units[normalize_text(text)].add(unit_id)
    duplicate_text_group = {
        text: stable_id("OTC-V51-TEXT", text)
        for text, unit_ids in normalized_text_units.items()
        if text and len(unit_ids) > 1
    }

    units: list[dict[str, str]] = []
    for location in sorted(location_groups):
        rows = location_groups[location]
        first = rows[0]
        product = product_by_item.get(first["item_sequence"])
        if product is None:
            raise ValueError(f"candidate product missing: {first['item_sequence']}")
        normalized_product = normalized_product_by_item.get(first["item_sequence"])
        if normalized_product is None:
            raise ValueError(f"normalized product missing: {first['item_sequence']}")
        if normalized_product["candidate_id"] != first["candidate_id"]:
            raise ValueError(
                f"candidate/product identity mismatch: {first['item_sequence']}"
            )
        if first["document_type"] not in {"UD", "NB"}:
            raise ValueError(
                f"unsupported candidate document: {first['document_type']}"
            )
        document_url_field = (
            "dosage_pdf_url"
            if first["document_type"] == "UD"
            else "precautions_pdf_url"
        )
        if normalized_product[document_url_field] != first["source_url"]:
            raise ValueError(
                f"candidate/source URL mismatch: {first['evidence_candidate_id']}"
            )
        pairs = sorted(ingredient_pairs_by_product[product["product_id"]])
        if not pairs:
            raise ValueError(
                f"candidate product has no ingredient names: {product['product_id']}"
            )
        pdf_key = (first["item_sequence"], first["document_type"])
        hashes = pdf_hashes.get(pdf_key)
        if not hashes:
            raise ValueError(f"candidate PDF hash missing: {pdf_key}")
        pdf_sha256 = next(iter(hashes))
        raw_pdf_path = f"research_v3/otc/raw/nedrug/{first['item_sequence']}/{first['document_type']}.pdf"
        if raw_hash_by_path.get(raw_pdf_path) != pdf_sha256:
            raise ValueError(f"raw manifest PDF hash mismatch: {raw_pdf_path}")
        page_key = (
            first["item_sequence"],
            first["document_type"],
            source_page(first["source_locator"]),
        )
        page_text_sha256 = page_text_hashes.get(page_key)
        if not page_text_sha256:
            raise ValueError(f"candidate page text hash missing: {page_key}")
        revision = revision_by_document.get(pdf_key)
        if revision is None:
            raise ValueError(f"candidate document revision metadata missing: {pdf_key}")
        texts = sorted(
            {row["evidence_text"] for row in rows},
            key=lambda value: (-len(value), value),
        )
        text_group_ids = sorted(
            {
                duplicate_text_group[normalize_text(text)]
                for text in texts
                if normalize_text(text) in duplicate_text_group
            }
        )
        unit_id = unit_id_by_location[location]
        duplicate_location = len(rows) > 1
        duplicate_text = bool(text_group_ids)
        duplicate_groups = []
        if duplicate_location:
            duplicate_groups.append(f"location:{unit_id}")
        duplicate_groups.extend(f"text:{value}" for value in text_group_ids)
        units.append(
            {
                "evidence_unit_id": unit_id,
                "candidate_id": first["candidate_id"],
                "item_sequence": first["item_sequence"],
                "product_id": product["product_id"],
                "product_name": first["product_name"],
                "ingredient_ids": ";".join(value[0] for value in pairs),
                "ingredient_names": ";".join(value[1] for value in pairs),
                "ingredient_scope": "product_authorized_ingredient_set_not_excerpt_attribution",
                "document_type": first["document_type"],
                "source_id": first["source_id"],
                "source_url": first["source_url"],
                "source_version": f"sha256:{pdf_sha256}",
                **revision,
                "source_pdf_sha256": pdf_sha256,
                "source_page_text_sha256": page_text_sha256,
                "retrieved_at": product["retrieved_at"],
                "retrieved_at_utc": normalized_product["retrieved_at_utc"],
                "source_locator": first["source_locator"],
                "representative_evidence_text": texts[0],
                "evidence_text_variant_count": str(len(texts)),
                "evidence_text_variants_json": json.dumps(texts, ensure_ascii=False),
                "evidence_text_override_count": str(
                    sum(row["evidence_candidate_id"] in override_by_id for row in rows)
                ),
                "candidate_link_count": str(len(rows)),
                "rule_types": ";".join(sorted({row["rule_type"] for row in rows})),
                "duplicate_flag": bool_text(duplicate_location or duplicate_text),
                "duplicate_group": ";".join(duplicate_groups),
                "duplicate_location": bool_text(duplicate_location),
                "duplicate_location_group_id": unit_id if duplicate_location else "",
                "duplicate_text": bool_text(duplicate_text),
                "duplicate_text_group_ids": ";".join(text_group_ids),
            }
        )

    require_complete_revision_metadata(units, artifact="evidence_units")
    unit_by_id = {row["evidence_unit_id"]: row for row in units}
    links: list[dict[str, str]] = []
    for candidate in candidates:
        rule = rule_by_type.get(candidate["rule_type"])
        if rule is None:
            raise ValueError(f"candidate rule type missing: {candidate['rule_type']}")
        product = product_by_item[candidate["item_sequence"]]
        pairs = sorted(ingredient_pairs_by_product[product["product_id"]])
        shortlist_row = shortlist_by_id.get(candidate["evidence_candidate_id"])
        override = override_by_id.get(candidate["evidence_candidate_id"])
        exclusion = excluded_items.get(candidate["item_sequence"])
        review = review_by_rule.get(rule["rule_id"])

        verified_primary = bool(
            shortlist_row
            and shortlist_row["recommendation"] == "recommended_primary"
            and shortlist_row["review_status"] == "human_expert_verified"
            and shortlist_row["supports_release"] == "true"
            and rule["status"] == "released"
            and review
            and review["decision"] == "approve"
            and review["reviewer_role"] == "pharmacist_expert"
        )
        if exclusion:
            evidence_status = "rejected"
            status_reason = "analysis_excluded_product"
        elif verified_primary:
            evidence_status = "verified_primary"
            status_reason = "expert_primary_released"
        elif shortlist_row:
            evidence_status = "needs_expert_review"
            status_reason = (
                "pharmacist_requested_revision"
                if shortlist_row["recommendation"] == "recommended_primary"
                and review
                and review["decision"] == "revise"
                else "shortlisted_context_not_expert_verified"
            )
        else:
            evidence_status = "provisional"
            status_reason = "machine_candidate_not_shortlisted"

        reviewer_id = review["reviewer_id"] if verified_primary and review else ""
        reviewer_role = review["reviewer_role"] if verified_primary and review else ""
        reviewed_at = review["reviewed_at"] if verified_primary and review else ""
        candidate_operational_status = (
            "active_existing_released_primary_evidence"
            if evidence_status == "verified_primary" and verified_primary
            else "inactive_candidate"
        )
        location = (candidate["source_url"], candidate["source_locator"])
        unit = unit_by_id[unit_id_by_location[location]]
        if override and (
            override["source_sha256"] != unit["source_pdf_sha256"]
            or override["evidence_text"] != candidate["evidence_text"]
        ):
            raise ValueError(
                f"evidence text override provenance mismatch: {candidate['evidence_candidate_id']}"
            )
        text_group_id = duplicate_text_group.get(
            normalize_text(candidate["evidence_text"]), ""
        )
        shortlist_changed = bool(
            shortlist_row
            and (
                shortlist_row["source_locator"] != candidate["source_locator"]
                or shortlist_row["evidence_text"] != candidate["evidence_text"]
            )
        )
        reviewed_source_locator = (
            shortlist_row["source_locator"]
            if candidate_operational_status
            == "active_existing_released_primary_evidence"
            and shortlist_row
            else ""
        )
        reviewed_evidence_text = (
            shortlist_row["evidence_text"]
            if candidate_operational_status
            == "active_existing_released_primary_evidence"
            and shortlist_row
            else ""
        )
        proposed_source_locator = (
            shortlist_row["source_locator"]
            if shortlist_row
            else candidate["source_locator"]
        )
        official_source_locator, official_source_text = official_source_for_locator(
            page_text_by_key,
            item_sequence=candidate["item_sequence"],
            document_type=candidate["document_type"],
            source_locator=proposed_source_locator,
        )
        links.append(
            {
                "evidence_candidate_id": candidate["evidence_candidate_id"],
                "evidence_unit_id": unit["evidence_unit_id"],
                "rule_id": rule["rule_id"],
                "rule_type": candidate["rule_type"],
                "referenced_rule_status": rule["status"],
                "severity": rule["severity"],
                "candidate_id": candidate["candidate_id"],
                "item_sequence": candidate["item_sequence"],
                "product_id": product["product_id"],
                "product_name": candidate["product_name"],
                "ingredient_ids": ";".join(value[0] for value in pairs),
                "ingredient_names": ";".join(value[1] for value in pairs),
                "ingredient_scope": "product_authorized_ingredient_set_not_excerpt_attribution",
                "document_type": candidate["document_type"],
                "source_id": candidate["source_id"],
                "source_url": candidate["source_url"],
                "source_version": unit["source_version"],
                "document_revision_date": unit["document_revision_date"],
                "document_revision_status": unit["document_revision_status"],
                "document_revision_basis": unit["document_revision_basis"],
                "document_revision_reason": unit["document_revision_reason"],
                "source_pdf_sha256": unit["source_pdf_sha256"],
                "source_page_text_sha256": unit["source_page_text_sha256"],
                "retrieved_at": unit["retrieved_at"],
                "retrieved_at_utc": unit["retrieved_at_utc"],
                "raw_candidate_source_locator": candidate["source_locator"],
                "raw_candidate_evidence_text": candidate["evidence_text"],
                "official_source_locator": official_source_locator,
                "official_source_text": official_source_text,
                "evidence_text_override": bool_text(bool(override)),
                "evidence_text_override_reason": override["correction_reason"]
                if override
                else "",
                "shortlist_source_locator": shortlist_row["source_locator"]
                if shortlist_row
                else "",
                "shortlist_evidence_text": shortlist_row["evidence_text"]
                if shortlist_row
                else "",
                "shortlist_changed_from_candidate": bool_text(shortlist_changed),
                "reviewed_source_locator": reviewed_source_locator,
                "reviewed_evidence_text": reviewed_evidence_text,
                "operational_source_locator": reviewed_source_locator,
                "operational_evidence_text": reviewed_evidence_text,
                "rule_scope": rule["scope"],
                "referenced_runtime_condition": runtime_condition(
                    bindings_by_rule[rule["rule_id"]]
                ),
                "rule_message_ko": rule["message_ko"],
                "next_action_ko": rule["next_action_ko"],
                "referenced_code_link": code_links[candidate["rule_type"]],
                "shortlist_rank": shortlist_row["rank"] if shortlist_row else "",
                "recommendation": shortlist_row["recommendation"]
                if shortlist_row
                else "",
                "evidence_status": evidence_status,
                "candidate_operational_status": candidate_operational_status,
                "status_reason": status_reason,
                "analysis_status": product["analysis_status"],
                "analysis_exclusion_reason": (
                    exclusion["exclusion_reason"]
                    if exclusion
                    else product["analysis_exclusion_reason"]
                ),
                "duplicate_flag": bool_text(
                    unit["duplicate_location"] == "true" or bool(text_group_id)
                ),
                "duplicate_group": ";".join(
                    value
                    for value in (
                        f"location:{unit['evidence_unit_id']}"
                        if unit["duplicate_location"] == "true"
                        else "",
                        f"text:{text_group_id}" if text_group_id else "",
                    )
                    if value
                ),
                "duplicate_location": unit["duplicate_location"],
                "duplicate_location_group_id": unit["duplicate_location_group_id"],
                "duplicate_text": bool_text(bool(text_group_id)),
                "duplicate_text_group_id": text_group_id,
                "reviewer_id": reviewer_id,
                "reviewer_role": reviewer_role,
                "reviewed_at": reviewed_at,
            }
        )

    links.sort(key=lambda row: row["evidence_candidate_id"])
    require_complete_revision_metadata(links, artifact="evidence_rule_links")
    status_counts = Counter(row["evidence_status"] for row in links)
    expected_status_counts = {
        "verified_primary": 15,
        "needs_expert_review": 33,
        "rejected": 4,
        "provisional": 308,
    }
    if dict(status_counts) != expected_status_counts:
        raise ValueError(f"unexpected v5.1 status counts: {dict(status_counts)}")
    review_links = {
        row["evidence_candidate_id"]: row
        for row in links
        if row["evidence_status"] == "needs_expert_review"
    }
    if set(triage_by_id) != set(review_links):
        raise ValueError("semantic triage candidate IDs do not match the expert queue")
    for candidate_id, triage_row in triage_by_id.items():
        link = review_links[candidate_id]
        for field, expected in {
            "rule_id": link["rule_id"],
            "rule_type": link["rule_type"],
            "product_name": link["product_name"],
            "item_sequence": link["item_sequence"],
            "current_scope": link["rule_scope"],
        }.items():
            if triage_row[field] != expected:
                raise ValueError(
                    f"semantic triage {field} mismatch for {candidate_id}: "
                    f"{triage_row[field]!r} != {expected!r}"
                )
        if triage_row["recommended_status"] not in TRIAGE_ALLOWED_STATUSES:
            raise ValueError(
                f"unsupported semantic triage status for {candidate_id}: "
                f"{triage_row['recommended_status']}"
            )
        for field in ("proposed_trigger", "expected_decision_ko"):
            if not triage_row[field].strip():
                raise ValueError(f"semantic triage {field} is blank for {candidate_id}")
    operational_counts = Counter(row["candidate_operational_status"] for row in links)
    expected_operational_counts = {
        "active_existing_released_primary_evidence": 15,
        "inactive_candidate": 345,
    }
    if dict(operational_counts) != expected_operational_counts:
        raise ValueError(
            "unexpected candidate operational status counts: "
            f"{dict(operational_counts)}"
        )
    for row in links:
        active = (
            row["candidate_operational_status"]
            == "active_existing_released_primary_evidence"
        )
        active_contract = (
            row["evidence_status"] == "verified_primary"
            and row["referenced_rule_status"] == "released"
            and row["recommendation"] == "recommended_primary"
            and row["reviewer_id"]
            and row["reviewer_role"] == "pharmacist_expert"
            and row["reviewed_at"]
            and row["reviewed_source_locator"]
            and row["reviewed_evidence_text"]
            and row["operational_source_locator"] == row["reviewed_source_locator"]
            and row["operational_evidence_text"] == row["reviewed_evidence_text"]
            and re.fullmatch(r"sha256:[0-9a-f]{64}", row["source_version"]) is not None
            and row["source_version"] == f"sha256:{row['source_pdf_sha256']}"
        )
        if active != bool(active_contract):
            raise ValueError(
                "candidate operational status violates activation contract: "
                f"{row['evidence_candidate_id']}"
            )
        if not active and any(
            row[field]
            for field in (
                "reviewed_source_locator",
                "reviewed_evidence_text",
                "operational_source_locator",
                "operational_evidence_text",
            )
        ):
            raise ValueError(
                "inactive candidate carries reviewed or operational evidence: "
                f"{row['evidence_candidate_id']}"
            )
    rule_016_active = [
        row
        for row in links
        if row["rule_id"] == "OTC-RULE-016"
        and row["candidate_operational_status"]
        == "active_existing_released_primary_evidence"
    ]
    if (
        len(rule_016_active) != 1
        or rule_016_active[0]["operational_source_locator"]
        != "사용상의주의사항 PDF p.2, 문단 12-19"
    ):
        raise ValueError(
            "OTC-RULE-016 operational evidence must use the human-reviewed locator"
        )
    if any(
        (row["reviewer_id"] or row["reviewer_role"] or row["reviewed_at"])
        and row["evidence_status"] != "verified_primary"
        for row in links
    ):
        raise ValueError("reviewer metadata leaked onto a non-verified candidate")

    queue: list[dict[str, str]] = []
    for link in links:
        if link["evidence_status"] != "needs_expert_review":
            continue
        triage_row = triage_by_id[link["evidence_candidate_id"]]
        non_target = non_target_product_fixture(
            link,
            products=products,
            ingredient_pairs_by_product=ingredient_pairs_by_product,
        )
        queue.append(
            {
                "evidence_candidate_id": link["evidence_candidate_id"],
                "evidence_unit_id": link["evidence_unit_id"],
                "rule_id": link["rule_id"],
                "rule_type": link["rule_type"],
                "referenced_rule_status": link["referenced_rule_status"],
                "candidate_operational_status": link["candidate_operational_status"],
                "shortlist_rank": link["shortlist_rank"],
                "recommendation": link["recommendation"],
                "product_name": link["product_name"],
                "item_sequence": link["item_sequence"],
                "ingredient_ids": link["ingredient_ids"],
                "ingredient_names": link["ingredient_names"],
                "ingredient_scope": link["ingredient_scope"],
                "current_rule_scope": link["rule_scope"],
                "referenced_runtime_condition": link["referenced_runtime_condition"],
                "proposed_message_ko": link["rule_message_ko"],
                "proposed_next_action_ko": link["next_action_ko"],
                "document_type": link["document_type"],
                "source_id": link["source_id"],
                "source_url": link["source_url"],
                "source_version": link["source_version"],
                "document_revision_date": link["document_revision_date"],
                "document_revision_status": link["document_revision_status"],
                "document_revision_basis": link["document_revision_basis"],
                "document_revision_reason": link["document_revision_reason"],
                "retrieved_at": link["retrieved_at"],
                "retrieved_at_utc": link["retrieved_at_utc"],
                "raw_candidate_source_locator": link["raw_candidate_source_locator"],
                "raw_candidate_evidence_text": link["raw_candidate_evidence_text"],
                "official_source_locator": link["official_source_locator"],
                "official_source_text": link["official_source_text"],
                "proposed_review_source_locator": (
                    link["shortlist_source_locator"]
                    or link["raw_candidate_source_locator"]
                ),
                "proposed_review_evidence_text": (
                    link["shortlist_evidence_text"]
                    or link["raw_candidate_evidence_text"]
                ),
                "reviewed_source_locator": link["reviewed_source_locator"],
                "reviewed_evidence_text": link["reviewed_evidence_text"],
                "operational_source_locator": link["operational_source_locator"],
                "operational_evidence_text": link["operational_evidence_text"],
                "evidence_text_override": link["evidence_text_override"],
                "evidence_text_override_reason": link["evidence_text_override_reason"],
                "referenced_code_link": link["referenced_code_link"],
                "duplicate_flag": link["duplicate_flag"],
                "duplicate_group": link["duplicate_group"],
                "review_status": "needs_expert_review",
                "status_reason": link["status_reason"],
                "review_question": (
                    "이 원문이 제안한 제품·성분·조건과 사용자 문구를 직접 지지하는지 "
                    "확인하세요. 참조 규칙 실행 조건이 허가 범위를 넘지 않는지도 "
                    "확인하세요. 이 후보는 전문가 승인 전까지 운영에 사용하지 않습니다."
                ),
                "adoption_options": "adopt|revise|reject",
                "required_regression_tests": required_regression_tests(
                    link, triage_row, non_target=non_target
                ),
                "review_decision": "",
                "review_comment": "",
                "reviewer_id": "",
                "reviewer_role": "",
                "reviewed_at": "",
            }
        )
    if len(queue) != 33:
        raise ValueError(f"expected 33 expert review rows, found {len(queue)}")
    require_complete_revision_metadata(queue, artifact="expert_review_queue")
    if any(
        row["candidate_operational_status"] != "inactive_candidate" for row in queue
    ):
        raise ValueError("expert review queue contains an active candidate")
    if any(
        row[field]
        for row in queue
        for field in (
            "reviewed_source_locator",
            "reviewed_evidence_text",
            "operational_source_locator",
            "operational_evidence_text",
            *QUEUE_HUMAN_REVIEW_FIELDS,
        )
    ):
        raise ValueError(
            "expert review queue contains reviewed, operational, or human decision data"
        )

    exact_text_counts = Counter(row["evidence_text"] for row in candidates)
    normalized_text_counts = Counter(
        normalize_text(row["evidence_text"]) for row in candidates
    )
    location_counts = Counter(
        (row["source_url"], row["source_locator"]) for row in candidates
    )
    inputs = {}
    for relative in [*INPUT_PATHS, *detail_paths]:
        if relative.startswith("research_v3/"):
            inputs[relative] = protected_input_lineage(root, relative)
        else:
            path = root / relative
            inputs[relative] = {
                "basis": "worktree_bytes",
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
    manifest = {
        "schema_version": "1.2.0",
        "release_lineage": "v5.1",
        "source_lineage": "v5.0_pinned_baseline_git_blobs",
        "generator": "scripts/research/otc/build_v51_evidence_review.py",
        "generator_sha256": inputs["scripts/research/otc/build_v51_evidence_review.py"][
            "sha256"
        ],
        "raw_manifest_updated_at_utc": raw_manifest["retrieved_at_utc"],
        "source_retrieved_at_utc_values": sorted(
            {row["retrieved_at_utc"] for row in normalized_products}
        ),
        "inputs": inputs,
        "artifacts": {},
        "counts": {
            "source_candidates": len(candidates),
            "evidence_units": len(units),
            "evidence_rule_links": len(links),
            "expert_review_queue": len(queue),
            "unique_products": len({row["item_sequence"] for row in candidates}),
            "unique_rule_types": len({row["rule_type"] for row in candidates}),
            "evidence_text_overrides": len(overrides),
            "shortlist_source_overlay_changes": sum(
                row.get("source_locator")
                != candidate_by_id[row["evidence_candidate_id"]]["source_locator"]
                or row.get("evidence_text")
                != candidate_by_id[row["evidence_candidate_id"]]["evidence_text"]
                for row in shortlist
            ),
            "status_counts": expected_status_counts,
            "candidate_operational_status_counts": expected_operational_counts,
            "document_revision_status_counts": dict(
                Counter(row["document_revision_status"] for row in links)
            ),
            "reviewed_primary_evidence_rows": sum(
                bool(row["reviewed_source_locator"] and row["reviewed_evidence_text"])
                for row in links
            ),
            "operational_evidence_rows": sum(
                bool(
                    row["operational_source_locator"]
                    and row["operational_evidence_text"]
                )
                for row in links
            ),
            "excluded_product_candidates": sum(
                row["evidence_status"] == "rejected" for row in links
            ),
            "source_location_duplicate_groups": sum(
                count > 1 for count in location_counts.values()
            ),
            "source_location_duplicate_extra_links": sum(
                count - 1 for count in location_counts.values() if count > 1
            ),
            "unique_exact_evidence_texts": len(exact_text_counts),
            "exact_text_duplicate_groups": sum(
                count > 1 for count in exact_text_counts.values()
            ),
            "unique_normalized_evidence_texts": len(normalized_text_counts),
            "normalized_text_duplicate_groups": sum(
                count > 1 for count in normalized_text_counts.values()
            ),
        },
        "status_contract": {
            "assignment_level": (
                "evidence_rule_links; evidence units remain status-free because one source "
                "location can support multiple rule tags"
            ),
            "verified_primary": (
                "v5.0 shortlist primary, human_expert_verified, supports_release=true, "
                "released rule, pharmacist approve"
            ),
            "needs_expert_review": "v5.0 shortlist row without row-level expert verification",
            "rejected": "candidate belongs to a product excluded from analysis and runtime",
            "provisional": "machine-matched authorization candidate not selected for the v5.0 shortlist",
            "activation_warning": (
                "evidence_status is a review classification, not the operational activation field"
            ),
        },
        "candidate_operational_status_contract": {
            "assignment_level": "evidence_rule_links",
            "field": "candidate_operational_status",
            "active_existing_released_primary_evidence": (
                "existing v5.0 primary evidence with human_expert_verified, "
                "supports_release=true, referenced released rule, pharmacist approve, "
                "and nonblank reviewer metadata"
            ),
            "inactive_candidate": (
                "every needs_expert_review, provisional, or rejected candidate; no review "
                "classification or referenced runtime/code context can activate a candidate"
            ),
            "active_count": 15,
            "inactive_count": 345,
            "context_only_fields": [
                "referenced_rule_status",
                "referenced_runtime_condition",
                "referenced_code_link",
            ],
            "reviewed_evidence_fields": [
                "reviewed_source_locator",
                "reviewed_evidence_text",
            ],
            "operational_evidence_fields": [
                "operational_source_locator",
                "operational_evidence_text",
                "source_version",
            ],
        },
        "duplicate_contract": {
            "evidence_unit_key": ["source_url", "source_locator"],
            "duplicate_location": "multiple rule-tag links share one evidence unit",
            "duplicate_text": "NFKC/casefold/alphanumeric-normalized text occurs at multiple evidence units",
            "candidate_links_are_preserved": True,
        },
        "ingredient_contract": {
            "scope": "product_authorized_ingredient_set_not_excerpt_attribution",
            "derivation": "product_id join, deduplicated by ingredient_id, preferred_name_ko display",
            "warning": (
                "ingredient_ids and ingredient_names describe the product formula; they do not "
                "claim that every listed ingredient is named or supported by each evidence excerpt"
            ),
        },
        "provenance_verification": {
            "raw_pdf_bytes_rehashed": True,
            "archived_detail_html_git_blobs_hashed": True,
            "extracted_page_text_rehashed": True,
            "candidate_product_identity_cross_checked": True,
            "candidate_document_url_cross_checked": True,
            "candidate_locator_id_cross_checked": True,
            "candidate_paragraphs_revalidated": True,
            "evidence_text_overrides_hash_checked": True,
        },
        "source_version_contract": {
            "source_version": (
                "SHA-256 identity of the archived local MFDS PDF bytes used for this snapshot"
            ),
            "source_page_text_sha256": (
                "SHA-256 of the extracted page text and the canonical content provenance "
                "for semantic comparison"
            ),
            "document_revision_date": (
                "latest document-type-specific change date parsed from the archived MFDS "
                "detail HTML change-history table"
            ),
            "document_revision_unavailable_policy": (
                "when no UD/NB-specific change-history row is present, keep the date and "
                "basis blank and record an explicit not-reported status and reason"
            ),
            "dynamic_endpoint_warning": (
                "MFDS PDF endpoints can regenerate byte-different PDFs at the same URL; "
                "remote PDF byte mismatch alone does not establish semantic drift"
            ),
            "freshness_policy": (
                "compare normalized extracted text before classifying semantic source drift"
            ),
        },
        "shortlist_overlay_contract": {
            "source_of_truth": (
                "official_evidence_candidates.csv source_url/source_locator/evidence_text"
            ),
            "raw_candidate_fields": (
                "raw_candidate_source_locator and raw_candidate_evidence_text"
            ),
            "overlay_fields": "shortlist_source_locator and shortlist_evidence_text",
            "reviewed_fields": (
                "reviewed_source_locator and reviewed_evidence_text; populated only for "
                "verified primary evidence"
            ),
            "operational_fields": (
                "operational_source_locator and operational_evidence_text; populated only "
                "for active_existing_released_primary_evidence"
            ),
            "policy": (
                "preserve raw candidates and shortlist context separately; active evidence "
                "uses the human-reviewed locator/text, including OTC-RULE-016 p.2 paragraphs 12-19"
            ),
        },
        "code_link_contract": {
            "path": "src/lib/otc/engine.ts",
            "field": "referenced_code_link",
            "derivation": (
                "first direct ruleType assignment, otherwise first exact quoted rule_type; "
                "informational link, not release authority"
            ),
            "line_numbers_bound_to_input_sha256": inputs["src/lib/otc/engine.ts"][
                "sha256"
            ],
            "regeneration_required_after_engine_change": True,
        },
        "review_boundary": {
            "expert_review_queue_status": "needs_expert_review",
            "expert_review_queue_operational_status": "inactive_candidate",
            "human_decisions_prefilled": 0,
            "existing_human_expert_verified_primary_rows": 15,
            "new_human_expert_reviews": 0,
            "expert_review_queue_human_fields": QUEUE_HUMAN_REVIEW_FIELDS,
            "reviewer_metadata_policy": (
                "only verified_primary rows preserve existing pharmacist reviewer_id and "
                "reviewer_role and reviewed_at; all expert review queue reviewer fields "
                "remain blank until human review"
            ),
        },
    }
    package = {
        "evidence_units": units,
        "evidence_rule_links": links,
        "expert_review_queue": queue,
        "manifest": manifest,
    }
    require_protected_boundary(root)
    return package


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def write(package: dict[str, object], output: Path = OUTPUT) -> dict[str, object]:
    require_protected_boundary(ROOT)
    paths = {
        "evidence_units": output / "evidence" / "evidence_units.csv",
        "evidence_rule_links": output / "evidence" / "evidence_rule_links.csv",
        "expert_review_queue": output / "review" / "expert_review_queue.csv",
        "manifest": output / "audit" / "evidence_inventory.json",
    }
    write_csv(paths["evidence_units"], UNIT_FIELDS, package["evidence_units"])
    write_csv(paths["evidence_rule_links"], LINK_FIELDS, package["evidence_rule_links"])
    write_csv(
        paths["expert_review_queue"], QUEUE_FIELDS, package["expert_review_queue"]
    )

    manifest = dict(package["manifest"])
    manifest["artifacts"] = {
        str(path.relative_to(ROOT)).replace("\\", "/")
        if path.is_relative_to(ROOT)
        else path.name: {
            "rows": len(package[name]),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "fields": fields,
        }
        for name, path, fields in (
            ("evidence_units", paths["evidence_units"], UNIT_FIELDS),
            ("evidence_rule_links", paths["evidence_rule_links"], LINK_FIELDS),
            ("expert_review_queue", paths["expert_review_queue"], QUEUE_FIELDS),
        )
    }
    paths["manifest"].parent.mkdir(parents=True, exist_ok=True)
    paths["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    require_protected_boundary(ROOT)
    return {"paths": paths, "manifest": manifest}


def main() -> int:
    package = build()
    result = write(package)
    print(
        json.dumps(
            {
                "evidence_units": len(package["evidence_units"]),
                "evidence_rule_links": len(package["evidence_rule_links"]),
                "expert_review_queue": len(package["expert_review_queue"]),
                "status_counts": package["manifest"]["counts"]["status_counts"],
                "manifest": str(result["paths"]["manifest"].relative_to(ROOT)),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
