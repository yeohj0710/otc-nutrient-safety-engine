import type { OtcProduct, SelectedProduct } from "./schema";

export type SelectedProductDraft = {
  product: OtcProduct;
  unitsPerDose: string;
  dosesPerDay: string;
  hoursSincePreviousDose: string;
  continuousDays: string;
};

const requiredNumber = (value: string): number => {
  const trimmed = value.trim();
  return trimmed === "" ? Number.NaN : Number(trimmed);
};

const optionalNumber = (value: string): number | undefined => {
  const trimmed = value.trim();
  return trimmed === "" ? undefined : Number(trimmed);
};

const numberDraft = (value: number | undefined): string =>
  value === undefined || !Number.isFinite(value) ? "" : String(value);

/** 일반 제품을 담을 때 임의의 복용량을 만들지 않는다. */
export function createSelectedProductDraft(product: OtcProduct): SelectedProductDraft {
  return {
    product,
    unitsPerDose: "",
    dosesPerDay: "",
    hoursSincePreviousDose: "",
    continuousDays: "",
  };
}

export function selectedProductToDraft(
  selected: SelectedProduct,
): SelectedProductDraft {
  return {
    product: selected.product,
    unitsPerDose: numberDraft(selected.unitsPerDose),
    dosesPerDay: numberDraft(selected.dosesPerDay),
    hoursSincePreviousDose: numberDraft(selected.hoursSincePreviousDose),
    continuousDays: numberDraft(selected.continuousDays),
  };
}

/**
 * 엔진의 기존 숫자 계약으로 변환한다. 필수값이 비어 있으면 NaN을 넘겨
 * 용량 계산만 보류하고 엔진의 입력 이슈로 추적한다.
 */
export function parseSelectedProductDraft(
  draft: SelectedProductDraft,
): SelectedProduct {
  return {
    product: draft.product,
    unitsPerDose: requiredNumber(draft.unitsPerDose),
    dosesPerDay: requiredNumber(draft.dosesPerDay),
    hoursSincePreviousDose: optionalNumber(draft.hoursSincePreviousDose),
    continuousDays: optionalNumber(draft.continuousDays),
  };
}

export function isRequiredDoseDraftEmpty(
  draft: Pick<SelectedProductDraft, "unitsPerDose" | "dosesPerDay">,
): boolean {
  return draft.unitsPerDose.trim() === "" || draft.dosesPerDay.trim() === "";
}
