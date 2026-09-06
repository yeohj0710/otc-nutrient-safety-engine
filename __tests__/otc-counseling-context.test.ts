import { describe, expect, it } from "vitest";
import data from "@/src/generated/otc-runtime.json";
import { parseOtcExplainInput } from "@/src/lib/ai/otc-explain-input";
import { buildOtcCounselingContext, validateOtcDiscussion } from "@/src/lib/ai/otc-counseling-context";

const request = {
  selected: [{ productId: data.products[0].productId, unitsPerDose: 2, dosesPerDay: 3 }],
  profile: { ageYears: 68, kidneyDisease: true, medications: ["와파린"], redFlagSymptoms: [] },
  evaluation: { findings: [{ ruleId: "invented", detailKo: "임의의 판정" }] },
};
describe("서버 원자료로 만드는 개인별 상담", () => {
  it("복용 횟수 초과 설명에 허가 기준과 계산값, 출처를 전달한다", () => {
    const input=parseOtcExplainInput({selected:[{productId:"MFDS-201110646",unitsPerDose:1,dosesPerDay:5}],profile:{ageYears:35,medications:[],redFlagSymptoms:[]}})!;
    const context=buildOtcCounselingContext(input.evaluation,input.selected,input.profile);
    const row=context.evidence.find(item=>item.calculation.reference===4 && item.calculation.amount===5)!;
    expect(row).toBeDefined();
    expect(row.calculation.sources.length).toBeGreaterThan(0);
    expect(validateOtcDiscussion([{ruleId:row.ruleId,pmids:[],text:"입력한 하루 5회는 허가 기준인 하루 4회를 초과합니다."}],context)).toEqual([]);
  });
  it("배경 문헌은 환자에 대한 직접 검증으로 표현하지 않는다", () => {
    const context={patient:null,productUse:[],evidence:[{ruleId:"rule",authorization:[],papers:[{pmid:"123",relation:"background",quote:"",finding:"",limitation:"대상이 다릅니다."}]}]} as unknown as Parameters<typeof validateOtcDiscussion>[1];
    expect(validateOtcDiscussion([{ruleId:"rule",pmids:["123"],text:"이 환자의 출혈 위험을 직접 확인했습니다."}],context)).toContain("background_overreach");
    expect(validateOtcDiscussion([{ruleId:"rule",pmids:["123"],text:"출혈 위험이 증가했습니다."}],context)).toContain("missing_background_limit");
    expect(validateOtcDiscussion([{ruleId:"rule",pmids:["123"],text:"배경 문헌으로, 연구 대상이 달라 입력한 환자에게 직접 적용할 수 없습니다."}],context)).toEqual([]);
  });
  it("클라이언트 판정문을 무시하고 실제 제품, 복용량, 환자 조건을 전달한다", () => {
    const input = parseOtcExplainInput(request)!;
    expect(input.evaluation.findings.some(row => row.ruleId === "invented")).toBe(false);
    const context = buildOtcCounselingContext(input.evaluation, input.selected, input.profile);
    expect(context.patient?.medications).toEqual(["와파린"]);
    expect(context.productUse[0].unitsPerDose).toBe(2);
    expect(context.productUse[0].ingredients).toEqual(data.products[0].ingredients);
  });
  it("목록에 없는 제품, 중복 제품, 잘못된 환자 정보를 거부한다", () => {
    expect(parseOtcExplainInput({ ...request, selected: [{ ...request.selected[0], productId: "invented" }] })).toBeNull();
    expect(parseOtcExplainInput({ ...request, selected: [...request.selected, ...request.selected] })).toBeNull();
    expect(parseOtcExplainInput({ ...request, profile: { ...request.profile, kidneyDisease: "false" } })).toBeNull();
  });
  it("연결되지 않은 논문이나 새 수치를 상담 근거로 쓸 수 없다", () => {
    const context = { patient: null, productUse: [], evidence: [{ ruleId: "rule", context: { products: [], ingredients: [] }, authorization: [], papers: [{ pmid: "123", title: "trial", studyDesign: "RCT", relation: "direct", quote: "5 mg reduced symptoms", finding: "", limitation: "", url: "https://pubmed.ncbi.nlm.nih.gov/123/" }] }] };
    // 이 검사는 문헌의 문장과 인용 번호의 연결만 다룬다.
    const typed = context as unknown as Parameters<typeof validateOtcDiscussion>[1];
    expect(validateOtcDiscussion([{ text: "5 mg 연구입니다.", ruleId: "rule", pmids: ["999"] }], typed)).toContain("unknown_paper");
    expect(validateOtcDiscussion([{ text: "50 mg 연구입니다.", ruleId: "rule", pmids: ["123"] }], typed)).toContain("unsupported_number");
    expect(validateOtcDiscussion([{ text: "5 mg 연구입니다.", ruleId: "rule", pmids: ["123"] }], typed)).toEqual([]);
    expect(validateOtcDiscussion([{ text: "5 g 연구입니다.", ruleId: "rule", pmids: ["123"] }], typed)).toContain("unsupported_unit");
  });
});
