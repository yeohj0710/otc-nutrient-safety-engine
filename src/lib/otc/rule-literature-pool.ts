import pool from "@/src/generated/otc-rule-literature-pool.json";

/**
 * 규칙별 '선별 통과 문헌'. 검증 근거(문장 locator + 원문 인용 대조를 통과한 10건)
 * 아래 층이며 지위가 다르다. 이 층의 문헌은 규칙을 배포시키지 못하고 판정을 바꾸지
 * 않는다. 생성기는 scripts/research/otc/build_rule_literature_pool.py 다.
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
};

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

export type PoolEntry = PoolPaper & { locator: string; quote: string };

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
    unique_papers_listed: number;
    quotable_sentences: number;
    title_only_quotes: number;
    retain_rows_in_corpus: number;
  };
  rules: Record<string, PoolRule>;
  papers: Record<string, PoolPaper>;
};

const data = pool as unknown as Pool;

export const rulePoolAuthority = data.authority;
export const rulePoolTotals = data.totals;

export function rulePoolFor(ruleId: string): PoolRule | null {
  return data.rules[ruleId] ?? null;
}

export function rulePoolPapers(ruleId: string, offset = 0, limit = 20): PoolEntry[] {
  const rule = data.rules[ruleId];
  if (!rule) return [];
  return rule.record_ids
    .slice(offset, offset + limit)
    .map((id) => {
      const paper = data.papers[id];
      if (!paper) return null;
      const q = rule.quotes[id];
      return { ...paper, locator: q?.locator ?? "", quote: q?.quote ?? "" };
    })
    .filter((entry): entry is PoolEntry => entry !== null);
}
