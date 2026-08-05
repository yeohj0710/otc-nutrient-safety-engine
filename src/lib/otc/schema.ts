export type Severity = "information" | "caution" | "high" | "urgent";

export type EvidenceLink = {
  sourceId: string;
  sourceVersion?: string;
  locator: string;
  url: string;
};

export type RuleEvidenceLink = EvidenceLink & {
  ruleId: string;
  productName: string;
  itemSequence: string;
  excerptKo: string;
  ruleType?: string;
  scope?: string;
  lineageStatus?: "mapped_from_v50_released_rule";
  applicability?: RuleApplicability;
};

export type ReleasedRuleEvidenceLink = RuleEvidenceLink & {
  sourceVersion: string;
};

export type RuleApplicability = {
  productItemSequences?: string[];
  ingredientIds?: string[];
  pharmacologicClasses?: string[];
  requiredAnchorIngredientIds?: string[];
  administrationConstraintTypes?: AdministrationConstraintType[];
  medicationTerms?: string[];
  minimumAgeYears?: number;
  pregnancyTrimesters?: Array<1 | 2 | 3>;
  lactationSupported?: boolean;
  urgentTerms?: string[];
};

export type ReleasedRulePolicy = {
  ruleId: string;
  ruleType: string;
  scope: string;
  lineageStatus: "mapped_from_v50_released_rule";
  applicability: RuleApplicability;
  evidence: ReleasedRuleEvidenceLink[];
};

export type OtcEvaluationOptions = {
  releasedRules: readonly ReleasedRulePolicy[];
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
  therapeuticClass?:
    | "해열진통제"
    | "종합감기약"
    | "위장관 일반의약품"
    | "외용 소염진통제"
    | "항히스타민제";
  doseUnitLabel: "정" | "캡슐" | "mL" | "병" | "매";
  ingredients: OtcIngredient[];
  administrationConstraints?: AdministrationConstraint[];
  supportedRuleTypes?: string[];
  supportedReleasedRuleIds?: string[];
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
  pregnancyTrimester?: 1 | 2 | 3;
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
  ruleId: string;
  decisionBasis: "released_rule" | "administration_constraint";
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
  ruleEvidence?: RuleEvidenceLink[];
};

export type SafetyInputIssue = {
  issueId: string;
  productId?: string;
  field:
    | "unitsPerDose"
    | "dosesPerDay"
    | "hoursSincePreviousDose"
    | "continuousDays"
    | "ageYears"
    | "pregnancyTrimester";
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
