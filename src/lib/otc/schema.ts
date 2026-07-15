export type Severity = "information" | "caution" | "high" | "urgent";

export type EvidenceLink = {
  sourceId: string;
  locator: string;
  url: string;
};

export type AdministrationConstraintType =
  | "maximum_units_per_dose"
  | "maximum_doses_per_day"
  | "maximum_daily_ingredient_amount"
  | "minimum_interval_hours";

export type AdministrationConstraint = {
  constraintId: string;
  type: AdministrationConstraintType;
  value: number;
  valueUnit: string;
  ingredientId?: string;
  derivationMethod?: string;
  evidence: EvidenceLink;
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
  administrationConstraints?: AdministrationConstraint[];
  supportedRuleTypes?: string[];
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

export type SafetyInputIssue = {
  issueId: string;
  productId?: string;
  field: "unitsPerDose" | "dosesPerDay" | "hoursSincePreviousDose" | "continuousDays" | "ageYears";
  messageKo: string;
};

export type EvaluationCoverageGap = {
  gapId: string;
  ruleType: string;
  titleKo: string;
  detailKo: string;
  productIds: string[];
};

export type SafetyEvaluation = {
  findings: SafetyFinding[];
  inputIssues: SafetyInputIssue[];
  coverageGaps: EvaluationCoverageGap[];
  ingredientDailyTotals: Record<string, { amount: number; unit: string }>;
  evaluatedProductIds: string[];
  decisionMode: "deterministic";
};
