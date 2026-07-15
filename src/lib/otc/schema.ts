export type Severity = "information" | "caution" | "high" | "urgent";

export type EvidenceLink = {
  sourceId: string;
  locator: string;
  url: string;
};

export type OtcIngredient = {
  ingredientId: string;
  nameKo: string;
  amountPerUnit: number;
  unit: "mg" | "g" | "mcg" | "mL" | "IU" | "%" | "unit";
  pharmacologicClasses: string[];
  maxDailyAmount?: number;
  minimumIntervalHours?: number;
  flags: string[];
  evidence: EvidenceLink;
};

export type OtcProduct = {
  productId: string;
  itemSequence: string;
  productName: string;
  classification: "일반의약품";
  authorizationStatus: "active";
  doseUnitLabel: "정" | "캡슐" | "mL" | "병" | "매";
  ingredients: OtcIngredient[];
  minimumAgeYears?: number;
  maximumContinuousDays?: number;
  flags: string[];
  evidence: EvidenceLink;
};

export type SelectedProduct = {
  product: OtcProduct;
  unitsPerDose: number;
  dosesPerDay: number;
  hoursSincePreviousDose?: number;
  continuousDays?: number;
};

export type UserProfile = {
  ageYears?: number;
  pregnant?: boolean;
  lactating?: boolean;
  liverDisease?: boolean;
  kidneyDisease?: boolean;
  giBleedingOrUlcer?: boolean;
  hypertensionOrCardiovascularDisease?: boolean;
  willDrive?: boolean;
  alcohol?: boolean;
  medications: string[];
  redFlagSymptoms: string[];
};

export type UrgentReferralBinding = {
  itemSequence: string;
  terms: string[];
};

export type SafetyFinding = {
  findingId: string;
  ruleType: string;
  severity: Severity;
  titleKo: string;
  detailKo: string;
  nextActionKo: string;
  productIds: string[];
  ingredientIds: string[];
  calculatedAmount?: number;
  referenceAmount?: number;
  unit?: string;
  evidence: EvidenceLink[];
};

export type SafetyEvaluation = {
  findings: SafetyFinding[];
  ingredientDailyTotals: Record<string, { amount: number; unit: string }>;
  evaluatedProductIds: string[];
  decisionMode: "deterministic";
};
