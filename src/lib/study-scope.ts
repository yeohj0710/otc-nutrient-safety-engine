export const studyScope = {
  shortLabel: "고함량 일반의약품형 영양성분",
  description:
    "일반의약품과 건강기능식품 경계에서 흔히 쓰이는 고함량 비타민, 미네랄, 식이섬유 성분을 중심으로 노출합니다.",
  ingredientIds: [
    "vitamin_d",
    "calcium",
    "vitamin_b6",
    "magnesium_supplement",
    "iron",
    "zinc",
    "vitamin_a_preformed",
    "niacin",
    "selenium",
    "iodine",
    "folic_acid",
    "vitamin_c",
    "psyllium_husk",
    "vitamin_b_complex",
    "vitamin_b12",
    "multivitamin_multimineral",
    "mineral_supplements_generic",
  ],
} as const;

export const studyIngredientIdSet = new Set<string>(studyScope.ingredientIds);
