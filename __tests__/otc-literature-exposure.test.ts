import { describe, expect, it } from "vitest";

import {
  rulePoolFor,
  rulePoolPapers,
  type PoolQuery,
} from "@/src/lib/otc/rule-literature-pool";
import runtimeJson from "@/src/generated/otc-runtime.json";
import poolJson from "@/src/generated/recollect/rule-literature-pool.json";
import type { UserProfile } from "@/src/lib/otc/schema";

const runtime = runtimeJson as unknown as {
  products: { productId: string; ingredients: { nameKo: string }[] }[];
};
const pool = poolJson as unknown as {
  rules: Record<string, { record_ids: string[] }>;
};

const BOOLS = [
  "liverDisease",
  "kidneyDisease",
  "giBleedingOrUlcer",
  "hypertensionOrCardiovascularDisease",
  "willDrive",
  "alcohol",
] as const;

function profiles(): UserProfile[] {
  const out: UserProfile[] = [];
  for (const age of [8, 30, 72]) {
    for (const meds of [[], ["와파린"], ["졸피뎀"]]) {
      for (let mask = 0; mask < 1 << BOOLS.length; mask += 7) {
        const p: Record<string, unknown> = {
          ageYears: age,
          medications: meds,
          redFlagSymptoms: [],
        };
        BOOLS.forEach((key, i) => {
          if (mask & (1 << i)) p[key] = true;
        });
        out.push(p as unknown as UserProfile);
      }
    }
  }
  return out;
}

function gini(values: number[]) {
  const xs = [...values].sort((a, b) => a - b);
  const total = xs.reduce((a, b) => a + b, 0);
  if (!total) return 0;
  return (
    xs.reduce((acc, x, i) => acc + (2 * i - xs.length + 1) * x, 0) /
    (xs.length * total)
  );
}

/**
 * 인용문이 상태에 맞게 골고루 노출되는지 고정한다.
 *
 * 예전에는 빌드 때 정한 순서를 그대로 잘라 규칙마다 같은 20건만 보여줬다. 인용문
 * 4,660개 가운데 화면에 닿는 것이 320개(6.9%)뿐이었고 지니계수는 0.931 이었다.
 * (그때는 옛 트랙이었고, 지금 풀은 재수집 트랙이라 인용문이 5,909개다.)
 * 지금은 입력한 상태·성분 적합도로 점수를 매기고, 점수 구간을 띠로 나눈 뒤 띠마다
 * 조회별 회전값으로 하나씩 꺼내 페이지를 엮는다.
 */
describe("선별 통과 문헌 노출 분포", () => {
  it("상태 조합을 합치면 인용문 대부분이 첫 페이지에 닿는다", () => {
    const universe: string[] = [];
    for (const [rid, r] of Object.entries(pool.rules))
      for (const rec of r.record_ids) universe.push(`${rid}|${rec}`);

    const seen = new Map<string, number>();
    const ps = profiles();
    const products = runtime.products.slice(0, 4).map((product) => ({
      product,
      unitsPerDose: 1,
      dosesPerDay: 3,
    })) as unknown as NonNullable<PoolQuery["selected"]>;
    for (const profile of ps) {
      for (const rid of Object.keys(pool.rules)) {
        if (!rulePoolFor(rid)) continue;
        for (const entry of rulePoolPapers(rid, 0, 20, { profile, selected: products }))
          seen.set(`${rid}|${entry.record_id}`, (seen.get(`${rid}|${entry.record_id}`) ?? 0) + 1);
      }
    }
    const counts = universe.map((k) => seen.get(k) ?? 0);
    const shown = counts.filter((v) => v > 0).length;
    const total = counts.reduce((a, b) => a + b, 0);
    const ranked = [...counts].sort((a, b) => b - a);
    const top20 = ranked
      .slice(0, Math.max(1, Math.floor(ranked.length / 5)))
      .reduce((a, b) => a + b, 0);
    // 빌드 순서를 그대로 자르던 때는 6.9% · 지니 0.931 이었다.
    expect(shown / universe.length).toBeGreaterThan(0.9);
    expect(gini(counts)).toBeLessThan(0.6);
    expect(top20 / total).toBeLessThan(0.7);
  }, 600000);

  it("상태가 다르면 첫 페이지도 달라진다", () => {
    const base: UserProfile = {
      ageYears: 40,
      medications: [],
      redFlagSymptoms: [],
    } as unknown as UserProfile;
    const liver = { ...base, liverDisease: true } as UserProfile;
    const a = rulePoolPapers("OTC-RULE-007", 0, 20, { profile: base }).map(
      (e) => e.record_id,
    );
    const b = rulePoolPapers("OTC-RULE-007", 0, 20, { profile: liver }).map(
      (e) => e.record_id,
    );
    expect(a.filter((id) => b.includes(id)).length).toBeLessThan(a.length);
  });

  it("같은 상태는 항상 같은 순서를 준다", () => {
    const profile = {
      ageYears: 72,
      alcohol: true,
      medications: ["와파린"],
      redFlagSymptoms: [],
    } as unknown as UserProfile;
    const first = rulePoolPapers("OTC-RULE-003", 0, 20, { profile }).map(
      (e) => e.record_id,
    );
    const second = rulePoolPapers("OTC-RULE-003", 0, 20, { profile }).map(
      (e) => e.record_id,
    );
    expect(first).toEqual(second);
  });

  it("입력한 상태를 다룬 문헌이 위로 온다", () => {
    const liver = {
      ageYears: 40,
      liverDisease: true,
      medications: [],
      redFlagSymptoms: [],
    } as unknown as UserProfile;
    const top = rulePoolPapers("OTC-RULE-007", 0, 10, { profile: liver });
    const withLiver = top.filter((e) =>
      /hepat|liver|cirrho|jaundice|transaminase/i.test(`${e.title} ${e.quote}`),
    ).length;
    expect(withLiver).toBeGreaterThanOrEqual(7);
  });
});
