"""Build the frozen v5 PubMed P AND I query definitions.

This file is the human-auditable source for ``query_definitions.json``.  It
does not call PubMed.  Terms in ``blocks.O`` are classification/audit records
only and are never interpolated into a query.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
TARGET = Path(__file__).with_name("query_definitions.json")
PROTOCOL = "research_v3/protocol/protocol-v5.0-mecir-search.md"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def block(classification: str, terms: list[str], *, included: bool, subtype: str) -> dict:
    return {
        "classification": classification,
        "included_in_query": included,
        "subtype": subtype,
        "terms": terms,
    }


def make_question(
    *,
    question_id: str,
    title_ko: str,
    ingredient_ids: list[str],
    rule_types: list[str],
    date_start: str,
    v4_hit_count: int,
    p_terms: list[str],
    i_groups: list[tuple[str, list[str]]],
    i_expression: str,
    o_terms: list[str],
    structure: str,
) -> dict:
    p_expression = f"({' OR '.join(p_terms)})"
    query = (
        f"({p_expression} AND {i_expression}) AND "
        f"(\"{date_start}\"[Date - Publication] : \"3000\"[Date - Publication])"
    )
    i_blocks = [block("I", terms, included=True, subtype=subtype) for subtype, terms in i_groups]
    return {
        "question_id": question_id,
        "title_ko": title_ko,
        "ingredient_ids": ingredient_ids,
        "rule_types": rule_types,
        "date_range": {"start": date_start, "end": "3000"},
        "v4_hit_count": v4_hit_count,
        "block_structure": structure,
        "blocks": {
            "P": [block("P", p_terms, included=True, subtype="population_or_risk_situation")],
            "I": i_blocks,
            "O": [block("O", o_terms, included=False, subtype="outcome_removed")],
        },
        "query": query,
        "query_sha256": sha256_text(query),
    }


def definitions() -> dict:
    q01_p = [
        '"Liver Diseases"[Mesh]', '"Hepatic Insufficiency"[Mesh]',
        '"Alcohol Drinking"[Mesh]', '"Alcoholism"[Mesh]', '"Child"[Mesh]',
        '"Adolescent"[Mesh]', '"Aged"[Mesh]', '"liver disease"[tiab]',
        '"hepatic disease"[tiab]', '"hepatic impairment"[tiab]',
        '"liver impairment"[tiab]', '"chronic liver disease"[tiab]',
        'cirrhosis[tiab]', '"alcohol use"[tiab]', '"alcohol drinking"[tiab]',
        '"alcohol consumption"[tiab]', 'alcoholic*[tiab]', 'pediatric*[tiab]',
        'paediatric*[tiab]', 'child*[tiab]', 'adolescent*[tiab]',
        '"older adult"[tiab]', '"older adults"[tiab]', 'elder*[tiab]',
        'geriatric*[tiab]',
    ]
    q01_i = [
        '"Acetaminophen"[Mesh]', 'acetaminophen[tiab]', 'paracetamol[tiab]',
        'APAP[tiab]', '"N-acetyl-p-aminophenol"[tiab]',
        '"N-acetyl-para-aminophenol"[tiab]',
        '"N-(4-hydroxyphenyl)acetamide"[tiab]', '"4-hydroxyacetanilide"[tiab]',
        '"p-hydroxyacetanilide"[tiab]', '"para-hydroxyacetanilide"[tiab]',
        'acetamidophenol[tiab]', 'acetylaminophenol[tiab]', 'Tylenol[tiab]',
        'Panadol[tiab]', 'Calpol[tiab]', 'Ofirmev[tiab]', 'Perfalgan[tiab]',
        'Datril[tiab]', 'Mapap[tiab]', 'Tempra[tiab]', 'Feverall[tiab]',
        'Acamol[tiab]', 'Crocin[tiab]', 'Paramol[tiab]', 'Tylex[tiab]',
        '"Children\'s Tylenol"[tiab]', '"anilide analgesics"[tiab]',
        'para-aminophenol*[tiab]',
        '("Acetaminophen"[Mesh] AND "Drug Overdose"[Mesh])',
        '(acetaminophen[tiab] AND overdos*[tiab])',
        '(paracetamol[tiab] AND overdos*[tiab])',
        '(APAP[tiab] AND overdos*[tiab])',
        '(acetaminophen[tiab] AND supratherapeutic[tiab])',
        '(paracetamol[tiab] AND supratherapeutic[tiab])',
        '(acetaminophen[tiab] AND (duplicate*[tiab] OR concomitant*[tiab]))',
        '(paracetamol[tiab] AND (duplicate*[tiab] OR concomitant*[tiab]))',
        '(acetaminophen[tiab] AND "dosing interval"[tiab])',
        '(paracetamol[tiab] AND "dosing interval"[tiab])',
        '(acetaminophen[tiab] AND "daily dose"[tiab])',
        '(paracetamol[tiab] AND "daily dose"[tiab])',
        '"high-dose acetaminophen"[tiab]', '"high-dose paracetamol"[tiab]',
    ]

    q02_p = [
        '"Pregnancy"[Mesh]', '"Breast Feeding"[Mesh]',
        '"Renal Insufficiency"[Mesh]', '"Kidney Diseases"[Mesh]',
        '("Peptic Ulcer"[Mesh] AND (histor*[tiab] OR previous[tiab] OR prior[tiab]))',
        '"Anticoagulants"[Mesh]', '"Platelet Aggregation Inhibitors"[Mesh]',
        'pregnan*[tiab]', 'lactat*[tiab]', 'breastfeed*[tiab]',
        '"breast feeding"[tiab]', '"renal disease"[tiab]', '"kidney disease"[tiab]',
        '"renal impairment"[tiab]', '"kidney impairment"[tiab]',
        '"chronic kidney disease"[tiab]', '"peptic ulcer history"[tiab]',
        '(peptic[tiab] AND ulcer*[tiab] AND histor*[tiab])',
        'anticoagulant*[tiab]', 'antiplatelet*[tiab]', 'warfarin[tiab]',
        'coumarin*[tiab]', '"direct oral anticoagulant"[tiab]',
        '"direct oral anticoagulants"[tiab]', 'DOAC[tiab]', 'DOACs[tiab]',
        '"aspirin use"[tiab]',
    ]
    q02_i = [
        '"Ibuprofen"[Mesh]', '"Naproxen"[Mesh]',
        '"Anti-Inflammatory Agents, Non-Steroidal"[Mesh]', 'ibuprofen[tiab]',
        'dexibuprofen[tiab]', '(dexibuprofen[tiab] AND trometamol[tiab])',
        '"S-ibuprofen"[tiab]', '"(S)-ibuprofen"[tiab]',
        '"2-(4-isobutylphenyl)propionic acid"[tiab]', 'naproxen[tiab]',
        '"naproxen sodium"[tiab]', '"S-naproxen"[tiab]', '"(S)-naproxen"[tiab]',
        '"(+)-naproxen"[tiab]',
        '"6-methoxy-alpha-methyl-2-naphthaleneacetic acid"[tiab]',
        'NSAID*[tiab]', '"nonsteroidal anti-inflammatory drug"[tiab]',
        '"nonsteroidal anti-inflammatory drugs"[tiab]',
        '"non-steroidal anti-inflammatory drug"[tiab]',
        '"non-steroidal anti-inflammatory drugs"[tiab]',
        '"propionic acid derivative"[tiab]', '"propionic acid derivatives"[tiab]',
        '"arylpropionic acid derivatives"[tiab]', '"2-arylpropionic acid"[tiab]',
        'Advil[tiab]', 'Motrin[tiab]', 'Nurofen[tiab]', 'Brufen[tiab]',
        'Caldolor[tiab]', 'Ibufen[tiab]', 'Seractil[tiab]', 'Deltaran[tiab]',
        'Aleve[tiab]', 'Naprosyn[tiab]', 'Anaprox[tiab]', 'Flanax[tiab]',
        'Synflex[tiab]', 'Naxen[tiab]', 'Dexpeed[tiab]',
        '(ibuprofen[tiab] AND naproxen[tiab])',
        '(NSAID*[tiab] AND (concomitant*[tiab] OR concurrent*[tiab] OR duplicate*[tiab] OR multiple[tiab]))',
        '(ibuprofen[tiab] AND dexibuprofen[tiab])',
    ]

    q03_p = [
        '"Automobile Driving"[Mesh]', '"Hypertension"[Mesh]',
        '"Hypnotics and Sedatives"[Mesh]',
        '"Central Nervous System Depressants"[Mesh]', 'driver*[tiab]',
        'driving[tiab]', '"motor vehicle operator"[tiab]',
        '"motor vehicle operators"[tiab]', '"machine operator"[tiab]',
        '"machine operators"[tiab]', '"operating machinery"[tiab]',
        'hypertens*[tiab]', '"high blood pressure"[tiab]',
        '"sedative medication"[tiab]', '"sedative medications"[tiab]',
        '"hypnotic use"[tiab]', '"benzodiazepine use"[tiab]',
        '"CNS depressant use"[tiab]', '"tranquilizer use"[tiab]',
        '"tranquillizer use"[tiab]', '"opioid use"[tiab]',
    ]
    q03_i = [
        '"Chlorpheniramine"[Mesh]', '"Cetirizine"[Mesh]',
        '"Phenylephrine"[Mesh]', '"Caffeine"[Mesh]',
        '"Carbetapentane"[Supplementary Concept]', '"Expectorants"[Mesh]',
        '"Nasal Decongestants"[Mesh]', '"Antitussive Agents"[Mesh]',
        '"Xanthines"[Mesh]', 'chlorpheniramine[tiab]', 'chlorphenamine[tiab]',
        '"chlorpheniramine maleate"[tiab]', '"chlorphenamine maleate"[tiab]',
        '(CPM[tiab] AND antihistamine*[tiab])',
        '(CTM[tiab] AND antihistamine*[tiab])', 'Piriton[tiab]',
        '"Chlor-Trimeton"[tiab]', 'cetirizine[tiab]',
        '"cetirizine hydrochloride"[tiab]', 'Zyrtec[tiab]', 'Reactine[tiab]',
        'phenylephrine[tiab]', 'phenylephrin*[tiab]',
        '"phenylephrine hydrochloride"[tiab]', '"phenylephrine HCl"[tiab]',
        'metaoxedrin[tiab]', 'metasympatol[tiab]', 'metasynephrine[tiab]',
        '"meta-synephrine"[tiab]', '"m-synephrine"[tiab]',
        '"Neo-Synephrine"[tiab]', 'neosynephrine[tiab]', 'Mezaton[tiab]',
        'pentoxyverine[tiab]', 'pentoxyverin*[tiab]', 'pentoxiverin*[tiab]',
        'carbetapentane[tiab]', 'carbetapentan*[tiab]',
        '"pentoxyverine citrate"[tiab]', '"carbetapentane citrate"[tiab]',
        'Toclase[tiab]', 'guaifenes*[tiab]', 'guaiphenes*[tiab]',
        'guaiphenezine[tiab]', '"glycerol guaiacolate"[tiab]',
        '"glyceryl guaiacolate"[tiab]', '"guaiacol glyceryl ether"[tiab]',
        '"glyceryl guaiacolate ether"[tiab]', 'Mucinex[tiab]', 'Humibid[tiab]',
        '"Scott-Tussin"[tiab]',
        '(GGE[tiab] AND (guaifenesin[tiab] OR "glyceryl guaiacolate"[tiab]))',
        'caffein*[tiab]', '"anhydrous caffeine"[tiab]',
        '"caffeine anhydrous"[tiab]', '"1,3,7-trimethylxanthine"[tiab]',
        'trimethylxanthin*[tiab]', 'methyltheobromine[tiab]', 'guaranine[tiab]',
        'theine[tiab]', 'thein[tiab]', 'coffein*[tiab]', 'Coffeinum[tiab]',
        'NoDoz[tiab]', 'Vivarin[tiab]',
        '(CAF[tiab] AND (caffeine[tiab] OR "anhydrous caffeine"[tiab]))',
        'antihistamine*[tiab]', '"H1 receptor antagonists"[tiab]',
        '"first-generation antihistamines"[tiab]',
        '"second-generation antihistamines"[tiab]', 'decongestant*[tiab]',
        'sympathomimetic*[tiab]', 'antitussiv*[tiab]', 'expectorant*[tiab]',
        'methylxanthin*[tiab]', '"cold medicine"[tiab]', '"cold medicines"[tiab]',
        'pancold*[tiab]', 'Panpyrin*[tiab]',
    ]

    q04_p = [
        '"Dyspepsia"[Mesh]', '"Exocrine Pancreatic Insufficiency"[Mesh]',
        '"Digestive System Diseases"[Mesh]', '"Malabsorption Syndromes"[Mesh]',
        '"Cystic Fibrosis"[Mesh]', '"Pancreatitis, Chronic"[Mesh]',
        '"Cholestasis"[Mesh]', '"Liver Cirrhosis, Biliary"[Mesh]',
        '"Flatulence"[Mesh]', '"Colic"[Mesh]', 'dyspepsia[tiab]',
        'indigestion[tiab]', 'maldigestion[tiab]', '"pancreatic insufficiency"[tiab]',
        '"exocrine pancreatic insufficiency"[tiab]', 'EPI[tiab]',
        '"digestive disorder"[tiab]', '"digestive disorders"[tiab]',
        '"gastrointestinal disorder"[tiab]', '"gastrointestinal disorders"[tiab]',
        '"digestive symptom"[tiab]', '"digestive symptoms"[tiab]',
        'malabsorption[tiab]', '"chronic pancreatitis"[tiab]',
        '"cystic fibrosis"[tiab]', 'postgastrectom*[tiab]',
        '"primary biliary cholangitis"[tiab]', '"primary biliary cirrhosis"[tiab]',
        'PBC[tiab]', 'cholestasis[tiab]', '"biliary disease"[tiab]',
        '"biliary diseases"[tiab]', 'gallstone*[tiab]', 'cholelithiasis[tiab]',
        'flatulence[tiab]', 'bloating[tiab]', '"infantile colic"[tiab]',
    ]
    q04_direct = [
        '"Pancreatin"[Mesh]', '"Pancrelipase"[Mesh]', '"Simethicone"[Mesh]',
        '"Ursodeoxycholic Acid"[Mesh]', '"Bromelains"[Mesh]', 'pancreatin[tiab]',
        'pancrelipase[tiab]', 'pancrealipase[tiab]', '"pancreatic extract"[tiab]',
        '"pancreatic extracts"[tiab]', '"pancreas extract"[tiab]',
        '"pancreatic enzyme"[tiab]', '"pancreatic enzymes"[tiab]',
        '"pancreatic enzyme preparation"[tiab]',
        '"pancreatic enzyme preparations"[tiab]',
        '"pancreatic enzyme replacement therapy"[tiab]', 'PERT[tiab]',
        '"enteric-coated pancreatin"[tiab]', '"enteric coated pancreatin"[tiab]',
        'Creon[tiab]', 'Zenpep[tiab]', 'Pancreaze[tiab]', 'Pertzye[tiab]',
        'Ultresa[tiab]', 'Panzytrat[tiab]', 'bromelain*[tiab]', 'bromelin*[tiab]',
        'ananase[tiab]', '"pineapple enzyme"[tiab]', '"pineapple protease"[tiab]',
        '"stem bromelain"[tiab]', '"fruit bromelain"[tiab]', 'simethicone[tiab]',
        'simeticone[tiab]', '"activated dimeticone"[tiab]',
        '"activated dimethicone"[tiab]', '"Antifoam A"[tiab]', 'Phazyme[tiab]',
        'Disflatyl[tiab]', 'ursodeoxycholic[tiab]', '"ursodeoxycholic acid"[tiab]',
        '"ursodesoxycholic acid"[tiab]', 'ursodiol[tiab]', 'UDCA[tiab]',
        'ursodeoxychol*[tiab]', 'ursodesoxychol*[tiab]',
        'ursodeoxycholate*[tiab]', '"sodium ursodeoxycholate"[tiab]',
        '"ursacholic acid"[tiab]', 'Actigall[tiab]', 'Ursofalk[tiab]',
        'Destolit[tiab]', 'Delursan[tiab]', 'Pancellase[tiab]', 'Panprosin[tiab]',
        '"Crease-PEG"[tiab]', '"Crease PEG"[tiab]', '"Prozyme 6"[tiab]',
        '"Prozyme-6"[tiab]', 'oryzin[tiab]', '"Biodiastase 2000"[tiab]',
        '"Biodiastase 2000 III"[tiab]', '"Dizet 100"[tiab]',
        '"Cellulase AP3"[tiab]', '"Lipase II"[tiab]', 'Bearse[tiab]',
        '"Doctor Bearse"[tiab]', '"Festal Gold"[tiab]', '"Festal Plus"[tiab]',
    ]
    q04_enzyme = [
        '"Amylases"[Mesh]', '"Peptide Hydrolases"[Mesh]', '"Cellulase"[Mesh]',
        '"Cellulases"[Mesh]', '"Lipase"[Mesh]', 'diastase[tiab]',
        '"fungal diastase"[tiab]', '"taka-diastase"[tiab]', 'amylase*[tiab]',
        'protease*[tiab]', 'proteinase*[tiab]', 'peptidase*[tiab]',
        'cellulase*[tiab]', 'endoglucanase*[tiab]',
        '"endo-1,4-beta-D-glucanase"[tiab]', '"fungal cellulase"[tiab]',
        'lipase*[tiab]', '"triacylglycerol lipase"[tiab]',
        '"triglyceride lipase"[tiab]', '"Aspergillus melleus protease"[tiab]',
        '"Aspergillus alkaline proteinase"[tiab]',
        '"diastase protease cellulase"[tiab]',
        '"diastase-protease-cellulase"[tiab]', '"diastase protease 100"[tiab]',
        '"diastase-protease 100"[tiab]',
    ]
    q04_form = [
        '"Administration, Oral"[Mesh]', 'oral[tiab]', 'orally[tiab]',
        'tablet*[tiab]', 'capsule*[tiab]', 'granule*[tiab]', 'supplement*[tiab]',
        'preparation*[tiab]', 'therap*[tiab]', 'replacement[tiab]', 'enteric*[tiab]',
        '"digestive enzyme"[tiab]', '"digestive enzymes"[tiab]',
        '"drug interaction"[tiab]', '"drug interactions"[tiab]',
    ]
    q04_i_expression = (
        f"({' OR '.join(q04_direct)} OR "
        f"(({' OR '.join(q04_enzyme)}) AND ({' OR '.join(q04_form)})))"
    )

    q05_p = [
        '"Child"[Mesh]', '"Infant"[Mesh]', '"Adolescent"[Mesh]',
        '"Anticoagulants"[Mesh]', '"Platelet Aggregation Inhibitors"[Mesh]',
        'child*[tiab]', 'pediatric*[tiab]', 'paediatric*[tiab]', 'infant*[tiab]',
        'toddler*[tiab]', 'adolescent*[tiab]', 'anticoagulant*[tiab]',
        'antiplatelet*[tiab]', 'warfarin[tiab]', 'coumarin*[tiab]',
        '"direct oral anticoagulant"[tiab]', '"direct oral anticoagulants"[tiab]',
        'DOAC[tiab]', 'DOACs[tiab]', '"aspirin use"[tiab]',
    ]
    q05_names = [
        '"Methyl Salicylate"[Supplementary Concept]', '"Menthol"[Mesh]',
        '"Camphor"[Mesh]', '"Thymol"[Mesh]',
        '("Mentha"[Mesh:noexp] AND ("Plant Oils"[Mesh] OR "Oils, Volatile"[Mesh]))',
        '"Salicylates"[Mesh]',
        '"methyl salicylate"[tiab]', '"methyl salicylat*"[tiab]',
        'methylsalicylat*[tiab]',
        '"oil of wintergreen"[tiab]', '"wintergreen oil"[tiab]',
        '"methyl 2-hydroxybenzoate"[tiab]',
        '"2-hydroxybenzoic acid methyl ester"[tiab]',
        '"salicylic acid methyl ester"[tiab]', '"methyl o-hydroxybenzoate"[tiab]',
        '"gaultheria oil"[tiab]', '"sweet birch oil"[tiab]',
        'menthol*[tiab]', 'levomenthol[tiab]', 'levomentholum[tiab]',
        '"L-menthol"[tiab]',
        '"(-)-menthol"[tiab]', '"l menthol"[tiab]',
        '"2-isopropyl-5-methylcyclohexanol"[tiab]', '"menthyl alcohol"[tiab]',
        '"p-menthan-3-ol"[tiab]', 'hexahydrothymol[tiab]',
        '"peppermint camphor"[tiab]', 'camphor*[tiab]',
        '"dl-camphor"[tiab]', '"DL camphor"[tiab]', '"racemic camphor"[tiab]',
        '"synthetic camphor"[tiab]',
        '"bornan-2-one"[tiab]', '"2-bornanone"[tiab]',
        '"1,7,7-trimethylbicyclo[2.2.1]heptan-2-one"[tiab]',
        '"2-camphanone"[tiab]', '"gum camphor"[tiab]', 'camphora[tiab]',
        '"Mentha oil"[tiab]', '"Mentha arvensis oil"[tiab]',
        '"Mentha arvensis leaf oil"[tiab]', '"Mentha arvensis flower oil"[tiab]',
        '"Mentha arvensis essential oil"[tiab]', '"Mentha canadensis oil"[tiab]',
        'cornmint[tiab]', '"corn mint oil"[tiab]', '"Japanese mint oil"[tiab]',
        '"field mint oil"[tiab]', '"wild mint oil"[tiab]',
        '"Oleum Menthae Japonicae"[tiab]',
        '"partly dementholised mint oil"[tiab]',
        '"partly dementholized mint oil"[tiab]', 'thymol[tiab]', 'thymolum[tiab]',
        '"5-methyl-2-(propan-2-yl)phenol"[tiab]',
        '"5-methyl-2-(1-methylethyl)phenol"[tiab]',
        '"2-isopropyl-5-methylphenol"[tiab]', '"6-isopropyl-m-cresol"[tiab]',
        '"3-p-cymenol"[tiab]', '"p-cymen-3-ol"[tiab]',
        '"3-hydroxy-p-cymene"[tiab]', '"thymic acid"[tiab]',
        '"thyme camphor"[tiab]',
        '"Jeil Cool Pap"[tiab]', '"Cool Pap Cataplasma"[tiab]',
        'Salonpas[tiab]', '"Tiger Balm"[tiab]',
        '"Vicks VapoRub"[tiab]', 'counterirritant*[tiab]',
    ]
    q05_form = [
        '"Administration, Topical"[Mesh]', '"Administration, Cutaneous"[Mesh]',
        '"Transdermal Patch"[Mesh]', 'topical*[tiab]', 'dermal*[tiab]',
        'cutaneous[tiab]', 'transdermal*[tiab]', 'patch*[tiab]', 'plaster*[tiab]',
        'poultice*[tiab]', 'cataplasm*[tiab]', 'liniment*[tiab]',
        'ointment*[tiab]', 'balm*[tiab]', 'cream*[tiab]', 'gel*[tiab]',
        'overdos*[tiab]', 'overuse[tiab]', '"excessive use"[tiab]',
        '"repeated use"[tiab]', '"repeated application"[tiab]',
    ]
    q05_i_expression = f"(({' OR '.join(q05_names)}) AND ({' OR '.join(q05_form)}))"

    questions = [
        make_question(
            question_id="OTC-LIT-Q01-ACETAMINOPHEN",
            title_ko="아세트아미노펜 용량·간격·간질환·음주 관련 위해",
            ingredient_ids=["ING-acetaminophen"],
            rule_types=["duplicate_ingredient", "max_daily_dose", "minimum_interval", "age_restriction", "hepatic_disease", "alcohol", "urgent_referral"],
            date_start="2010/01/01", v4_hit_count=2709, p_terms=q01_p,
            i_groups=[("ingredient_name_brand_class_and_exposure", q01_i)],
            i_expression=f"({' OR '.join(q01_i)})",
            o_terms=['hepatotox*[tiab]', '"liver injury"[tiab]', 'toxicity[tiab]', '"adverse reaction"[tiab]', 'death*[tiab]'],
            structure="P AND I; overdose, duplicate dosing, dose and interval remain inside I",
        ),
        make_question(
            question_id="OTC-LIT-Q02-NSAID", title_ko="이부프로펜·덱시부프로펜·나프록센의 중복과 주요 위해",
            ingredient_ids=["ING-dexibuprofen", "ING-ibuprofen", "ING-naproxen"],
            rule_types=["duplicate_pharmacologic_class", "pregnancy_lactation", "renal_disease", "gi_bleeding_ulcer", "anticoagulant_antiplatelet"],
            date_start="2010/01/01", v4_hit_count=683, p_terms=q02_p,
            i_groups=[("ingredient_name_brand_class_and_coexposure", q02_i)],
            i_expression=f"({' OR '.join(q02_i)})",
            o_terms=['"Gastrointestinal Hemorrhage"[Mesh]', 'bleed*[tiab]', 'hemorrhag*[tiab]', 'haemorrhag*[tiab]', 'toxicity[tiab]', '"adverse reaction"[tiab]', 'death*[tiab]'],
            structure="P AND I; pregnancy, lactation, kidney disease, ulcer history and anticoagulant use are P",
        ),
        make_question(
            question_id="OTC-LIT-Q03-COLD-ALLERGY", title_ko="감기·알레르기 복합성분의 진정·운전·혈압·병용 위해",
            ingredient_ids=["ING-cetirizine_hydrochloride", "ING-chlorpheniramine_maleate", "ING-mf-src-41c782105274", "ING-mf-src-4b985f9d3bdb", "ING-mf-src-cd3363b1ac1f", "ING-mf-src-dc293e7de142"],
            rule_types=["sedation_driving", "sedative_medication", "decongestant_hypertension", "maximum_duration"],
            date_start="2010/01/01", v4_hit_count=1533, p_terms=q03_p,
            i_groups=[("ingredient_name_brand_class_and_combination", q03_i)],
            i_expression=f"({' OR '.join(q03_i)})",
            o_terms=['sedat*[tiab]', 'drows*[tiab]', 'somnolen*[tiab]', 'psychomotor[tiab]', 'cardiovascular[tiab]', '"adverse reaction"[tiab]', 'death*[tiab]'],
            structure="P AND I; driving, hypertension and concomitant sedative-medication use are P",
        ),
        make_question(
            question_id="OTC-LIT-Q04-DIGESTIVE", title_ko="소화효소·담즙산·가스제거 성분 복합 사용의 안전성",
            ingredient_ids=["ING-mf-src-0546ff64775e", "ING-mf-src-06cdde4eaaee", "ING-mf-src-484bf5816144", "ING-mf-src-5abce34aadf5", "ING-mf-src-7ace07a0f45d", "ING-mf-src-7ae387262216", "ING-mf-src-8f38da8a73d0", "ING-mf-src-a5c9920bea02", "ING-mf-src-a742c02533bc", "ING-mf-src-d33c06bc01c8", "ING-mf-src-d75c9c1aefc3", "ING-mf-src-db4cde0b063f", "ING-mf-src-ea4c014f0616"],
            rule_types=["duplicate_ingredient", "maximum_duration"],
            date_start="2000/01/01", v4_hit_count=104, p_terms=q04_p,
            i_groups=[("direct_ingredient_name_brand_and_class", q04_direct), ("enzyme_name_or_class", q04_enzyme), ("administration_form_or_combination_exposure", q04_form)],
            i_expression=q04_i_expression,
            o_terms=['"Drug-Related Side Effects and Adverse Reactions"[Mesh]', '"adverse effect"[tiab]', '"adverse effects"[tiab]', 'safety[Title]', 'allergy[tiab]', 'bleeding[tiab]', 'toxicity[tiab]', 'death*[tiab]'],
            structure="P AND I; broad enzyme class terms are paired with administration/form/exposure terms inside I",
        ),
        make_question(
            question_id="OTC-LIT-Q05-TOPICAL", title_ko="살리실산메틸·멘톨·캄파 등 외용 복합성분의 위해",
            ingredient_ids=["ING-mf-src-25b653f7fbe2", "ING-mf-src-4a3225f1eb5d", "ING-mf-src-76b6b5a5a31f", "ING-mf-src-8bebf0ac75f4", "ING-mf-src-e2b868294a4f"],
            rule_types=["age_restriction", "anticoagulant_antiplatelet", "urgent_referral"],
            date_start="2000/01/01", v4_hit_count=713, p_terms=q05_p,
            i_groups=[("ingredient_name_brand_and_class", q05_names), ("topical_form_and_excess_exposure", q05_form)],
            i_expression=q05_i_expression,
            o_terms=['poison*[tiab]', 'toxic*[tiab]', 'adverse[tiab]', 'bleed*[tiab]', 'hemorrhag*[tiab]', 'haemorrhag*[tiab]', 'death*[tiab]'],
            structure="P AND I; ingredient names are paired with topical form or excess/repeated exposure inside I",
        ),
    ]

    selected = []
    for question in questions:
        selected.extend(question["ingredient_ids"])
    if len(selected) != 28 or len(set(selected)) != 28:
        raise ValueError(f"expected 28 unique selected ingredients, got {len(selected)}/{len(set(selected))}")
    for question in questions:
        i_terms = [term for group in question["blocks"]["I"] for term in group["terms"]]
        if len(set(i_terms)) < 25:
            raise ValueError(f"{question['question_id']}: fewer than 25 distinct I terms")
        query_lower = question["query"].lower()
        forbidden = ["humans[mesh]", "clinical trial[pt]", "english[lang]", "review[pt]"]
        present = [value for value in forbidden if value in query_lower]
        if present:
            raise ValueError(f"{question['question_id']}: forbidden query fragments {present}")

    return {
        "schema_version": "5.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_path": PROTOCOL,
        "database": "PubMed",
        "query_authority": "final query strings in this file",
        "selected_ingredient_count": 28,
        "selected_ingredient_ids": selected,
        "ingredient_mapping_path": "research_v3/otc/literature/v5/ingredient_mappings.json",
        "questions": questions,
    }


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(definitions(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(TARGET.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
