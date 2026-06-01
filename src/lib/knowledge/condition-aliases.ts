type ConditionAliasPreset = {
  displayLabel: string;
  aliases: string[];
};

function normalizeConditionAliasKey(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[_\-\/()]+/g, " ")
    .replace(/[^a-z0-9가-힣\s]+/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

const conditionAliasPresets: Record<string, ConditionAliasPreset> = {
  obesity: {
    displayLabel: "비만",
    aliases: ["비만", "obese"],
  },
  overweight: {
    displayLabel: "과체중",
    aliases: ["과체중"],
  },
  diabetes: {
    displayLabel: "당뇨병",
    aliases: ["당뇨", "당뇨병"],
  },
  prediabetes: {
    displayLabel: "당뇨 전단계",
    aliases: ["당뇨 전단계", "공복혈당장애", "전당뇨"],
  },
  hypertension: {
    displayLabel: "고혈압",
    aliases: ["고혈압"],
  },
  hypotension: {
    displayLabel: "저혈압",
    aliases: ["저혈압"],
  },
  dyslipidemia: {
    displayLabel: "이상지질혈증",
    aliases: ["이상지질혈증", "고지혈증"],
  },
  hyperlipidemia: {
    displayLabel: "고지혈증",
    aliases: ["고지혈증", "이상지질혈증"],
  },
  "fatty liver": {
    displayLabel: "지방간",
    aliases: ["지방간", "지방간 질환"],
  },
  nafld: {
    displayLabel: "비알코올성 지방간",
    aliases: ["비알코올성 지방간", "nafld", "비알콜성 지방간"],
  },
  "chronic liver disease": {
    displayLabel: "만성 간질환",
    aliases: ["간질환", "간 질환", "만성 간질환", "만성간질환"],
  },
  cirrhosis: {
    displayLabel: "간경변",
    aliases: ["간경변", "간경화"],
  },
  hepatitis: {
    displayLabel: "간염",
    aliases: ["간염"],
  },
  "history_of_drug_induced_liver_injury": {
    displayLabel: "약인성 간손상 병력",
    aliases: ["약인성 간손상", "약인성 간손상 병력", "dili", "dili 병력"],
  },
  renal_disorder: {
    displayLabel: "신장 질환",
    aliases: ["신질환", "신장질환", "신장 질환", "신장 문제"],
  },
  kidney_disease: {
    displayLabel: "신장 질환",
    aliases: ["신질환", "신장질환", "신장 질환", "콩팥 질환"],
  },
  chronic_kidney_disease: {
    displayLabel: "만성 신장질환",
    aliases: ["만성 신장질환", "만성신장질환", "ckd"],
  },
  "history_of_kidney_stones": {
    displayLabel: "신장결석 병력",
    aliases: ["신장결석", "신장결석 병력", "신결석", "요로결석 병력"],
  },
  hyperoxaluria: {
    displayLabel: "고옥살산뇨",
    aliases: ["고옥살산뇨"],
  },
  hypercalciuria: {
    displayLabel: "고칼슘뇨",
    aliases: ["고칼슘뇨"],
  },
  bowel_obstruction: {
    displayLabel: "장폐색",
    aliases: ["장폐색"],
  },
  constipation: {
    displayLabel: "변비",
    aliases: ["변비"],
  },
  diarrhea: {
    displayLabel: "설사",
    aliases: ["설사"],
  },
  dysphagia: {
    displayLabel: "연하곤란",
    aliases: ["연하곤란", "삼킴곤란"],
  },
  hypothyroidism: {
    displayLabel: "갑상선기능저하증",
    aliases: ["갑상선기능저하증", "갑상선 저하증", "저하증"],
  },
  hyperthyroidism: {
    displayLabel: "갑상선기능항진증",
    aliases: ["갑상선기능항진증", "갑상선 항진증", "항진증"],
  },
  osteoporosis: {
    displayLabel: "골다공증",
    aliases: ["골다공증"],
  },
  osteopenia: {
    displayLabel: "골감소증",
    aliases: ["골감소증"],
  },
  pre_existing_chronic_liver_disease: {
    displayLabel: "기저 만성 간질환",
    aliases: ["기저 간질환", "기저 만성 간질환"],
  },
  cholestatic_hepatitis: {
    displayLabel: "담즙정체성 간염",
    aliases: ["담즙정체성 간염"],
  },
  acute_on_chronic_liver_failure: {
    displayLabel: "만성 간질환의 급성 악화",
    aliases: ["급성 악화 간부전", "만성 간질환의 급성 악화", "aclf"],
  },
};

export function getConditionAliasPreset(canonicalValue: string) {
  return conditionAliasPresets[normalizeConditionAliasKey(canonicalValue)] ?? null;
}

export function getConditionAliases(canonicalValue: string) {
  const preset = getConditionAliasPreset(canonicalValue);
  return preset?.aliases ?? [];
}

export function getConditionDisplayLabel(canonicalValue: string) {
  const preset = getConditionAliasPreset(canonicalValue);
  return preset?.displayLabel ?? canonicalValue.replace(/_/g, " ").replace(/\s+/g, " ").trim();
}

export function getConditionPresetCanonicalValues() {
  return Object.keys(conditionAliasPresets);
}
