"""P3-B 무라벨 사례 생성기.

식약처 허가원문에서 정규화한 13개 분석 제품·성분·함량·복용 조건만으로 규칙 유형 16개의
사례를 만든다. **정답 라벨과 엔진 예측을 만들지 않는다.** 사례 파일에는 판정에 쓰일 수 있는
어떤 라벨 필드도 넣지 않는다.

규칙 유형별로 발동 조건을 설정한 사례와 설정하지 않은 사례를 같은 수로 만들어 특이도를
측정할 수 있게 한다. 어떤 사례가 어느 쪽인지는 파일에도 매니페스트에도 기록하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED = ROOT / "research_v3" / "otc" / "normalized"
RULES_CSV = ROOT / "research_v3" / "otc" / "rules" / "rules.csv"
OUT_DIR = ROOT / "research_v3" / "otc" / "validation" / "ai_independent_cases"
MANIFEST = OUT_DIR / "case_manifest.json"

SCHEMA_VERSION = "1.0.0"

# 실제 허가 품목 일련번호 (분석 대상 13개)
TYLENOL500 = "202106092"
TYLENOL_SUSP = "202200525"
PANCOL_A = "196800036"
PANPYRIN_T = "199400202"
DEXPID = "201110646"
NAXEN = "197500016"
BRUFEN_SYRUP = "198601920"
ZYRTEC = "200610765"
BEARSE = "198700405"
DR_BEARSE = "200300406"
FESTAL_GOLD = "199900926"
FESTAL_PLUS = "199801026"
COOL_PARP = "198400250"

DEFAULT_PROFILE: dict[str, Any] = {
    "ageYears": None,
    "pregnant": False,
    "lactating": False,
    "liverDisease": False,
    "kidneyDisease": False,
    "giBleedingOrUlcer": False,
    "hypertensionOrCardiovascularDisease": False,
    "willDrive": False,
    "alcohol": False,
    "medications": [],
    "redFlagSymptoms": [],
}

RULE_TYPE_DEFINITION_KO = {
    "duplicate_ingredient": "같은 유효성분이 둘 이상의 제품에 중복되어 총량이 늘어나는 상황",
    "duplicate_pharmacologic_class": "같은 약효 계열(예: NSAID) 성분을 둘 이상 함께 복용하는 상황",
    "max_daily_dose": "계산한 하루 총 성분량이 허가된 1일 최대량을 넘는 상황",
    "minimum_interval": "허가된 최소 복용 간격이 지나기 전에 다시 복용하는 상황",
    "age_restriction": "입력한 연령이 해당 제품의 허가 연령 기준에 맞지 않는 상황",
    "pregnancy_lactation": "임신 또는 수유 중 주의가 필요한 성분을 복용하는 상황",
    "hepatic_disease": "간질환이 있는 사람이 간독성 주의 성분을 복용하는 상황",
    "renal_disease": "신장질환이 있는 사람이 신독성 주의 성분을 복용하는 상황",
    "gi_bleeding_ulcer": "위장관 출혈·궤양 병력이 있는 사람이 위장관 위험 성분을 복용하는 상황",
    "sedation_driving": "졸림을 유발할 수 있는 성분을 복용하고 운전·기계 조작을 하는 상황",
    "alcohol": "음주와 함께 복용할 때 주의가 필요한 성분을 복용하는 상황",
    "anticoagulant_antiplatelet": "항응고제·항혈소판제를 복용 중인 사람이 출혈 위험 성분을 함께 쓰는 상황",
    "sedative_medication": "진정 작용이 있는 다른 약과 겹쳐 복용하는 상황",
    "decongestant_hypertension": "고혈압·심혈관질환이 있는 사람이 비충혈제거 성분을 복용하는 상황",
    "maximum_duration": "허가된 연속 복용 기간을 넘겨 계속 복용하는 상황",
    "urgent_referral": "즉시 상담·진료가 필요한 중대 이상 증상이 입력된 상황",
}


def _p(seq: str, units: float = 1, doses: int = 3, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "inputType": "verified_product",
        "itemSequence": seq,
        "unitsPerDose": units,
        "dosesPerDay": doses,
    }
    row.update(extra)
    return row


def _profile(**overrides: Any) -> dict[str, Any]:
    profile = json.loads(json.dumps(DEFAULT_PROFILE))
    profile.update(overrides)
    return profile


# --------------------------------------------------------------------------
# 규칙 유형별 사례 설계 (발동 예상 7건 + 미발동 예상 7건)
# 미발동 쪽은 두 가지 방식으로 만든다. (1) 사용자 조건을 끄거나 수량을 상한 이내로 두는 것,
# (2) 조건은 그대로 두고 해당 주의가 허가원문에 없는 제품으로 바꾸는 것. 어느 쪽인지는
# 사례 파일에도 매니페스트에도 표시하지 않는다. 설계 의도는 정답이 아니며 참조표준은
# 허가원문을 보고 독립적으로 판정한다.
# --------------------------------------------------------------------------
def build_specs() -> list[tuple[str, list[dict[str, Any]], dict[str, Any]]]:
    """(rule_type, productInputs, userProfile) 목록을 결정론적으로 만든다."""
    specs: list[tuple[str, list[dict[str, Any]], dict[str, Any]]] = []

    def add(rule_type: str, products: list[dict[str, Any]], profile: dict[str, Any]) -> None:
        specs.append((rule_type, products, profile))

    # 1. duplicate_ingredient
    for pair in [
        [_p(TYLENOL500, 1, 3), _p(PANCOL_A, 1, 3)],
        [_p(TYLENOL500, 1, 3), _p(PANPYRIN_T, 1, 3)],
        [_p(PANCOL_A, 1, 3), _p(PANPYRIN_T, 1, 3)],
        [_p(TYLENOL500, 1, 2), _p(TYLENOL_SUSP, 10, 3)],
        [_p(TYLENOL_SUSP, 10, 3), _p(PANCOL_A, 1, 3)],
        [_p(TYLENOL_SUSP, 10, 3), _p(PANPYRIN_T, 1, 3)],
        [_p(TYLENOL500, 1, 2), _p(PANCOL_A, 1, 2), _p(PANPYRIN_T, 1, 2)],
    ]:
        add("duplicate_ingredient", pair, _profile(ageYears=30))
    for combo in [
        [_p(TYLENOL500, 1, 3)],
        [_p(PANCOL_A, 1, 3)],
        [_p(TYLENOL500, 1, 3), _p(DEXPID, 1, 3)],
        [_p(TYLENOL500, 1, 3), _p(ZYRTEC, 1, 1)],
        [_p(PANPYRIN_T, 1, 3), _p(BEARSE, 1, 3)],
        [_p(NAXEN, 1, 2), _p(ZYRTEC, 1, 1)],
        [_p(TYLENOL500, 1, 3), _p(COOL_PARP, 1, 2)],
    ]:
        add("duplicate_ingredient", combo, _profile(ageYears=30))

    # 2. duplicate_pharmacologic_class
    for combo in [
        [_p(DEXPID, 1, 3), _p(NAXEN, 1, 2)],
        [_p(DEXPID, 1, 3), _p(BRUFEN_SYRUP, 10, 3)],
        [_p(NAXEN, 1, 2), _p(BRUFEN_SYRUP, 10, 3)],
        [_p(DEXPID, 1, 2), _p(NAXEN, 1, 2), _p(BRUFEN_SYRUP, 10, 2)],
        [_p(NAXEN, 2, 2), _p(BRUFEN_SYRUP, 15, 3)],
        [_p(DEXPID, 1, 4), _p(BRUFEN_SYRUP, 20, 3)],
        [_p(NAXEN, 1, 3), _p(DEXPID, 1, 2)],
    ]:
        add("duplicate_pharmacologic_class", combo, _profile(ageYears=35))
    for combo in [
        [_p(DEXPID, 1, 3)],
        [_p(NAXEN, 1, 2)],
        [_p(BRUFEN_SYRUP, 10, 3)],
        [_p(DEXPID, 1, 3), _p(TYLENOL500, 1, 3)],
        [_p(NAXEN, 1, 2), _p(ZYRTEC, 1, 1)],
        [_p(BRUFEN_SYRUP, 10, 3), _p(BEARSE, 1, 3)],
        [_p(TYLENOL500, 1, 3), _p(FESTAL_GOLD, 1, 3)],
    ]:
        add("duplicate_pharmacologic_class", combo, _profile(ageYears=35))

    # 3. max_daily_dose (타이레놀정500 기준 1일 4,000 mg)
    for combo in [
        [_p(TYLENOL500, 2, 5)],
        [_p(TYLENOL500, 3, 4)],
        [_p(TYLENOL500, 2, 6)],
        [_p(TYLENOL500, 3, 3)],
        [_p(TYLENOL500, 4, 3)],
        [_p(TYLENOL500, 2, 4), _p(PANCOL_A, 1, 3)],
        [_p(TYLENOL500, 2, 4), _p(PANPYRIN_T, 1, 3)],
    ]:
        add("max_daily_dose", combo, _profile(ageYears=30))
    for combo in [
        [_p(TYLENOL500, 2, 4)],
        [_p(TYLENOL500, 1, 4)],
        [_p(TYLENOL500, 2, 3)],
        [_p(TYLENOL500, 1, 3)],
        [_p(TYLENOL500, 2, 2)],
        [_p(TYLENOL500, 1, 2)],
        [_p(PANCOL_A, 1, 3)],
    ]:
        add("max_daily_dose", combo, _profile(ageYears=30))

    # 4. minimum_interval (타이레놀정500 최소 4시간)
    for hours in [1, 2, 3, 2, 1, 3, 2]:
        add(
            "minimum_interval",
            [_p(TYLENOL500, 1, 3, hoursSincePreviousDose=hours)],
            _profile(ageYears=30),
        )
    for hours in [4, 5, 6, 8, 4, 12, 24]:
        add(
            "minimum_interval",
            [_p(TYLENOL500, 1, 3, hoursSincePreviousDose=hours)],
            _profile(ageYears=30),
        )

    # 5. age_restriction (타이레놀정500 12세 이상)
    for age in [5, 8, 10, 11, 6, 9, 7]:
        add("age_restriction", [_p(TYLENOL500, 1, 3)], _profile(ageYears=age))
    for age in [12, 15, 20, 35, 60, 13, 45]:
        add("age_restriction", [_p(TYLENOL500, 1, 3)], _profile(ageYears=age))

    # 6. pregnancy_lactation
    for products, profile in [
        ([_p(BRUFEN_SYRUP, 10, 3)], _profile(ageYears=29, pregnant=True)),
        ([_p(DEXPID, 1, 3)], _profile(ageYears=31, pregnant=True)),
        ([_p(NAXEN, 1, 2)], _profile(ageYears=27, pregnant=True)),
        ([_p(BRUFEN_SYRUP, 10, 3)], _profile(ageYears=30, lactating=True)),
        ([_p(DEXPID, 1, 3)], _profile(ageYears=33, lactating=True)),
        ([_p(NAXEN, 1, 2)], _profile(ageYears=28, lactating=True)),
        ([_p(DEXPID, 1, 3), _p(NAXEN, 1, 2)], _profile(ageYears=32, pregnant=True)),
    ]:
        add("pregnancy_lactation", products, profile)
    for products, profile in [
        ([_p(BRUFEN_SYRUP, 10, 3)], _profile(ageYears=29)),
        ([_p(DEXPID, 1, 3)], _profile(ageYears=31)),
        ([_p(NAXEN, 1, 2)], _profile(ageYears=27)),
        ([_p(BEARSE, 1, 3)], _profile(ageYears=30, pregnant=True)),
        ([_p(COOL_PARP, 1, 2)], _profile(ageYears=33, pregnant=True)),
        ([_p(FESTAL_PLUS, 1, 3)], _profile(ageYears=28, lactating=True)),
        ([_p(DR_BEARSE, 1, 3)], _profile(ageYears=32, pregnant=True)),
    ]:
        add("pregnancy_lactation", products, profile)

    # 7. hepatic_disease
    for products in [
        [_p(TYLENOL500, 1, 3)],
        [_p(PANCOL_A, 1, 3)],
        [_p(PANPYRIN_T, 1, 3)],
        [_p(TYLENOL_SUSP, 10, 3)],
        [_p(TYLENOL500, 2, 4)],
        [_p(PANPYRIN_T, 1, 3), _p(PANCOL_A, 1, 3)],
        [_p(TYLENOL500, 1, 3), _p(DEXPID, 1, 3)],
    ]:
        add("hepatic_disease", products, _profile(ageYears=48, liverDisease=True))
    for products, profile in [
        ([_p(TYLENOL500, 1, 3)], _profile(ageYears=48)),
        ([_p(PANCOL_A, 1, 3)], _profile(ageYears=40)),
        ([_p(PANPYRIN_T, 1, 3)], _profile(ageYears=52)),
        ([_p(ZYRTEC, 1, 1)], _profile(ageYears=48, liverDisease=True)),
        ([_p(COOL_PARP, 1, 2)], _profile(ageYears=50, liverDisease=True)),
        ([_p(BEARSE, 1, 3)], _profile(ageYears=45, liverDisease=True)),
        ([_p(FESTAL_GOLD, 1, 3)], _profile(ageYears=55, liverDisease=True)),
    ]:
        add("hepatic_disease", products, profile)

    # 8. renal_disease
    for products in [
        [_p(DEXPID, 1, 3)],
        [_p(NAXEN, 1, 2)],
        [_p(BRUFEN_SYRUP, 10, 3)],
        [_p(DEXPID, 1, 3), _p(NAXEN, 1, 2)],
        [_p(NAXEN, 2, 2)],
        [_p(BRUFEN_SYRUP, 20, 3)],
        [_p(DEXPID, 1, 4)],
    ]:
        add("renal_disease", products, _profile(ageYears=63, kidneyDisease=True))
    for products, profile in [
        ([_p(DEXPID, 1, 3)], _profile(ageYears=63)),
        ([_p(NAXEN, 1, 2)], _profile(ageYears=58)),
        ([_p(BRUFEN_SYRUP, 10, 3)], _profile(ageYears=41)),
        ([_p(ZYRTEC, 1, 1)], _profile(ageYears=63, kidneyDisease=True)),
        ([_p(BEARSE, 1, 3)], _profile(ageYears=60, kidneyDisease=True)),
        ([_p(COOL_PARP, 1, 2)], _profile(ageYears=57, kidneyDisease=True)),
        ([_p(FESTAL_PLUS, 1, 3)], _profile(ageYears=66, kidneyDisease=True)),
    ]:
        add("renal_disease", products, profile)

    # 9. gi_bleeding_ulcer
    for products in [
        [_p(DEXPID, 1, 3)],
        [_p(NAXEN, 1, 2)],
        [_p(BRUFEN_SYRUP, 10, 3)],
        [_p(NAXEN, 2, 2)],
        [_p(DEXPID, 1, 4)],
        [_p(DEXPID, 1, 3), _p(NAXEN, 1, 2)],
        [_p(BRUFEN_SYRUP, 15, 3)],
    ]:
        add("gi_bleeding_ulcer", products, _profile(ageYears=55, giBleedingOrUlcer=True))
    for products, profile in [
        ([_p(DEXPID, 1, 3)], _profile(ageYears=55)),
        ([_p(NAXEN, 1, 2)], _profile(ageYears=44)),
        ([_p(BRUFEN_SYRUP, 10, 3)], _profile(ageYears=38)),
        ([_p(TYLENOL500, 1, 3)], _profile(ageYears=55, giBleedingOrUlcer=True)),
        ([_p(ZYRTEC, 1, 1)], _profile(ageYears=50, giBleedingOrUlcer=True)),
        ([_p(COOL_PARP, 1, 2)], _profile(ageYears=47, giBleedingOrUlcer=True)),
        ([_p(FESTAL_GOLD, 1, 3)], _profile(ageYears=61, giBleedingOrUlcer=True)),
    ]:
        add("gi_bleeding_ulcer", products, profile)

    # 10. sedation_driving
    for products in [
        [_p(PANCOL_A, 1, 3)],
        [_p(PANPYRIN_T, 1, 3)],
        [_p(ZYRTEC, 1, 1)],
        [_p(PANCOL_A, 1, 3), _p(TYLENOL500, 1, 3)],
        [_p(PANPYRIN_T, 1, 3), _p(NAXEN, 1, 2)],
        [_p(PANCOL_A, 1, 3), _p(ZYRTEC, 1, 1)],
        [_p(PANPYRIN_T, 1, 2)],
    ]:
        add("sedation_driving", products, _profile(ageYears=34, willDrive=True))
    for products, profile in [
        ([_p(PANCOL_A, 1, 3)], _profile(ageYears=34)),
        ([_p(PANPYRIN_T, 1, 3)], _profile(ageYears=29)),
        ([_p(PANCOL_A, 1, 2)], _profile(ageYears=42)),
        ([_p(TYLENOL500, 1, 3)], _profile(ageYears=34, willDrive=True)),
        ([_p(NAXEN, 1, 2)], _profile(ageYears=36, willDrive=True)),
        ([_p(BEARSE, 1, 3)], _profile(ageYears=39, willDrive=True)),
        ([_p(COOL_PARP, 1, 2)], _profile(ageYears=31, willDrive=True)),
    ]:
        add("sedation_driving", products, profile)

    # 11. alcohol
    for products in [
        [_p(TYLENOL500, 1, 3)],
        [_p(PANCOL_A, 1, 3)],
        [_p(PANPYRIN_T, 1, 3)],
        [_p(TYLENOL500, 2, 3)],
        [_p(TYLENOL_SUSP, 10, 3)],
        [_p(TYLENOL500, 1, 3), _p(PANCOL_A, 1, 3)],
        [_p(PANPYRIN_T, 1, 2)],
    ]:
        add("alcohol", products, _profile(ageYears=44, alcohol=True))
    for products, profile in [
        ([_p(TYLENOL500, 1, 3)], _profile(ageYears=44)),
        ([_p(PANCOL_A, 1, 3)], _profile(ageYears=37)),
        ([_p(PANPYRIN_T, 1, 3)], _profile(ageYears=51)),
        ([_p(BEARSE, 1, 3)], _profile(ageYears=44, alcohol=True)),
        ([_p(COOL_PARP, 1, 2)], _profile(ageYears=46, alcohol=True)),
        ([_p(ZYRTEC, 1, 1)], _profile(ageYears=40, alcohol=True)),
        ([_p(FESTAL_PLUS, 1, 3)], _profile(ageYears=49, alcohol=True)),
    ]:
        add("alcohol", products, profile)

    # 12. anticoagulant_antiplatelet
    for products, meds in [
        ([_p(DEXPID, 1, 3)], ["와파린"]),
        ([_p(NAXEN, 1, 2)], ["와파린"]),
        ([_p(BRUFEN_SYRUP, 10, 3)], ["와파린"]),
        ([_p(DEXPID, 1, 3)], ["쿠마딘"]),
        ([_p(NAXEN, 2, 2)], ["와파린"]),
        ([_p(DEXPID, 1, 3), _p(NAXEN, 1, 2)], ["와파린"]),
        ([_p(BRUFEN_SYRUP, 15, 3)], ["쿠마딘"]),
    ]:
        add("anticoagulant_antiplatelet", products, _profile(ageYears=67, medications=meds))
    for products, meds in [
        ([_p(DEXPID, 1, 3)], []),
        ([_p(NAXEN, 1, 2)], []),
        ([_p(BRUFEN_SYRUP, 10, 3)], []),
        ([_p(BEARSE, 1, 3)], ["와파린"]),
        ([_p(ZYRTEC, 1, 1)], ["와파린"]),
        ([_p(FESTAL_GOLD, 1, 3)], ["와파린"]),
        ([_p(TYLENOL500, 1, 3)], []),
    ]:
        add("anticoagulant_antiplatelet", products, _profile(ageYears=67, medications=meds))

    # 13. sedative_medication
    for products, meds in [
        ([_p(PANCOL_A, 1, 3)], ["졸피뎀"]),
        ([_p(PANPYRIN_T, 1, 3)], ["졸피뎀"]),
        ([_p(PANCOL_A, 1, 3)], ["디아제팜"]),
        ([_p(PANPYRIN_T, 1, 3)], ["디아제팜"]),
        ([_p(PANCOL_A, 1, 3)], ["다른 종합감기약"]),
        ([_p(PANCOL_A, 1, 2), _p(PANPYRIN_T, 1, 2)], ["졸피뎀"]),
        ([_p(ZYRTEC, 1, 1)], ["졸피뎀"]),
    ]:
        add("sedative_medication", products, _profile(ageYears=41, medications=meds))
    for products, meds in [
        ([_p(PANCOL_A, 1, 3)], []),
        ([_p(PANPYRIN_T, 1, 3)], []),
        ([_p(PANCOL_A, 1, 2)], []),
        ([_p(BEARSE, 1, 3)], ["졸피뎀"]),
        ([_p(TYLENOL500, 1, 3)], ["졸피뎀"]),
        ([_p(COOL_PARP, 1, 2)], ["디아제팜"]),
        ([_p(FESTAL_PLUS, 1, 3)], ["졸피뎀"]),
    ]:
        add("sedative_medication", products, _profile(ageYears=41, medications=meds))

    # 14. decongestant_hypertension
    for products in [
        [_p(PANCOL_A, 1, 3)],
        [_p(PANCOL_A, 1, 2)],
        [_p(PANCOL_A, 1, 3), _p(TYLENOL500, 1, 3)],
        [_p(PANCOL_A, 1, 3), _p(ZYRTEC, 1, 1)],
        [_p(PANCOL_A, 1, 3), _p(BEARSE, 1, 3)],
        [_p(PANCOL_A, 1, 1)],
        [_p(PANCOL_A, 1, 3), _p(COOL_PARP, 1, 2)],
    ]:
        add(
            "decongestant_hypertension",
            products,
            _profile(ageYears=59, hypertensionOrCardiovascularDisease=True),
        )
    for products, profile in [
        ([_p(PANCOL_A, 1, 3)], _profile(ageYears=59)),
        ([_p(PANCOL_A, 1, 2)], _profile(ageYears=45)),
        ([_p(PANCOL_A, 1, 3)], _profile(ageYears=33)),
        (
            [_p(PANPYRIN_T, 1, 3)],
            _profile(ageYears=59, hypertensionOrCardiovascularDisease=True),
        ),
        (
            [_p(TYLENOL500, 1, 3)],
            _profile(ageYears=62, hypertensionOrCardiovascularDisease=True),
        ),
        ([_p(BEARSE, 1, 3)], _profile(ageYears=57, hypertensionOrCardiovascularDisease=True)),
        ([_p(ZYRTEC, 1, 1)], _profile(ageYears=54, hypertensionOrCardiovascularDisease=True)),
    ]:
        add("decongestant_hypertension", products, profile)

    # 15. maximum_duration
    for days in [5, 7, 10, 14, 6, 8, 30]:
        add(
            "maximum_duration",
            [_p(PANCOL_A, 1, 3, continuousDays=days)],
            _profile(ageYears=36),
        )
    for days in [1, 2, 3, 1, 2, 3, 1]:
        add(
            "maximum_duration",
            [_p(PANCOL_A, 1, 3, continuousDays=days)],
            _profile(ageYears=36),
        )

    # 16. urgent_referral
    for symptom in [
        "호흡곤란",
        "두드러기",
        "얼굴부기",
        "쇽",
        "천식발작",
        "스티븐스-존슨",
        "혈관부기",
    ]:
        add(
            "urgent_referral",
            [_p(TYLENOL500, 1, 3)],
            _profile(ageYears=38, redFlagSymptoms=[symptom]),
        )
    for symptoms in [[], [], [], ["가벼운 두통"], ["콧물"], ["기침"], ["속쓰림"]]:
        add(
            "urgent_referral",
            [_p(TYLENOL500, 1, 3)],
            _profile(ageYears=38, redFlagSymptoms=symptoms),
        )

    return specs


# --------------------------------------------------------------------------
def load_products() -> dict[str, dict[str, Any]]:
    master = {
        row["item_sequence"]: row
        for row in csv.DictReader(
            (NORMALIZED / "product_master.csv").open(encoding="utf-8-sig")
        )
        if row["calculation_ready"] == "true"
    }
    ingredients: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in csv.DictReader(
        (NORMALIZED / "product_ingredient.csv").open(encoding="utf-8-sig")
    ):
        if row["selected_for_calculation"] != "true":
            continue
        ingredients[row["product_id"]].append(row)
    constraints: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in csv.DictReader(
        (NORMALIZED / "administration_constraints.csv").open(encoding="utf-8-sig")
    ):
        constraints[row["item_sequence"]].append(row)

    products: dict[str, dict[str, Any]] = {}
    for seq, row in master.items():
        products[seq] = {
            "itemSequence": seq,
            "productName": row["product_name"],
            "ingredients": [
                {
                    "ingredientId": item["ingredient_id"],
                    "nameKo": item["ingredient_name_normalized"],
                    "amountPerUnit": item["amount_per_unit"],
                    "unit": item["amount_unit"],
                    "unitBasis": item["unit_basis"],
                }
                for item in ingredients[row["product_id"]]
            ],
            "administrationConstraints": [
                {
                    "type": item["constraint_type"],
                    "value": item["value"],
                    "valueUnit": item["value_unit"],
                    "ingredientId": item["ingredient_id"],
                }
                for item in constraints[seq]
            ],
        }
    return products


def cmd_build(_: argparse.Namespace) -> int:
    products = load_products()
    rule_types = [
        row["rule_type"]
        for row in csv.DictReader(RULES_CSV.open(encoding="utf-8-sig"))
    ]
    specs = build_specs()

    unknown = {rt for rt, _, _ in specs} - set(rule_types)
    if unknown:
        raise SystemExit(f"unknown rule types in specs: {sorted(unknown)}")
    missing = set(rule_types) - {rt for rt, _, _ in specs}
    if missing:
        raise SystemExit(f"rule types without cases: {sorted(missing)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("AIC-OTC-*.json"):
        old.unlink()

    per_type: dict[str, int] = defaultdict(int)
    written: list[dict[str, Any]] = []
    for index, (rule_type, product_inputs, profile) in enumerate(specs, start=1):
        for item in product_inputs:
            if item["itemSequence"] not in products:
                raise SystemExit(f"product not in analysis set: {item['itemSequence']}")
        case_id = f"AIC-OTC-{index:03d}"
        payload = {
            "caseId": case_id,
            "schemaVersion": SCHEMA_VERSION,
            "targetRuleType": rule_type,
            "productInputs": product_inputs,
            "userProfile": profile,
        }
        path = OUT_DIR / f"{case_id}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        per_type[rule_type] += 1
        written.append(
            {
                "case_id": case_id,
                "target_rule_type": rule_type,
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose_ko": "P3-B 규칙엔진 AI 맹검 독립평가용 무라벨 사례",
        "generator": "tools/ai_independent_cases.py",
        "label_fields_present": False,
        "prediction_fields_present": False,
        "note_ko": (
            "사례 파일에는 정답 라벨과 엔진 예측을 넣지 않는다. 규칙 유형별로 발동 조건을 "
            "설정한 사례와 설정하지 않은 사례를 같은 수로 만들었으나 어느 쪽인지는 "
            "사례 파일과 매니페스트 어디에도 표시하지 않는다."
        ),
        "source_files": {
            name: hashlib.sha256((NORMALIZED / name).read_bytes()).hexdigest()
            for name in (
                "product_master.csv",
                "product_ingredient.csv",
                "administration_constraints.csv",
            )
        },
        "rules_csv_sha256": hashlib.sha256(RULES_CSV.read_bytes()).hexdigest(),
        "analysis_products": sorted(products),
        "excluded_product_ko": "신신파스아렉스(200501321)는 분석·런타임에서 제외한다.",
        "rule_types": rule_types,
        "cases_total": len(written),
        "cases_per_rule_type": dict(sorted(per_type.items())),
        "cases": written,
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"cases={len(written)} rule_types={len(per_type)} min_per_type={min(per_type.values())}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P3-B unlabeled case builder")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build").set_defaults(func=cmd_build)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
