import json
from pathlib import Path

from scripts.research.otc.build_metrics import build, write
from scripts.research.otc.audit_claim_consistency import audit as audit_claim_consistency


ROOT = Path(__file__).resolve().parents[2]


def test_active_metrics_exclude_superseded_nutrient_counts() -> None:
    manifest = build()
    serialized = json.dumps(manifest, ensure_ascii=False)
    assert manifest["research_direction"] == "korean_otc_product_safety"
    assert manifest["prior_direction"] == {"status": "superseded", "metrics_included": False}
    assert "unique_pmids" not in serialized
    assert "high_dose_nutrient" not in serialized
    assert manifest["metrics"]["official_designation_candidates"]["value"] == 13
    assert manifest["metrics"]["rules_released"]["value"] == 15
    assert manifest["metrics"]["released_source_locator_rate"]["value"] == 1.0
    assert manifest["release_ready"] is False


def test_written_root_and_otc_manifests_match(tmp_path: Path) -> None:
    manifest = build()
    write(manifest)
    root_manifest = json.loads((ROOT / "research_v3" / "metrics_manifest.json").read_text(encoding="utf-8"))
    otc_manifest = json.loads((ROOT / "research_v3" / "otc" / "metrics_manifest.json").read_text(encoding="utf-8"))
    assert root_manifest == otc_manifest
    assert root_manifest["metrics"]["products_verified_from_source"]["value"] == 14
    assert root_manifest["metrics"]["products_calculation_ready"]["value"] == 13
    assert root_manifest["metrics"]["analysis_products"]["value"] == 13
    assert root_manifest["metrics"]["analysis_ingredients"]["value"] == 28
    assert root_manifest["metrics"]["analysis_product_ingredient_variant_rows"]["value"] == 57
    assert root_manifest["metrics"]["runtime_product_ingredient_bindings"]["value"] == 47
    assert root_manifest["metrics"]["verified_administration_constraints"]["value"] == 32
    assert root_manifest["metrics"]["analysis_exclusions"]["value"] == 1
    assert root_manifest["metrics"]["runtime_research_alignment"]["value"] is True
    assert root_manifest["metrics"]["runtime_official_candidates"]["value"] == 2
    assert root_manifest["metrics"]["independent_scenarios"]["status"] == "evaluated_codex_prefilled_external_human_confirmation"
    assert root_manifest["metrics"]["independent_scenarios"]["performance_claim_allowed"] is False
    assert root_manifest["metrics"]["ingredient_normalization_accuracy"]["status"] == "evaluated_human_locked_reference"
    assert root_manifest["metrics"]["analysis_ingredient_normalization_accuracy"]["numerator"] == 28
    assert root_manifest["metrics"]["analysis_ingredient_normalization_accuracy"]["denominator"] == 28
    assert len(root_manifest["data_limitations"]) == 1


def test_documents_use_site_aligned_counts_and_claim_boundary() -> None:
    result = audit_claim_consistency()
    assert result["valid"] is True
    assert result["errors"] == []
