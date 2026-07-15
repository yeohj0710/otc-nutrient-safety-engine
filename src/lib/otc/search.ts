import type { OtcProduct } from "./schema";

type SearchCandidate = { productName: string };

export function searchOtcProducts<T extends SearchCandidate>(products: OtcProduct[], candidates: T[], query: string) {
  const normalized = query.trim().toLocaleLowerCase("ko-KR");
  if (!normalized) return { verified: [] as OtcProduct[], candidates: [] as T[] };
  return {
    verified: products.filter((product) => product.productName.toLocaleLowerCase("ko-KR").includes(normalized)),
    candidates: candidates.filter((candidate) => candidate.productName.toLocaleLowerCase("ko-KR").includes(normalized)),
  };
}
