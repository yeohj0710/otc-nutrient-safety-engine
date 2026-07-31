from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
V51_APPLICABILITY = ROOT / "research_v51" / "evidence" / "active_rule_applicability.csv"

CLASS_NAMES = {
    "OTC-CLASS-ANALGESIC": "해열진통제",
    "OTC-CLASS-COLD": "종합감기약",
    "OTC-CLASS-GI": "위장관 일반의약품",
    "OTC-CLASS-TOPICAL": "외용 소염진통제",
    "OTC-CLASS-ANTIHISTAMINE": "항히스타민제",
}

ADMINISTRATION_CONSTRAINT_TYPES = {
    "maximum_units_per_dose",
    "maximum_doses_per_day",
    "maximum_daily_ingredient_amount",
    "minimum_interval_hours",
}

CONSTRAINT_RULE_TYPES = {
    "maximum_units_per_dose": "max_daily_dose",
    "maximum_doses_per_day": "max_daily_dose",
    "maximum_daily_ingredient_amount": "max_daily_dose",
    "minimum_interval_hours": "minimum_interval",
}

DOCUMENT_LABELS = {
    "EE": "효능효과",
    "UD": "용법용량",
    "NB": "사용상의주의사항",
}


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical_text_sha256(path: Path) -> str:
    canonical = (
        path.read_text(encoding="utf-8-sig")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_source_documents() -> dict[tuple[str, str], dict]:
    manifest_rows = rows(OTC / "extracted" / "nedrug" / "page_manifest.csv")
    documents: dict[tuple[str, str], dict] = {}
    verified_paths: dict[str, str] = {}
    for row in manifest_rows:
        key = (row["item_sequence"], row["document_type"])
        expected = {
            "pdfSha256": row["pdf_sha256"],
            "pdfPath": row["pdf_path"],
            "documentLabel": row["document_label"],
        }
        document = documents.setdefault(key, {**expected, "pages": set()})
        if any(document[field] != value for field, value in expected.items()):
            raise ValueError(f"MFDS source manifest is inconsistent: {key}")
        page = int(row["page"])
        if page in document["pages"]:
            raise ValueError(f"MFDS source manifest has a duplicate page: {key} p.{page}")
        document["pages"].add(page)

        if row["pdf_path"] not in verified_paths:
            actual_hash = file_sha256(ROOT / row["pdf_path"])
            verified_paths[row["pdf_path"]] = actual_hash
        if verified_paths[row["pdf_path"]] != row["pdf_sha256"]:
            raise ValueError(f"MFDS source PDF hash mismatch: {row['pdf_path']}")
    return documents


def evidence_source_version(
    evidence: dict[str, str], documents: dict[tuple[str, str], dict]
) -> str:
    parsed_url = urlparse(evidence["source_url"])
    path_match = re.fullmatch(
        r"/dsie/pdf/drb/([^/]+)/(EE|UD|NB)", parsed_url.path
    )
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc != "nedrug.mfds.go.kr"
        or parsed_url.params
        or parsed_url.query
        or parsed_url.fragment
        or path_match is None
    ):
        raise ValueError(f"invalid MFDS evidence URL: {evidence['source_url']}")
    url_item_sequence, document_type = path_match.groups()
    if url_item_sequence != evidence["item_sequence"]:
        raise ValueError(
            f"MFDS evidence URL item mismatch: {evidence.get('rule_id', evidence['item_sequence'])}"
        )
    document = documents.get((url_item_sequence, document_type))
    if document is None:
        raise ValueError(
            f"MFDS evidence source is absent from protected manifest: {evidence.get('rule_id', evidence['item_sequence'])}"
        )
    if document_type not in DOCUMENT_LABELS or document["documentLabel"] != DOCUMENT_LABELS[document_type]:
        raise ValueError(f"MFDS evidence document type mismatch: {document_type}")
    page_match = re.search(r" PDF p\.(\d+)(?:,|$)", evidence["source_locator"])
    if (
        not evidence["source_locator"].startswith(f"{document['documentLabel']} PDF p.")
        or page_match is None
        or int(page_match.group(1)) not in document["pages"]
    ):
        raise ValueError(
            f"MFDS evidence locator is outside protected manifest: {evidence.get('rule_id', evidence['item_sequence'])}"
        )
    return f"sha256:{document['pdfSha256']}"


def values(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def build_applicability(row: dict[str, str]) -> dict:
    applicability: dict[str, object] = {}
    list_fields = {
        "product_item_sequences": "productItemSequences",
        "ingredient_ids": "ingredientIds",
        "pharmacologic_classes": "pharmacologicClasses",
        "required_anchor_ingredient_ids": "requiredAnchorIngredientIds",
        "administration_constraint_types": "administrationConstraintTypes",
        "medication_terms": "medicationTerms",
        "urgent_terms": "urgentTerms",
    }
    for csv_name, runtime_name in list_fields.items():
        parsed = values(row[csv_name])
        if parsed:
            if csv_name == "administration_constraint_types" and any(
                value not in ADMINISTRATION_CONSTRAINT_TYPES for value in parsed
            ):
                raise ValueError(f"invalid administration constraint type: {row['rule_id']}")
            applicability[runtime_name] = parsed
    trimesters = values(row["pregnancy_trimesters"])
    if trimesters:
        parsed_trimesters = [int(value) for value in trimesters]
        if any(value not in {1, 2, 3} for value in parsed_trimesters):
            raise ValueError(f"invalid pregnancy trimester: {row['rule_id']}")
        applicability["pregnancyTrimesters"] = parsed_trimesters
    if row["minimum_age_years"]:
        minimum_age = float(row["minimum_age_years"])
        if minimum_age < 0:
            raise ValueError(f"invalid minimum age: {row['rule_id']}")
        applicability["minimumAgeYears"] = (
            int(minimum_age) if minimum_age.is_integer() else minimum_age
        )
    if row["lactation_supported"]:
        if row["lactation_supported"] not in {"true", "false"}:
            raise ValueError(f"invalid lactation flag: {row['rule_id']}")
        applicability["lactationSupported"] = row["lactation_supported"] == "true"
    return applicability


def validate_active_rule_applicability(
    policies: list[dict], products: list[dict]
) -> None:
    products_by_item = {product["itemSequence"]: product for product in products}
    known_ingredients = {
        ingredient["ingredientId"]
        for product in products
        for ingredient in product["ingredients"]
    }
    known_classes = {
        group
        for product in products
        for ingredient in product["ingredients"]
        for group in ingredient["pharmacologicClasses"]
    }

    for policy in policies:
        applicability = policy["applicability"]
        item_sequences = set(applicability.get("productItemSequences", []))
        ingredient_ids = set(applicability.get("ingredientIds", []))
        class_ids = set(applicability.get("pharmacologicClasses", []))
        anchor_ids = set(applicability.get("requiredAnchorIngredientIds", []))

        unknown_items = item_sequences - products_by_item.keys()
        if unknown_items:
            raise ValueError(
                f"active applicability has unknown product items: {policy['ruleId']}"
            )
        if ingredient_ids - known_ingredients:
            raise ValueError(
                f"active applicability has unknown ingredients: {policy['ruleId']}"
            )
        if anchor_ids - known_ingredients:
            raise ValueError(
                f"active applicability has unknown anchors: {policy['ruleId']}"
            )
        if class_ids - known_classes:
            raise ValueError(
                f"active applicability has unknown classes: {policy['ruleId']}"
            )

        for item_sequence in item_sequences:
            product = products_by_item[item_sequence]
            product_ingredients = {
                ingredient["ingredientId"] for ingredient in product["ingredients"]
            }
            product_classes = {
                group
                for ingredient in product["ingredients"]
                for group in ingredient["pharmacologicClasses"]
            }
            product_constraint_types = {
                constraint["type"]
                for constraint in product["administrationConstraints"]
            }
            if ingredient_ids and not ingredient_ids.issubset(product_ingredients):
                raise ValueError(
                    f"active applicability ingredient is outside product scope: {policy['ruleId']}"
                )
            if class_ids and not class_ids.issubset(product_classes):
                raise ValueError(
                    f"active applicability class is outside product scope: {policy['ruleId']}"
                )
            if anchor_ids and not anchor_ids.issubset(product_ingredients):
                raise ValueError(
                    f"active applicability anchor is outside product scope: {policy['ruleId']}"
                )
            constraint_types = set(
                applicability.get("administrationConstraintTypes", [])
            )
            if constraint_types and not constraint_types.issubset(
                product_constraint_types
            ):
                raise ValueError(
                    f"active applicability constraint is outside product scope: {policy['ruleId']}"
                )
            if (
                applicability.get("minimumAgeYears") is not None
                and product.get("minimumAgeYears")
                != applicability["minimumAgeYears"]
            ):
                raise ValueError(
                    f"active applicability age is inconsistent with product scope: {policy['ruleId']}"
                )


def runtime_amount(join: dict[str, str]) -> tuple[float, str, str]:
    amount = float(join["amount_per_unit"])
    unit = join["amount_unit"]
    basis = join["unit_basis"].replace(" ", "")
    if "100mL" in basis or "100밀리리터" in basis:
        if unit == "g":
            return amount * 1000 / 100, "mg", "mL"
        if unit == "mg":
            return amount / 100, "mg", "mL"
    if "1병" in basis:
        return amount, unit, "병"
    if "1매" in basis:
        return amount, unit, "매"
    if "1캡슐" in basis:
        return amount, unit, "캡슐"
    return amount, unit, "정"


def build() -> dict:
    products = rows(OTC / "normalized" / "product_master.csv")
    ingredients = {row["ingredient_id"]: row for row in rows(OTC / "normalized" / "ingredient_master.csv")}
    joins = rows(OTC / "normalized" / "product_ingredient.csv")
    candidate_rows = rows(OTC / "selection" / "official_designation_candidates.csv")
    candidate_rows += rows(OTC / "selection" / "rule_coverage_candidates.csv")
    candidates = {row["candidate_id"]: row for row in candidate_rows}
    rules = rows(OTC / "rules" / "rules.csv")
    catalog_summary = json.loads(
        (OTC / "selection" / "catalog_health_kr_summary.json").read_text(encoding="utf-8")
    )
    catalog_match_rows = rows(
        OTC / "selection" / "catalog_health_kr_existing_product_matches.csv"
    )
    if catalog_summary["runtime_promotion_allowed_count"] != 0:
        raise ValueError("health.kr candidates cannot be promoted without MFDS evidence")
    released_rules = [rule for rule in rules if rule["status"] == "released"]
    released_rule_ids = {rule["rule_id"] for rule in released_rules}
    rule_types_by_id = {rule["rule_id"]: rule["rule_type"] for rule in released_rules}
    primary_evidence_rows = [
        row for row in rows(OTC / "rules" / "rule_evidence_shortlist.csv")
        if row["rule_id"] in released_rule_ids
        and row["recommendation"] == "recommended_primary"
        and row["review_status"] == "human_expert_verified"
        and row["supports_release"] == "true"
    ]
    primary_evidence_by_rule = {row["rule_id"]: row for row in primary_evidence_rows}
    if set(primary_evidence_by_rule) != released_rule_ids:
        raise ValueError("every released rule must have one human-verified primary evidence row")
    if len(primary_evidence_rows) != len(primary_evidence_by_rule):
        raise ValueError("released rule has duplicate primary evidence rows")
    source_documents = verified_source_documents()
    applicability_rows = rows(V51_APPLICABILITY)
    applicability_by_rule = {row["rule_id"]: row for row in applicability_rows}
    if len(applicability_rows) != len(applicability_by_rule):
        raise ValueError("active applicability has duplicate rule IDs")
    if set(applicability_by_rule) != released_rule_ids:
        raise ValueError("active applicability must map exactly the released v5.0 rules")

    released_rule_policies = []
    rule_evidence_by_type: dict[str, list[dict]] = {}
    for rule in released_rules:
        applicability_row = applicability_by_rule[rule["rule_id"]]
        if applicability_row["rule_type"] != rule["rule_type"]:
            raise ValueError(f"active applicability type mismatch: {rule['rule_id']}")
        if applicability_row["scope"] != rule["scope"]:
            raise ValueError(f"active applicability scope mismatch: {rule['rule_id']}")
        if applicability_row["lineage_status"] != "mapped_from_v50_released_rule":
            raise ValueError(f"active applicability has unapproved lineage: {rule['rule_id']}")
        applicability = build_applicability(applicability_row)
        primary = primary_evidence_by_rule[rule["rule_id"]]
        evidence = {
            "ruleId": rule["rule_id"],
            "productName": primary["product_name"],
            "itemSequence": primary["item_sequence"],
            "sourceId": primary["source_id"],
            "sourceVersion": evidence_source_version(primary, source_documents),
            "locator": primary["source_locator"],
            "url": primary["source_url"],
            "excerptKo": primary["evidence_text"],
        }
        policy = {
            "ruleId": rule["rule_id"],
            "ruleType": rule["rule_type"],
            "scope": applicability_row["scope"],
            "lineageStatus": applicability_row["lineage_status"],
            "applicability": applicability,
            "evidence": [evidence],
        }
        released_rule_policies.append(policy)
        rule_evidence_by_type.setdefault(rule["rule_type"], []).append({
            **evidence,
            "ruleType": rule["rule_type"],
            "scope": applicability_row["scope"],
            "lineageStatus": applicability_row["lineage_status"],
            "applicability": applicability,
        })
    bindings = [
        row for row in rows(OTC / "rules" / "runtime_rule_bindings.csv")
        if row["rule_id"] in released_rule_ids and row["supports_release"] == "true"
    ]
    bindings_by_item: dict[str, list[dict[str, str]]] = {}
    for binding in bindings:
        bindings_by_item.setdefault(binding["item_sequence"], []).append(binding)

    dosage_pdf_hashes = {
        row["item_sequence"]: row["pdf_sha256"]
        for row in rows(OTC / "extracted" / "nedrug" / "page_manifest.csv")
        if row["document_type"] == "UD" and row["page"] == "1"
    }
    constraint_rows = [
        row for row in rows(OTC / "normalized" / "administration_constraints.csv")
        if row["record_status"] == "verified_from_authorization_source"
    ]
    constraints_by_item: dict[str, list[dict[str, str]]] = {}
    for row in constraint_rows:
        if row["constraint_type"] not in ADMINISTRATION_CONSTRAINT_TYPES:
            raise ValueError(f"unsupported administration constraint: {row['constraint_type']}")
        if float(row["value"]) <= 0:
            raise ValueError(f"administration constraint must be positive: {row['constraint_id']}")
        if dosage_pdf_hashes.get(row["item_sequence"]) != row["source_sha256"]:
            raise ValueError(f"administration constraint source hash mismatch: {row['constraint_id']}")
        constraints_by_item.setdefault(row["item_sequence"], []).append(row)

    by_product: dict[str, list[dict[str, str]]] = {}
    for join in joins:
        if join["selected_for_calculation"] == "true":
            by_product.setdefault(join["product_id"], []).append(join)

    runtime_products = []
    unresolved = []
    for product in products:
        candidate = candidates[product["candidate_id"]]
        class_name = CLASS_NAMES.get(candidate["class_id"], candidate["class_id"])
        if product.get("analysis_status") == "excluded":
            continue
        if product["record_status"] != "verified_from_source":
            unresolved.append({
                "candidateId": product["candidate_id"], "productName": product["product_name"],
                "className": class_name, "status": "withdrawn",
            })
            continue
        if product["calculation_ready"] != "true":
            unresolved.append({
                "candidateId": product["candidate_id"], "productName": product["product_name"],
                "className": class_name, "status": "package_variant_unresolved",
            })
            continue
        product_ingredients = []
        product_bindings = bindings_by_item.get(product["item_sequence"], [])
        product_constraints = constraints_by_item.get(product["item_sequence"], [])
        product_flags = sorted({flag for binding in product_bindings for flag in binding["flags"].split(";") if flag})
        dose_unit_label = "정"
        for join in by_product.get(product["product_id"], []):
            ingredient = ingredients[join["ingredient_id"]]
            amount, amount_unit, dose_unit_label = runtime_amount(join)
            ingredient_bindings = [binding for binding in product_bindings if binding["ingredient_id"] == join["ingredient_id"]]
            ingredient_row = {
                "ingredientId": join["ingredient_id"], "nameKo": join["ingredient_name_normalized"],
                "amountPerUnit": amount, "unit": amount_unit,
                "pharmacologicClasses": [value for value in ingredient["pharmacologic_classes"].split(";") if value and value != "unclassified"],
                "flags": sorted({flag for binding in ingredient_bindings for flag in binding["flags"].split(";") if flag}),
                "evidence": {
                    "sourceId": product["source_id"], "locator": join["source_locator"],
                    "url": product["authorization_document_url"],
                },
            }
            max_daily = [float(binding["max_daily_amount"]) for binding in ingredient_bindings if binding["max_daily_amount"]]
            intervals = [float(binding["minimum_interval_hours"]) for binding in ingredient_bindings if binding["minimum_interval_hours"]]
            if max_daily:
                ingredient_row["maxDailyAmount"] = min(max_daily)
            if intervals:
                ingredient_row["minimumIntervalHours"] = max(intervals)
            product_ingredients.append(ingredient_row)
        product_ingredient_ids = {row["ingredientId"] for row in product_ingredients}
        for constraint in product_constraints:
            if constraint["ingredient_id"] and constraint["ingredient_id"] not in product_ingredient_ids:
                raise ValueError(f"constraint ingredient is not in product: {constraint['constraint_id']}")
        supported_released_rule_ids = {
            binding["rule_id"]
            for binding in product_bindings
            if binding["rule_id"] in rule_types_by_id
        }
        supported_rule_types = {
            rule_types_by_id[rule_id] for rule_id in supported_released_rule_ids
        }
        supported_rule_types.update(
            CONSTRAINT_RULE_TYPES[constraint["constraint_type"]]
            for constraint in product_constraints
        )
        runtime_product = {
            "productId": product["product_id"], "itemSequence": product["item_sequence"],
            "productName": product["product_name"], "classification": "일반의약품",
            "authorizationStatus": "active", "therapeuticClass": class_name,
            "doseUnitLabel": dose_unit_label,
            "ingredients": product_ingredients, "flags": product_flags,
            "supportedRuleTypes": sorted(supported_rule_types),
            "supportedReleasedRuleIds": sorted(supported_released_rule_ids),
            "administrationConstraints": [
                {
                    "constraintId": constraint["constraint_id"],
                    "type": constraint["constraint_type"],
                    "value": float(constraint["value"]),
                    "valueUnit": constraint["value_unit"],
                    **({"ingredientId": constraint["ingredient_id"]} if constraint["ingredient_id"] else {}),
                    "derivationMethod": constraint["derivation_method"],
                    "evidence": {
                        "sourceId": constraint["source_id"],
                        "sourceVersion": f"sha256:{constraint['source_sha256']}",
                        "locator": constraint["source_locator"],
                        "url": constraint["source_url"],
                    },
                }
                for constraint in product_constraints
            ],
            "evidence": {
                "sourceId": product["source_id"], "locator": product["source_locator"],
                "url": product["authorization_document_url"],
            },
        }
        minimum_ages = [float(binding["minimum_age_years"]) for binding in product_bindings if binding["minimum_age_years"]]
        maximum_days = [float(binding["maximum_continuous_days"]) for binding in product_bindings if binding["maximum_continuous_days"]]
        if minimum_ages:
            runtime_product["minimumAgeYears"] = max(minimum_ages)
        if maximum_days:
            runtime_product["maximumContinuousDays"] = min(maximum_days)
        runtime_products.append(runtime_product)
    validate_active_rule_applicability(released_rule_policies, runtime_products)
    return {
        "schemaVersion": "2.1.0", "generatedAt": date.today().isoformat(),
        "researchDirection": "korean_otc_product_safety", "releaseReady": False,
        "rulesReleased": len(released_rules), "releasedRuleTypes": [rule["rule_type"] for rule in released_rules],
        "authorizationConstraintsCount": sum(
            len(product["administrationConstraints"]) for product in runtime_products
        ),
        "releasedRules": released_rule_policies,
        "ruleApplicabilityProvenance": {
            "path": V51_APPLICABILITY.relative_to(ROOT).as_posix(),
            "sha256": canonical_text_sha256(V51_APPLICABILITY),
            "normalization": "utf8_lf",
            "lineageStatus": "mapped_from_v50_released_rule",
        },
        "ruleEvidenceByType": rule_evidence_by_type,
        "catalogCoverage": {
            "sourceSkuCount": catalog_summary["source_record_count"],
            "healthKrConfirmedCount": catalog_summary["confirmed_count"],
            "healthKrConfirmedUniqueProductCount": catalog_summary["confirmed_unique_official_product_count"],
            "runtimePromotionAllowedCount": catalog_summary["runtime_promotion_allowed_count"],
            "classificationCounts": catalog_summary["classification_counts"],
            "existingProductRematch": catalog_summary[
                "existing_research_product_rematch"
            ],
        },
        "catalogExistingMatches": [
            {
                "itemSequence": row["mfds_item_sequence"],
                "matchStatus": row["match_status"],
                "officialItemName": row["official_item_name"],
                "officialManufacturer": row["official_manufacturer"],
                "officialDosageForm": row["official_dosage_form"],
                "retailDisplayLinks": row["retail_display_links"],
                "sourceUrl": row["official_source_url"],
                "mfdsPromotionEvidenceComplete": False,
            }
            for row in catalog_match_rows
            if row["in_runtime"] == "true" and row["match_status"] in {"success", "conflict"}
        ],
        "urgentReferralBindings": [
            {"itemSequence": binding["item_sequence"], "terms": [term for term in binding.get("red_flag_terms", "").split(";") if term]}
            for binding in bindings if binding.get("red_flag_terms")
        ],
        "products": runtime_products,
        "officialCandidates": unresolved,
    }


def main() -> int:
    runtime = build()
    target = ROOT / "src" / "generated" / "otc-runtime.json"
    target.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"products={len(runtime['products'])} unresolved={len(runtime['officialCandidates'])} released_rules={runtime['rulesReleased']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
