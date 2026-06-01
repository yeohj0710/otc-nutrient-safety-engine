type MedicationAliasPreset = {
  displayLabel: string;
  aliases: string[];
};

function normalizeMedicationAliasKey(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[_\-\/()]+/g, " ")
    .replace(/[^a-z0-9가-힣\s]+/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

const medicationAliasPresets: Record<string, MedicationAliasPreset> = {
  warfarin: {
    displayLabel: "와파린",
    aliases: ["와파린", "와파"],
  },
  levothyroxine: {
    displayLabel: "레보티록신",
    aliases: ["레보티록신"],
  },
  hydrochlorothiazide: {
    displayLabel: "하이드로클로로티아지드",
    aliases: ["하이드로클로로티아지드"],
  },
  chlorthalidone: {
    displayLabel: "클로르탈리돈",
    aliases: ["클로르탈리돈"],
  },
  "thiazide diuretic": {
    displayLabel: "티아지드계 이뇨제",
    aliases: ["티아지드", "티아지드계 이뇨제"],
  },
  "loop diuretic": {
    displayLabel: "루프계 이뇨제",
    aliases: ["루프 이뇨제", "루프계 이뇨제"],
  },
  furosemide: {
    displayLabel: "푸로세미드",
    aliases: ["푸로세미드"],
  },
  bumetanide: {
    displayLabel: "부메타니드",
    aliases: ["부메타니드"],
  },
  digoxin: {
    displayLabel: "디곡신",
    aliases: ["디곡신"],
  },
  aspirin: {
    displayLabel: "아스피린",
    aliases: ["아스피린"],
  },
  salicylate: {
    displayLabel: "살리실산계 약물",
    aliases: ["살리실산", "살리실산계 약물"],
  },
  nitrofurantoin: {
    displayLabel: "니트로푸란토인",
    aliases: ["니트로푸란토인"],
  },
  cyclosporine: {
    displayLabel: "사이클로스포린",
    aliases: ["사이클로스포린"],
  },
  tacrolimus: {
    displayLabel: "타크로리무스",
    aliases: ["타크로리무스"],
  },
  phenytoin: {
    displayLabel: "페니토인",
    aliases: ["페니토인"],
  },
  carbamazepine: {
    displayLabel: "카르바마제핀",
    aliases: ["카르바마제핀"],
  },
  simvastatin: {
    displayLabel: "심바스타틴",
    aliases: ["심바스타틴"],
  },
  statin: {
    displayLabel: "스타틴계 약물",
    aliases: ["스타틴", "스타틴계 약물"],
  },
  antidepressant: {
    displayLabel: "항우울제",
    aliases: ["항우울제"],
  },
  antiepileptic: {
    displayLabel: "항경련제",
    aliases: ["항경련제", "항전간제"],
  },
  anticoagulant: {
    displayLabel: "항응고제",
    aliases: ["항응고제"],
  },
  apixaban: {
    displayLabel: "아픽사반",
    aliases: ["아픽사반"],
  },
  rivaroxaban: {
    displayLabel: "리바록사반",
    aliases: ["리바록사반"],
  },
  dabigatran: {
    displayLabel: "다비가트란",
    aliases: ["다비가트란"],
  },
  "birth control pill": {
    displayLabel: "피임약",
    aliases: ["피임약", "경구피임약", "경구 피임약"],
  },
  "oral contraceptive": {
    displayLabel: "경구 피임약",
    aliases: ["피임약", "경구피임약", "경구 피임약"],
  },
  insulin: {
    displayLabel: "인슐린",
    aliases: ["인슐린"],
  },
  orlistat: {
    displayLabel: "올리스타트",
    aliases: ["올리스타트"],
  },
  ivabradine: {
    displayLabel: "이바브라딘",
    aliases: ["이바브라딘"],
  },
  indinavir: {
    displayLabel: "인디나비르",
    aliases: ["인디나비르"],
  },
  nevirapine: {
    displayLabel: "네비라핀",
    aliases: ["네비라핀"],
  },
  irinotecan: {
    displayLabel: "이리노테칸",
    aliases: ["이리노테칸"],
  },
  imatinib: {
    displayLabel: "이매티닙",
    aliases: ["이매티닙"],
  },
  docetaxel: {
    displayLabel: "도세탁셀",
    aliases: ["도세탁셀"],
  },
};

export function getMedicationAliasPreset(canonicalValue: string) {
  return medicationAliasPresets[normalizeMedicationAliasKey(canonicalValue)] ?? null;
}

export function getMedicationAliases(canonicalValue: string) {
  const preset = getMedicationAliasPreset(canonicalValue);
  return preset?.aliases ?? [];
}

export function getMedicationDisplayLabel(canonicalValue: string) {
  const preset = getMedicationAliasPreset(canonicalValue);
  return preset?.displayLabel ?? canonicalValue.replace(/_/g, " ").replace(/\s+/g, " ").trim();
}
