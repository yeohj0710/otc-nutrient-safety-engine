import pool from "@/src/generated/recollect/rule-literature-pool.json";
import type { SelectedProduct, UserProfile } from "@/src/lib/otc/schema";

/**
 * 규칙별 선별 통과 문헌. 검증 근거(문장 locator 와 원문 인용 대조를 통과한 10건)
 * 아래 층이며 지위가 다르다. 이 층의 문헌은 규칙을 배포시키지 못하고 판정을 바꾸지
 * 않는다.
 *
 * 자료는 재수집 트랙(recollect-v2 · kwon)이다. 생성기는
 * scripts/research/otc/build_recollect_rule_literature_pool.py 이며, 도출식은
 * 옛 빌더 build_rule_literature_pool.py 에서 그대로 가져와 쓴다.
 */
export type PoolPaper = {
  record_id: string;
  pmid: string;
  title: string;
  journal: string;
  year: string;
  doi: string;
  publication_types: string;
  has_abstract: boolean;
  url: string;
  /** 상태 표지 비트마스크. profile_facets 순서를 따른다. */
  f?: number;
  /** 성분 언급 비트마스크. ingredient_terms 순서를 따른다. */
  g?: number;
};

export type PoolEntry = PoolPaper & { locator: string; quote: string };

export type PoolRule = {
  rule_type: string;
  status: string;
  allowed_question_ids: string[];
  question_pool_total: number;
  rule_type_matched_total: number;
  listed: number;
  truncated: number;
  verified_link_count: number;
  record_ids: string[];
  quotes: Record<string, { locator: string; quote: string }>;
};

type Pool = {
  schema_version: string;
  authority: {
    supports_rule_release: boolean;
    evidence_authority: string;
    quote_verified: boolean;
    human_expert_reviewed: number;
  };
  totals: {
    rules: number;
    /** 두 단계 좁히기를 통과한 고유 논문. 규칙당 상한을 적용하기 전 값이다. */
    unique_papers_matched: number;
    rule_paper_pairs: number;
    rule_question_paper_rows: number;
    /** 그중 화면에 싣는 고유 논문. 규칙당 상한을 적용한 뒤 값이다. */
    unique_papers_listed: number;
    quotable_sentences: number;
    title_only_quotes: number;
    retain_rows_in_corpus: number;
    retain_papers_in_corpus: number;
  };
  profile_facets: string[];
  ingredient_terms: string[];
  rules: Record<string, PoolRule>;
  papers: Record<string, PoolPaper>;
};

const data = pool as unknown as Pool;

export const rulePoolAuthority = data.authority;
export const rulePoolTotals = data.totals;
export const rulePoolFacets = data.profile_facets;

export function rulePoolFor(ruleId: string): PoolRule | null {
  return data.rules[ruleId] ?? null;
}

/** 사용자가 화면에 입력한 것을 상태 표지 비트마스크로 바꾼다. */
export function profileFacetMask(profile: UserProfile | undefined): number {
  if (!profile) return 0;
  const on: string[] = [];
  const age = profile.ageYears;
  if (typeof age === "number" && age < 19) on.push("pediatric");
  if (typeof age === "number" && age >= 65) on.push("elderly");
  if (profile.pregnant || profile.pregnancyTrimester) on.push("pregnancy");
  if (profile.lactating) on.push("lactation");
  if (profile.liverDisease) on.push("liver");
  if (profile.kidneyDisease) on.push("kidney");
  if (profile.giBleedingOrUlcer) on.push("gi_bleed");
  if (profile.hypertensionOrCardiovascularDisease) on.push("hypertension");
  if (profile.willDrive) on.push("driving");
  if (profile.alcohol) on.push("alcohol");
  const meds = (profile.medications ?? []).join(" ").toLowerCase();
  if (/와파린|warfarin|아스피린|aspirin|항응고|클로피도그렐|clopidogrel/.test(meds))
    on.push("anticoagulant");
  if (/졸피뎀|zolpidem|수면|진정|벤조|benzo|디아제팜|diazepam/.test(meds))
    on.push("sedative");
  let mask = 0;
  for (const name of on) {
    const index = data.profile_facets.indexOf(name);
    if (index >= 0) mask |= 1 << index;
  }
  return mask;
}

const INGREDIENT_MATCHERS: Record<string, RegExp> = {
  acetaminophen: /아세트아미노펜|파라세타몰/,
  ibuprofen: /이부프로펜/,
  dexibuprofen: /덱시부프로펜/,
  naproxen: /나프록센/,
  aspirin: /아스피린|아세틸살리실/,
  chlorpheniramine: /클로르페니라민/,
  pheniramine: /페니라민/,
  cetirizine: /세티리진/,
  pseudoephedrine: /슈도에페드린|페닐에프린/,
  dextromethorphan: /덱스트로메토르판/,
  guaifenesin: /구아이페네신/,
  caffeine: /카페인/,
  pancreatin: /판크레아틴|소화효소/,
  ursodeoxycholic: /우르소데옥시콜|우르소/,
  simethicone: /시메티콘|디메티콘/,
  methyl_salicylate: /살리실산메틸/,
  menthol: /멘톨|캄파/,
};

/** 고른 제품의 성분을 문헌 검색용 표기로 바꾼다. */
export function ingredientMask(selected: readonly SelectedProduct[] | undefined) {
  if (!selected?.length) return 0;
  const text = selected
    .flatMap((item) => item.product.ingredients.map((ing) => ing.nameKo))
    .join(" ");
  let mask = 0;
  for (const [name, pattern] of Object.entries(INGREDIENT_MATCHERS)) {
    if (!pattern.test(text)) continue;
    const index = data.ingredient_terms.indexOf(name);
    if (index >= 0) mask |= 1 << index;
  }
  return mask;
}

function popcount(value: number) {
  let n = value;
  let count = 0;
  while (n) {
    n &= n - 1;
    count += 1;
  }
  return count;
}

/** 32비트 결정적 해시. 조회마다 다른 순서를 주되 난수는 쓰지 않는다. */
function rotationKey(seed: string, recordId: string) {
  let hash = 2166136261;
  const text = `${seed}|${recordId}`;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967296;
}

const STOP_WORDS = new Set([
  "the", "and", "for", "with", "that", "this", "were", "was", "are", "from",
  "have", "has", "had", "not", "but", "than", "into", "also", "may", "can",
  "results", "conclusions", "background", "methods", "objective", "study",
  "patients", "group", "groups", "among", "between", "after", "before",
]);

function contentTokens(text: string) {
  return new Set(
    text
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((word) => word.length > 3 && !STOP_WORDS.has(word)),
  );
}

function overlapRatio(left: Set<string>, right: Set<string>) {
  if (!left.size || !right.size) return 0;
  let shared = 0;
  for (const token of left) if (right.has(token)) shared += 1;
  return shared / Math.min(left.size, right.size);
}

function quoteQuality(entry: PoolEntry) {
  let score = 0;
  if (/^(?:RESULTS?|CONCLUSIONS?|FINDINGS?):/i.test(entry.quote)) score += 1.5;
  if (/(?<![A-Za-z])\d/.test(entry.quote)) score += 1;
  if (/increase|decreas|reduc|associat|risk|higher|lower|significant/i.test(entry.quote))
    score += 1;
  if (entry.quote.length >= 90) score += 0.5;
  if (!entry.has_abstract) score -= 2;
  return score;
}

export type PoolQuery = {
  profile?: UserProfile;
  selected?: readonly SelectedProduct[];
  /** 조회 서명. 같은 값이면 같은 순서를 준다. */
  seed?: string;
};

const orderCache = new Map<string, PoolEntry[]>();

/**
 * 규칙의 문헌을 사용자 상태에 맞춰 정렬한다.
 *
 * 예전에는 빌드 때 정한 순서를 그대로 잘라 보여줬다. 그래서 어떤 상태를 입력하든
 * 규칙마다 같은 20건만 화면에 닿았고, 인용문 4,660개 가운데 320개(6.9%)만 노출됐다.
 * (그때 수치이고, 지금은 재수집 트랙이라 인용문이 5,909개다.)
 * 지금은 세 가지를 함께 쓴다.
 *   ① 상태 적합도  입력한 항목과 성분을 실제로 언급한 문헌을 위로 올린다
 *   ② 다양성       이미 고른 인용문과 낱말이 겹치면 뒤로 민다
 *   ③ 띠 엮기      점수 구간을 띠로 나누고 띠마다 조회별 회전값으로 하나씩 꺼낸다
 * 회전값은 조회 서명에서 나온 결정적 해시라 같은 입력은 항상 같은 순서를 준다.
 */
export function rulePoolOrdered(
  ruleId: string,
  pageSize: number,
  query: PoolQuery = {},
): PoolEntry[] {
  const rule = data.rules[ruleId];
  if (!rule) return [];
  const facetMask = profileFacetMask(query.profile);
  const ingMask = ingredientMask(query.selected);
  const seed = query.seed ?? `${ruleId}|${facetMask}|${ingMask}`;
  const cacheKey = `${ruleId}|${pageSize}|${seed}`;
  const cached = orderCache.get(cacheKey);
  if (cached) return cached;

  const entries: PoolEntry[] = rule.record_ids
    .map((id) => {
      const paper = data.papers[id];
      if (!paper) return null;
      const quote = rule.quotes[id];
      return { ...paper, locator: quote?.locator ?? "", quote: quote?.quote ?? "" };
    })
    .filter((entry): entry is PoolEntry => entry !== null);

  const scored = entries.map((entry) => ({
    entry,
    tokens: contentTokens(entry.quote || entry.title),
    // 입력한 상태를 언급한 문헌이 크게 앞선다. 성분 일치는 그다음이다.
    base:
      popcount((entry.f ?? 0) & facetMask) * 3 +
      popcount((entry.g ?? 0) & ingMask) * 1.5 +
      quoteQuality(entry),
    rotation: rotationKey(seed, entry.record_id),
  }));
  scored.sort(
    (a, b) => b.base - a.base || a.entry.record_id.localeCompare(b.entry.record_id),
  );

  let result: PoolEntry[];
  if (scored.length <= pageSize) {
    result = scored.map((item) => item.entry);
  } else {
    const bands: (typeof scored)[] = [];
    const bandSize = scored.length / pageSize;
    for (let band = 0; band < pageSize; band += 1) {
      const from = Math.floor(band * bandSize);
      const to =
        band === pageSize - 1
          ? scored.length
          : Math.max(from, Math.floor((band + 1) * bandSize));
      const slice = scored.slice(from, to);
      slice.sort(
        (a, b) =>
          b.rotation - a.rotation ||
          a.entry.record_id.localeCompare(b.entry.record_id),
      );
      bands.push(slice);
    }
    const out: (typeof scored)[number][] = [];
    const depth = Math.max(...bands.map((band) => band.length));
    for (let index = 0; index < depth; index += 1) {
      const page: (typeof scored)[number][] = [];
      for (const band of bands) if (index < band.length) page.push(band[index]);
      // 페이지 안에서만 다양성을 건다. 페이지 경계를 넘지 않아 페이징이 안정적이다.
      const picked: (typeof scored)[number][] = [];
      const rest = [...page];
      while (rest.length) {
        let bestIndex = 0;
        let bestValue = -Infinity;
        for (let i = 0; i < rest.length; i += 1) {
          let penalty = 0;
          for (const done of picked) {
            const ratio = overlapRatio(rest[i].tokens, done.tokens);
            if (ratio > penalty) penalty = ratio;
          }
          const value = (page.length - i) / page.length - penalty * 2.5;
          if (value > bestValue) {
            bestValue = value;
            bestIndex = i;
          }
        }
        picked.push(rest[bestIndex]);
        rest.splice(bestIndex, 1);
      }
      out.push(...picked);
    }
    result = out.map((item) => item.entry);
  }

  if (orderCache.size > 200) orderCache.clear();
  orderCache.set(cacheKey, result);
  return result;
}

export function rulePoolPapers(
  ruleId: string,
  offset = 0,
  limit = 20,
  query: PoolQuery = {},
): PoolEntry[] {
  return rulePoolOrdered(ruleId, limit, query).slice(offset, offset + limit);
}
