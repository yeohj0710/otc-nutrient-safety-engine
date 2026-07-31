import type { OtcProduct } from "./schema";

type SearchCandidate = { productName: string; className?: string };

const therapeuticClassAliases: Record<string, string[]> = {
  해열진통제: ["해열제", "진통제", "소염진통제", "두통약"],
  종합감기약: ["감기약", "기침약", "코감기약"],
  "위장관 일반의약품": ["소화제", "소화약", "위장약"],
  "외용 소염진통제": ["파스", "붙이는약", "외용진통제"],
  항히스타민제: ["알레르기약", "비염약"],
};

export function normalizeOtcSearchText(value: string): string {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("ko-KR")
    .replace(/[^\p{L}\p{N}]+/gu, "");
}

const containsQuery = (values: Array<string | undefined>, query: string) =>
  values.some((value) => value && normalizeOtcSearchText(value).includes(query));

const productSearchRank = (product: OtcProduct, query: string) => {
  if (containsQuery([product.productName], query)) return 0;
  if (containsQuery(product.ingredients.map((ingredient) => ingredient.nameKo), query)) {
    return 1;
  }
  if (containsQuery([product.therapeuticClass], query)) return 2;
  if (
    containsQuery(
      product.therapeuticClass
        ? therapeuticClassAliases[product.therapeuticClass] ?? []
        : [],
      query,
    )
  ) {
    return 3;
  }
  return Number.POSITIVE_INFINITY;
};

export function searchOtcProducts<T extends SearchCandidate>(
  products: OtcProduct[],
  candidates: T[],
  query: string,
) {
  const normalized = normalizeOtcSearchText(query);
  if (!normalized) return { verified: [] as OtcProduct[], candidates: [] as T[] };
  return {
    verified: products
      .map((product, index) => ({
        product,
        index,
        rank: productSearchRank(product, normalized),
      }))
      .filter(({ rank }) => Number.isFinite(rank))
      .sort((left, right) => left.rank - right.rank || left.index - right.index)
      .map(({ product }) => product),
    candidates: candidates.filter((candidate) =>
      containsQuery([candidate.productName, candidate.className], normalized),
    ),
  };
}
