"use client";

import { FormEvent, useState } from "react";
import { evaluateResearchV3Draft } from "@/src/lib/research-v3/engine";
import styles from "./research-v3-explorer.module.css";

type Meta = {
  lineage: "research_v3";
  releaseStatus: "draft_not_for_clinical_use";
  claimBoundary: string;
  ruleCount: number;
  releasedRuleCount: number;
};

const ingredients = [
  { id: "vitamin_d", label: "비타민 D", unit: "μg", field: "dailyTotalUg" },
  { id: "vitamin_b6", label: "비타민 B6", unit: "mg", field: "dailyTotalMg" },
  { id: "iron", label: "철", unit: "mg", field: "dailyTotalMg" },
  { id: "magnesium", label: "마그네슘(식품 외 급원)", unit: "mg", field: "nonFoodDailyTotalMg" },
  { id: "zinc", label: "아연", unit: "mg", field: "dailyTotalMg" },
  { id: "calcium", label: "칼슘", unit: "mg", field: "dailyTotalMg" },
] as const;

type Result = ReturnType<typeof evaluateResearchV3Draft> | null;

export function ResearchV3Explorer({ meta }: { meta: Meta }) {
  const [ingredientId, setIngredientId] = useState("vitamin_d");
  const [amount, setAmount] = useState("100");
  const [age, setAge] = useState("30");
  const [sex, setSex] = useState<"male" | "female">("female");
  const [result, setResult] = useState<Result>(null);
  const selected = ingredients.find((item) => item.id === ingredientId) ?? ingredients[0];

  function submit(event: FormEvent) {
    event.preventDefault();
    const numericAmount = Number(amount);
    const input = {
      age: Number(age),
      sex,
      ingredientId,
      [selected.field]: numericAmount,
    };
    setResult(evaluateResearchV3Draft(input));
  }

  function loadExample() {
    setIngredientId("vitamin_d");
    setAmount("125");
    setAge("30");
    setSex("female");
    setResult(
      evaluateResearchV3Draft({
        age: 30,
        sex: "female",
        ingredientId: "vitamin_d",
        dailyTotalUg: 125,
      }),
    );
  }

  return (
    <main id="main-content" tabIndex={-1} className={styles.page}>
      <section className={styles.shell}>
        <header className={styles.header}>
          <p className={styles.eyebrow}>선행 계보 자료 · 현재 연구의 결과가 아닙니다</p>
          <h1>하루 총량, 기준과 함께 확인해요</h1>
          <p>제품 라벨의 같은 성분을 모두 더한 뒤 입력하세요. 현재 화면은 전문가 검토 전 연구 초안입니다.</p>
        </header>

        {/*
          이 연구는 2026-07-27 개정(AM-OTC-001)으로 고함량 영양성분에서 국내
          일반의약품 중복복용으로 방향을 바꿨다. 이 화면은 그 전에 만든 것이라
          지우지 않고 남기되, 현재 결과로 읽히지 않도록 맨 위에서 밝힌다.
        */}
        <aside className={styles.notice} aria-label="연구 상태">
          <strong>이 화면은 방향을 바꾸기 전의 계보 자료입니다.</strong>
          <span>
            현재 연구는 국내 일반의약품 중복복용이며, 그 내용은 <a href="/research">연구 정보</a>에
            있습니다. 여기의 KDRI 기준 초안은 현재 연구의 결과가 아니므로 인용하지 마십시오.
            공개 가능한 규칙 {meta.releasedRuleCount}건 · 검토 중 초안 {meta.ruleCount}건
          </span>
        </aside>

        <form className={styles.form} onSubmit={submit}>
          <label>
            성분
            <select value={ingredientId} onChange={(event) => { setIngredientId(event.target.value); setResult(null); }}>
              {ingredients.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
          </label>
          <div className={styles.row}>
            <label>
              하루 총량 ({selected.unit})
              <input required min="0" step="any" inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} />
            </label>
            <label>
              만 나이
              <input required min="0" max="120" step="1" inputMode="numeric" value={age} onChange={(event) => setAge(event.target.value)} />
            </label>
          </div>
          {ingredientId === "calcium" && (
            <fieldset>
              <legend>성별(칼슘 기준 구분)</legend>
              <label><input type="radio" checked={sex === "female"} onChange={() => setSex("female")} /> 여성</label>
              <label><input type="radio" checked={sex === "male"} onChange={() => setSex("male")} /> 남성</label>
            </fieldset>
          )}
          <div className={styles.actions}>
            <button className={styles.primary} type="submit">기준 초안 확인</button>
            <button className={styles.secondary} type="button" onClick={loadExample}>예시 입력으로 바로 보기</button>
          </div>
        </form>

        {result && (
          <section className={styles.result} aria-live="polite">
            <p className={styles.resultLabel}>확인 결과</p>
            {result.matches.length ? result.matches.map((rule) => (
              <article key={rule.id}>
                <h2>{rule.messageKo}</h2>
                <p>{rule.nextActionKo}</p>
                <details>
                  <summary>근거와 규칙 상태</summary>
                  <dl><dt>상태</dt><dd>전문가 검토 전 초안</dd><dt>출처 ID</dt><dd>{rule.sourceId}</dd><dt>원문 위치</dt><dd>{rule.locator}</dd><dt>규칙 ID</dt><dd>{rule.id}</dd></dl>
                </details>
              </article>
            )) : (
              <article>
                <h2>현재 초안의 초과 조건은 확인되지 않았어요.</h2>
                <p>이 결과는 안전하다는 뜻이 아닙니다. 연령, 질환, 병용약, 치료 목적 등은 아직 평가하지 않습니다.</p>
              </article>
            )}
          </section>
        )}

        <footer className={styles.footer}>
          연구 계보 {meta.lineage === "research_v3" ? "연구용 v3" : meta.lineage} ·{" "}
          {meta.releaseStatus === "draft_not_for_clinical_use"
            ? "임상 사용 전 초안"
            : meta.releaseStatus}{" "}
          · 성능 주장 없음
        </footer>
      </section>
    </main>
  );
}
