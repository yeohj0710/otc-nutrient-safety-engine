import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const componentSource = readFileSync(
  resolve(process.cwd(), "src/components/otc-product-safety-client.tsx"),
  "utf8",
);
const styleSource = readFileSync(
  resolve(process.cwd(), "src/components/otc-product-safety.module.css"),
  "utf8",
);
const pageSource = readFileSync(
  resolve(process.cwd(), "app/page.tsx"),
  "utf8",
);
const presentationSource = readFileSync(
  resolve(process.cwd(), "src/lib/otc/presentation.ts"),
  "utf8",
);
const explainSource = readFileSync(
  resolve(process.cwd(), "src/lib/ai/explainOtcFindings.ts"),
  "utf8",
);
const explainRouteSource = readFileSync(
  resolve(process.cwd(), "app/api/otc-explain/route.ts"),
  "utf8",
);

describe("OTC checker layout contract", () => {
  it("keeps the two input panels in one independent flow column", () => {
    expect(componentSource).toContain("className={styles.inputColumn}");
    expect(styleSource).toContain(".inputColumn");
    expect(styleSource).not.toContain("grid-row: 1 / span 2");
  });

  it("uses a left-aligned uniform grid for example actions", () => {
    expect(styleSource).toMatch(
      /\.quickCheckList\s*\{[\s\S]*?grid-template-columns:[\s\S]*?justify-content:\s*start/,
    );
    expect(componentSource).not.toContain(
      "<small>{quickCheck.description}</small>",
    );
  });

  it("separates authorization evidence from reference literature in wording and markup", () => {
    // 판정 근거는 허가원문, 문헌은 설명용. 화면에서 두 블록이 분리돼 있어야 한다.
    expect(componentSource).toContain('aria-label="판정에 사용한 식약처 허가 근거"');
    expect(componentSource).toContain('aria-label="참고 문헌 · 판정 근거 아님"');
    expect(componentSource).toContain("<strong>판정 규칙 근거</strong>");
    expect(componentSource).toContain(">참고 문헌</strong>");
    expect(componentSource).toContain("판정 근거 아님");
    // 요약 줄도 두 축을 나눠 센다.
    expect(componentSource).toContain("현재 제품 규칙 원문 전체 일치");
    // 예전 표현이 남아 있으면 문헌이 판정 근거처럼 읽힌다.
    expect(componentSource).not.toContain("직접 연결 학술문헌");
  });

  it("always shows the literature disclaimer next to reference papers", () => {
    expect(componentSource).toContain("참고 문헌은 판정 근거가 아니며 허가원문 판정을 바꾸지");
    expect(componentSource).toContain("않습니다.");
    expect(componentSource).toContain("styles.literatureDisclaimer");
    expect(styleSource).toContain(".literatureDisclaimer");
  });

  it("shows same-rule papers without calling them direct ingredient evidence", () => {
    expect(componentSource).toContain(
      "문장 인용 대조를 통과한 검증 근거가 없습니다",
    );
    expect(componentSource).toContain("같은 규칙의 배경 문헌");
    expect(componentSource).toContain("현재 판정의 직접 근거가 아님");
    expect(componentSource).not.toContain(
      "직접 연결된 참고 문헌은 아직 없습니다.",
    );
  });

  it("states the small runtime scope instead of hiding it behind one rule count", () => {
    expect(pageSource).toContain("공개 안전성 규칙");
    expect(pageSource).toContain("제품별 직접 규칙 연결");
    expect(pageSource).toContain("허가 사용·복용 조건");
    expect(pageSource).toContain("v5.0 채택");
    expect(pageSource).not.toContain("보조 문헌");
  });

  it("keeps released rules, authorization constraints, and literature states distinct", () => {
    expect(pageSource).toContain(
      "공개 안전성 규칙과 제품별 허가 사용·복용 조건만 판정",
    );
    expect(pageSource).not.toContain("연결된 규칙만 판정");
    expect(pageSource).toContain("직접 일치 {v5DirectMatchLinkCount}건");
    expect(pageSource).toContain(
      "범위 일치 시 직접 {v5ConditionalDirectLinkCount}건",
    );
    expect(pageSource).toContain("배경 전용 {v5BackgroundOnlyLinkCount}건");
    expect(pageSource).toContain(
      "감사 전용·결과 화면 제외 {v5ExcludedLinkCount}건",
    );
    expect(pageSource).not.toContain("v5DirectCapableLinkCount");
    expect(componentSource).toContain(
      "공개 안전성 규칙 또는 제품별 허가 사용·복용 조건이 연결된 제품만 점검에 사용해요.",
    );
    expect(componentSource).toContain(
      "제품별 공개 안전성 규칙이나 허가 사용·복용 조건이 연결된 입력만",
    );
    expect(componentSource).not.toContain(
      "식약처 허가 원문과 안전성 규칙까지 연결된 제품만 점검에 사용해요.",
    );
    expect(presentationSource).toContain(
      "기각한 10건은 감사용 데이터로 보존하지만 결과 화면에서는 항상 제외한다.",
    );
  });

  it("groups repetitive warnings and shows the checked scope beside the result", () => {
    expect(componentSource).toContain("groupFindingsForDisplay");
    expect(componentSource).toContain("styles.resultScope");
    expect(componentSource).toContain("선택 제품");
    expect(componentSource).toContain("지원 점검 유형");
    expect(componentSource).toContain("공개 규칙 연결");
    expect(componentSource).toContain("사용·복용 조건");
    expect(styleSource).toContain(".resultScope");
    expect(pageSource).toContain("max-w-[1240px]");
  });

  it("orders results by action, direct authorization, gaps, calculations, and literature status", () => {
    const headingIds = [
      "result-actions-heading",
      "direct-authorization-heading",
      "coverage-heading",
      "calculation-heading",
      "v5-literature-heading",
      "background-evidence-heading",
    ];
    const positions = headingIds.map((id) => componentSource.indexOf(`id="${id}"`));
    expect(positions.every((position) => position >= 0)).toBe(true);
    expect(positions).toEqual([...positions].sort((left, right) => left - right));
    expect(componentSource).toContain("현재 제품의 식약처 허가 원문");
    expect(componentSource).toContain("v5.0 채택 PubMed 문헌");
    expect(componentSource).toContain("대표 제품 허가 원문");
  });

  it("renders only v5.0-emitted direct and background literature", () => {
    expect(componentSource).toContain("현재 판정과 직접 일치");
    expect(componentSource).toContain("현재 판정의 직접 근거가 아님");
    expect(componentSource).not.toContain("v5.0 연결 밖 후보");
    expect(componentSource).not.toContain("검색식 미인출");
    expect(componentSource).not.toContain("허용 질문에서 retain 아님");
    expect(componentSource).not.toContain("outsideV50LiteratureForFinding");
    expect(componentSource).not.toContain("v50CorpusStatus");
  });

  it("uses exact released-rule evidence for representative product sources", () => {
    expect(componentSource).toContain("releasedRuleEvidenceById");
    expect(componentSource).toContain(
      'finding.decisionBasis === "released_rule"',
    );
    expect(componentSource).toContain(
      "releasedRuleEvidenceById.get(finding.ruleId)",
    );
  });

  it("keeps tooltip buttons out of selectable product buttons", () => {
    expect(componentSource).toContain("showLimitTooltip = false");
    expect(componentSource).toContain("{showLimitTooltip && (");
    expect(componentSource.match(/showLimitTooltip\s*\/>/g)).toHaveLength(1);
    expect(componentSource).toContain('pointerType === "touch"');
    expect(componentSource).toContain("setOpen((current) => !current)");
  });

  it("shows partial current-product authorization matches without inflating them", () => {
    expect(componentSource).toContain("findingsWithAllDirectRuleEvidence");
    expect(componentSource).toContain("findingsWithPartialDirectRuleEvidence");
    expect(componentSource).toContain("display?.matchedProductCount");
    expect(componentSource).toContain("display?.findingProductCount");
    expect(componentSource).toContain('display?.productMatch === "partial"');
  });

  it("collects the exact pregnancy stage and states the recognized medication scope", () => {
    expect(componentSource).toContain('name="pregnancy-trimester"');
    expect(componentSource).toContain('<option value="1">1기</option>');
    expect(componentSource).toContain('<option value="2">2기</option>');
    expect(componentSource).toContain('<option value="3">3기</option>');
    expect(componentSource).toContain("현재 어린이부루펜의 임신 3기만 판정합니다.");
    expect(componentSource).toContain("현재 항응고제는 와파린·쿠마린 표현만 판정합니다.");
    expect(componentSource).toContain("아픽사반·아스피린과 다른 약은 판정하지 않고");
  });

  it("shows product and profile support boundaries before evaluation", () => {
    expect(componentSource).toContain("buildProductSupportSummary");
    expect(presentationSource).toContain(
      'activeCheckTypes.includes("minimum_interval")',
    );
    expect(componentSource).toContain("inputSupportStatusMessage");
    expect(componentSource).toContain("현재 입력값에 지원 범위 밖 항목 있음");
    expect(componentSource).toContain("hasCoverageGapFor");
    expect(componentSource).toContain("현재 점검에 사용되지 않음");
    expect(styleSource).toContain(".productSupport");
    expect(styleSource).toContain(".inputSupportStatus");
  });

  it("labels the checker as a research prototype in all key states", () => {
    expect(pageSource).toContain("연구용 시제품 · 임상 사용 승인 아님");
    expect(componentSource).toContain("연구용 시제품 · 임상 사용 승인 아님");
    expect(componentSource).toContain(
      "제품별로 연결된 사용량·간격·질환·병용약 조건만 판정합니다.",
    );
  });

  it("keeps the related-literature disclosure keyboard visible", () => {
    expect(styleSource).toContain(
      ".otherIngredientLiterature summary:focus-visible",
    );
  });

  it("shows the sentence-level locator and preserved authorization conflicts", () => {
    expect(componentSource).toContain("styles.literatureLocator");
    expect(componentSource).toContain("link.locatorQuoteEn");
    expect(componentSource).toContain('authorizationAlignment === "conflict"');
    expect(componentSource).toContain("<strong>허가원문과 다른 점</strong>");
    expect(styleSource).toContain(".literatureConflict");
  });

  it("does not fake a loading state for synchronous calculations", () => {
    expect(componentSource).not.toContain("isEvaluating");
    expect(componentSource).not.toContain("460");
    expect(componentSource).not.toContain("calculationSpinner");
  });

  it("keeps manual dose input as a string draft and clears the active demo", () => {
    expect(componentSource).toContain("SelectedProductDraft");
    expect(componentSource).toContain("clearActiveDemo");
    expect(componentSource).not.toContain("unitsPerDose: Number(event.target.value)");
    expect(componentSource).not.toContain("dosesPerDay: Number(event.target.value)");
  });

  it("does not show the clear result while required dose fields are incomplete", () => {
    expect(componentSource).toMatch(
      /pendingDoseDrafts\.length === 0 &&\s+orderedFindings\.length === 0 &&\s+visibleInputIssues\.length === 0/,
    );
    expect(componentSource).toMatch(
      /const showResultSummary =\s+orderedFindings\.length > 0 \|\| visibleInputIssues\.length > 0/,
    );
    expect(componentSource).toContain(") : showResultSummary ? (");
  });

  it("uses accessible help, focus, touch, spacing, and safe-area contracts", () => {
    expect(componentSource).toContain('role="tooltip"');
    expect(componentSource).toContain('event.key === "Escape"');
    expect(styleSource).toContain("--space-1: 4px");
    expect(styleSource).toContain("--space-2: 8px");
    expect(styleSource).toContain("--tap-target: 44px");
    expect(styleSource).toContain("min-height: var(--tap-target)");
    expect(styleSource).toContain("env(safe-area-inset-bottom)");
    // 머리띠(4rem) 아래에 단계 표시가 또 붙어 있다. 둘을 다 비우지 않으면
    // 결과로 데려간 자리에서 패널 머리글이 단계 표시에 가린다.
    expect(styleSource).toMatch(
      /\.resultPanel\s*\{[\s\S]*?scroll-margin-top:\s*calc\(4rem \+ var\(--space-12\) \+ var\(--space-3\)\)/,
    );
    expect(styleSource).toContain(":focus-visible");
    expect(styleSource).toContain("@media (prefers-reduced-motion: reduce)");
    expect(styleSource).toContain("@media (max-width: 420px)");
    expect(styleSource).toMatch(
      /@media \(max-width: 560px\)[\s\S]*?\.quickCheckList\s*\{\s*grid-template-columns:\s*1fr/,
    );
    expect(styleSource).toMatch(
      /@media \(max-width: 560px\)[\s\S]*?\.quickCheckButton span[\s\S]*?white-space:\s*normal/,
    );
    expect(componentSource).toContain('setActiveTherapeuticClass("전체")');
    expect(componentSource).toContain("setOpenFindingIds({})");
  });

  it("keeps the primary product flow on the spacing scale with readable support text", () => {
    expect(styleSource).toMatch(
      /\.workspaceGrid\s*\{[\s\S]*?gap:\s*var\(--space-6\)/,
    );
    expect(styleSource).toMatch(
      /\.inputColumn\s*\{[\s\S]*?gap:\s*var\(--space-6\)/,
    );
    expect(styleSource).toMatch(
      /\.searchResults > button,[\s\S]*?padding:\s*var\(--space-3\) var\(--space-4\)/,
    );
    expect(styleSource).toMatch(
      /\.productShelfGrid\s*\{[\s\S]*?gap:\s*var\(--space-2\)/,
    );
    expect(styleSource).toMatch(
      /\.selectedCardHeader\s*\{[\s\S]*?padding:\s*var\(--space-4\)/,
    );
    expect(styleSource).toMatch(
      /\.profileBody\s*\{[\s\S]*?gap:\s*var\(--space-4\);[\s\S]*?padding:\s*var\(--space-4\)/,
    );
    expect(styleSource).toMatch(
      /\.resultBody\s*\{[\s\S]*?padding:\s*var\(--space-6\)/,
    );
    // 13px 이 보조 설명의 기본이고 12px 이 바닥이다. 예전에는 9~11px 짜리
    // 설명줄이 화면 곳곳에 있었는데, 한글은 같은 px 에서 라틴 문자보다 작아
    // 보여서 그 크기에 회색까지 겹치면 읽는 일 자체가 일이 된다.
    expect(styleSource).toMatch(
      /\.productSupportTitle\s*\{[\s\S]*?font-size:\s*13px/,
    );
    expect(styleSource).toMatch(
      /\.productSupportDetails,[\s\S]*?font-size:\s*13px/,
    );
    expect(styleSource).toMatch(
      /\.inputSupportStatus\s*\{[\s\S]*?font-size:\s*13px/,
    );
    expect(styleSource).toMatch(
      /\.resultScope span\s*\{[\s\S]*?font-size:\s*13px/,
    );
    // 바닥 아래로 다시 새지 않게 막는다.
    expect(styleSource).not.toMatch(/font-size:\s*(?:[1-9]|10|11)px/);
    expect(styleSource).toMatch(
      /\.findings\s*\{[\s\S]*?gap:\s*var\(--space-3\);[\s\S]*?margin-top:\s*var\(--space-3\)/,
    );
    expect(styleSource).toMatch(
      /\.findingDisclosure > summary\s*\{[\s\S]*?gap:\s*var\(--space-3\);[\s\S]*?padding:\s*var\(--space-3\) var\(--space-4\)/,
    );
  });

  it("writes every margin, padding, and gap on the scale", () => {
    // 한때 1·2·3·5·6·7·9·10·11·14·15·18px 이 전부 여백으로 쓰였다. 같은 일을
    // 하는 카드 안쪽 여백이 9·10·11px 세 가지였다는 뜻이다. 값이 아니라 역할이
    // 흩어져 있던 것이라, 새 값을 하나 적으면 조용히 다시 흩어진다.
    //
    // 예외 둘은 리듬이 아니라 자리 예약이다. 절대 배치한 배지가 들어올 자리
    // (60px)와 화면 아래 고정 막대가 덮지 않게 비운 자리(80px).
    const RESERVED = /60px|80px/;
    const offScale: string[] = [];
    const declaration =
      /(?:^|\n)\s*(margin|margin-top|margin-right|margin-bottom|margin-left|margin-block|margin-inline|padding|padding-top|padding-right|padding-bottom|padding-left|padding-block|padding-inline|gap|row-gap|column-gap)\s*:\s*([^;]+);/g;
    for (const match of styleSource.matchAll(declaration)) {
      const value = match[2];
      if (RESERVED.test(value)) continue;
      if (/(^|[\s(])-?\d+px/.test(value)) offScale.push(`${match[1]}: ${value.trim()}`);
    }
    expect(offScale).toEqual([]);

    // 반 단계가 없으면 2px·6px 자리를 4px 격자로 못 잡아 다시 원시값이 샌다.
    expect(styleSource).toContain("--space-0-5: 2px");
    expect(styleSource).toContain("--space-1-5: 6px");
  });

  it("derives the tooltip inset from the tap target instead of a fixed offset", () => {
    // 44px 탭 영역을 24px 아이콘 자리로 줄이는 음수 여백이다. -10px 로 적어 두면
    // --tap-target 을 고칠 때 같이 안 따라와 글줄이 밀린다.
    expect(styleSource).toMatch(
      /\.supportTooltip\s*\{[\s\S]*?margin:\s*calc\(\(var\(--tap-target\) - var\(--space-6\)\) \/ -2\)/,
    );
    expect(styleSource).not.toMatch(/margin:\s*-10px -8px -10px 2px/);
  });

  it("keeps the AI summary panel on screen when the summary fails", () => {
    // 예전에는 실패하면 칸이 통째로 사라져서, 요약이 원래 없는 화면인지 이번에
    // 못 붙은 것인지 알 길이 없었다. 판정은 아래 엔진 결과가 정본이라 칸을
    // 남겨도 잃는 내용이 없고, 남겨야 왜 못 붙었는지 말할 자리가 생긴다.
    expect(componentSource).toContain("{(aiExplainPending || aiExplain) && (");
    expect(componentSource).not.toContain("{(aiExplainPending || aiExplain?.ok) && (");
    expect(componentSource).toContain("{aiExplain.notice}");
    expect(componentSource).toContain("이번에는 못 붙였습니다");
    // 400 응답도 본문을 읽어야 까닭이 남는다.
    expect(componentSource).not.toContain("res.ok ? res.json() : null");
  });

  it("tells the summary writer not to issue instructions", () => {
    // 예전 지시문이 "판단이 필요하면 약사·의사와 상의하라고만 적으십시오"로
    // 끝나서, 요약이 엔진의 nextAction 을 그대로 옮겨 "…확인하고 약사 또는
    // 의사와 상담하십시오"라고 시키는 문장이 화면에 나갔다. 할 일은 판정마다
    // 붙는 "지금 할 일" 칸이 이미 적고 있으므로 요약이 다시 시킬 자리가 아니다.
    // 문체 문제이므로 심판이 아니라 프롬프트에서 막는다.
    expect(explainSource).not.toContain("약사·의사와 상의하라고만 적으십시오");
    expect(explainSource).toContain("시키는 말투를 쓰지 마십시오");
    for (const ending of ["~하십시오", "~하세요", "~해 주세요", "~해야 합니다"]) {
      expect(explainSource, ending).toContain(`'${ending}'`);
    }
    expect(explainSource).toContain(
      "엔진이 적어 둔 nextAction 을 요약문에 옮겨 적지 마십시오",
    );
    // 고쳐 쓰기 짝이 있어야 무엇으로 바꾸라는 것인지가 지시문 안에서 닫힌다.
    expect(explainSource).toContain("이렇게 쓰지 마십시오 → 이렇게 쓰십시오:");
  });

  it("gives every AI failure its own sentence and logs the cause", () => {
    // 실패마다 같은 문장을 쓰면 사용자가 할 일을 못 가린다. 키가 없는 서버는
    // 다시 눌러도 안 붙고, 시간 초과는 다시 누르면 붙는다.
    // 문구는 전부 "아래 엔진 결과만 보여드립니다"로 끝난다 — 사용자가 다음에
    // 볼 것을 문장이 직접 말한다. 그 문장이 실패 갈래 수만큼 있고 서로 달라야 한다.
    const notices = [...explainSource.matchAll(/"([^"]*보여드립니다[^"]*)"/g)].map((m) => m[1]);
    expect(notices.length).toBeGreaterThanOrEqual(5);
    expect(new Set(notices).size).toBe(notices.length);
    for (const reason of ["missing_api_key", "invalid_response", "refereed_out"]) {
      expect(explainSource).toMatch(new RegExp(`reason:\\s*"${reason}"`));
    }
    expect(explainSource).toMatch(/console\.warn\("\[otc-explain\] fallback"/);
    // notice 는 화면에 그대로 나간다. 원본 오류 메시지를 넣으면 영어 스택이 보인다.
    expect(explainRouteSource).not.toMatch(/notice:\s*message/);
    expect(explainRouteSource).toMatch(/console\.warn\("\[otc-explain\]/);
  });
});
