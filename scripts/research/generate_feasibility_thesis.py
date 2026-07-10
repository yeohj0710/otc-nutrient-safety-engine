#!/usr/bin/env python3
"""Generate the reduced-scope Korean thesis DOCX from machine-readable artifacts."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2] / "research_v2"
OUT = ROOT / "thesis"
TITLE = "일반의약품형 고함량 영양성분의 안전성 근거 탐색과 추적 가능한 조회 도구의 타당성 연구"
TITLE_EN = "A PubMed Feasibility Study of Traceable Safety Evidence for High-Dose Over-the-Counter Nutrient Ingredients"


def rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def shade(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), fill); tc_pr.append(shd)


def set_cell_text(cell, text: str, bold=False):
    cell.text = ""
    p = cell.paragraphs[0]; r = p.add_run(text); r.bold = bold; r.font.size = Pt(8.5)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def heading(doc: Document, text: str, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.space_before = Pt(12); p.paragraph_format.space_after = Pt(6)
    return p


def para(doc: Document, text: str):
    p = doc.add_paragraph(text)
    p.paragraph_format.first_line_indent = Cm(0.55)
    p.paragraph_format.line_spacing = 1.25
    p.paragraph_format.space_after = Pt(5)
    return p


def page(doc: Document):
    doc.add_page_break()


def main():
    metrics = json.loads((OUT / "metrics_manifest.json").read_text(encoding="utf-8"))["metrics"]
    evidence_map = rows(ROOT / "synthesis" / "abstract_evidence_map.csv")
    evidence = rows(ROOT / "extraction" / "seed_abstract_evidence.csv")
    screening = json.loads((ROOT / "screening" / "computational_screening_summary.json").read_text(encoding="utf-8"))

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.0)
    sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(1.8)
    styles = doc.styles
    styles["Normal"].font.name = "Malgun Gothic"; styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")
    styles["Normal"].font.size = Pt(10)
    for name in ("Title", "Heading 1", "Heading 2"):
        styles[name].font.name = "Malgun Gothic"; styles[name]._element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")
        styles[name].font.color.rgb = RGBColor(25, 35, 55)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("졸업논문 연구 산출물\n"); r.bold = True; r.font.size = Pt(14)
    r = p.add_run("PUBMED 단독 타당성 연구본"); r.bold = True; r.font.size = Pt(11); r.font.color.rgb = RGBColor(190, 70, 55)
    doc.add_paragraph("\n")
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(TITLE); r.bold = True; r.font.size = Pt(18)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(TITLE_EN); r.italic = True; r.font.size = Pt(11)
    doc.add_paragraph("\n\n")
    for line in ["성명  권혁찬", "학번  2021194024", "연세대학교 약학대학", "작성일  2026년 7월 10일"]:
        p = doc.add_paragraph(line); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("\n")
    p = doc.add_paragraph("주의: 본 문서는 PubMed 단독·초록 중심 타당성 연구이다. 다중 데이터베이스 체계적 문헌고찰, 임상 검증 도구 또는 진료 지침으로 해석할 수 없다.")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.runs[0].font.color.rgb = RGBColor(180, 55, 45); p.runs[0].bold = True

    page(doc); heading(doc, "국문초록")
    para(doc, f"본 연구는 일반의약품 또는 보충제 형태로 접할 수 있는 비타민 D, 비타민 B6, 철분, 마그네슘, 아연의 안전성 문헌을 PubMed에서 전량 회수하고, 원문 위치를 추적할 수 있는 규칙 초안을 생성할 수 있는지 평가하였다. 기관 구독 데이터베이스, 이중 선별, 전문 검토와 전문가 평가는 확보되지 않아 연구 범위를 PubMed 단독 타당성 연구로 사전에 축소하였다.")
    para(doc, f"검색식은 5개 임상 노드로 구성하였다. 1차 검색에서 사전 지정 seed 22건 중 15건만 회수되어 누락 문헌의 제목·초록·MeSH를 분석하고 K2–K5 검색식을 개정하였다. 최종 검색은 {metrics['pubmed_occurrences']['value']:,}건의 노드별 occurrence를 전량 export했고, {metrics['duplicates_removed']['value']:,}건을 중복으로 제거하여 {metrics['unique_records']['value']:,}건의 고유 레코드를 얻었다. 개정 검색식은 seed 22건을 모두 회수했다.")
    para(doc, "계산 선별은 최종 포함 판정이 아니라 우선순위 제안으로 제한하였다. 사전 seed 22건의 PubMed 초록에서 연구설계와 안전성 결과 신호를 확인하고 locator를 보존했다. 이 자료로 5개 설명형 규칙을 만들었으나 모두 draft_ai로 유지했으며 released 규칙은 0개였다. 독립 human gold set과 전문가 시나리오가 없어 AI 선별 재현율, 위험 탐지 민감도, critical false negative와 내용타당도는 평가하지 않았다.")
    para(doc, "결론적으로 전량 검색, 해시 계보, 중복 제거, seed 회수 검증과 초록 locator 연결은 재현 가능하게 구현되었다. 반면 전문 수준의 효과 추출, RoB, GRADE, 임상 규칙 출시와 성능 검증은 후속 사람 검토가 필요하다. 따라서 본 결과는 탐색 및 소프트웨어 타당성에 한정된다.")
    para(doc, "주요어: 일반의약품, 영양제, 안전성, PubMed, 비타민 D, 비타민 B6, 철분, 마그네슘, 아연")

    page(doc); heading(doc, "1. 서론")
    para(doc, "고함량 영양성분은 처방 없이 접근하기 쉽지만 제품 간 중복 복용, 장기간 섭취, 기저 신장질환과 같은 조건에서 위해 양상이 달라질 수 있다. 단순한 ‘안전/위험’ 표시는 용량, 기간, 병용과 출처를 숨겨 실제 상담에 필요한 질문을 제공하지 못한다.")
    para(doc, "본 연구는 다섯 성분을 하나의 점수로 합치지 않고 임상 노드로 분리했다. K1은 비타민 D와 고칼슘혈증·고칼슘뇨·결석, K2는 비타민 B6와 감각신경병증, K3는 경구 철분과 위장관 이상반응, K4는 마그네슘과 설사·고마그네슘혈증, K5는 아연과 구리결핍·혈액학적 또는 신경학적 이상을 다뤘다.")
    para(doc, "연구 질문은 두 가지다. 첫째, 각 노드의 PubMed 결과를 상위 N건으로 자르지 않고 전량 회수하며 사전 seed를 놓치지 않을 수 있는가. 둘째, 확인 가능한 초록 locator에서만 안전성 신호를 가져와 출시 전 규칙 초안을 만들고, 확인하지 못한 성능을 명시적으로 비워 둘 수 있는가.")

    heading(doc, "2. 연구 방법")
    heading(doc, "2.1 연구설계와 범위", 2)
    para(doc, "2026년 7월 10일 amendment-001에 따라 PubMed 단독, 단일 연구자·계산 지원, 초록 중심 근거 지도 및 소프트웨어 타당성 연구로 수행했다. 다중 데이터베이스 체계적 문헌고찰, 임상 효과 확정, 진단·치료 권고와 임상 검증 주장은 금지했다.")
    heading(doc, "2.2 검색과 계보", 2)
    para(doc, "각 노드 검색식은 MeSH와 제목·초록 자유어를 조합하고 언어·기간·연구설계 필터를 적용하지 않았다. NCBI E-utilities를 사용해 UID와 XML을 전량 저장했다. 각 원시 파일의 SHA-256, 쿼리 해시, hit·export·import 수를 manifest에 기록하고 세 수가 일치하지 않으면 실행을 실패시켰다.")
    para(doc, "1차 검색의 seed 회수 실패는 오류 S-07로 기록했다. 누락 7건을 PubMed XML에서 직접 진단해 abuse, adverse event, administration, generic ingredient, hyphenated over-the-counter 표현을 보완했다. v0.1 원시는 삭제하지 않고 v0.2를 쿼리 해시별 디렉터리에 저장했다.")
    heading(doc, "2.3 중복 제거와 계산 선별", 2)
    para(doc, "PMID를 우선 키로 사용해 노드 간 occurrence를 고유 레코드로 병합했다. 계산 선별은 명백한 동물 전용, 시험관 전용 또는 소아 전용 표현을 제외 후보로 제안하고, 정보가 부족하면 retain_uncertain으로 남겼다. 어떤 계산 결과도 사람의 최종 포함·제외 판정으로 변환하지 않았다.")
    heading(doc, "2.4 초록 근거와 규칙", 2)
    para(doc, "사전 seed의 제목, 초록, 출판유형과 안전성 용어를 정규화 레코드와 대조했다. 각 근거행은 PMID, PubMed URL, 초록 locator, 전문 미검토, RoB 미평가, GRADE 미평가 상태를 포함했다. 규칙은 질문을 유도하는 informational 수준으로만 작성하고 draft_ai 상태를 유지했다.")

    heading(doc, "3. 연구 결과")
    heading(doc, "3.1 검색과 선별", 2)
    table = doc.add_table(rows=1, cols=5); table.alignment = WD_TABLE_ALIGNMENT.CENTER; table.style = "Table Grid"
    for c, t in zip(table.rows[0].cells, ["노드", "검색 occurrence", "seed", "초록 후보", "최종 사람 판정"]): set_cell_text(c, t, True); shade(c, "DCE6F1")
    node_counts = screening["node_membership_counts"]
    for map_row in evidence_map:
        node = map_row["clinical_node_id"]
        cells = table.add_row().cells
        vals = [node, f"{node_counts[node]:,}", map_row["prespecified_seed_count"], str(json.loads((ROOT / "extraction" / "abstract_evidence_shortlist_summary.json").read_text())["node_counts"][node]), "0"]
        for c, v in zip(cells, vals): set_cell_text(c, v)
    para(doc, f"5개 검색의 합은 {screening['identified_occurrences']:,}건이었다. 노드 간 PMID 중복 {screening['duplicates_removed']:,}건을 제거한 고유 레코드는 {screening['unique_records']:,}건이었다. 계산 제안은 priority_include_candidate {screening['proposal_counts']['priority_include_candidate']:,}건, retain_uncertain {screening['proposal_counts']['retain_uncertain']:,}건, explicit_exclude_candidate {screening['proposal_counts']['explicit_exclude_candidate']:,}건이었다.")
    heading(doc, "3.2 Seed 회수와 오류 교정", 2)
    para(doc, "v0.1의 seed 회수율은 15/22(68.2%)였다. K2 1건, K3 1건, K4 3건, K5 2건이 누락됐다. 누락 문헌별 실패 블록을 수정한 v0.2는 22/22(100%)를 회수했다. 이 값은 검색식의 기술적 점검값이며 held-out AI 선별 재현율이 아니다.")
    heading(doc, "3.3 노드별 초록 근거 지도", 2)
    table = doc.add_table(rows=1, cols=5); table.style = "Table Grid"; table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, t in zip(table.rows[0].cells, ["노드", "초록 확인 seed", "설계 구성", "전문/RoB/GRADE", "합성 상태"]): set_cell_text(c, t, True); shade(c, "DCE6F1")
    for row in evidence_map:
        cells = table.add_row().cells; designs = ", ".join(f"{k} {v}" for k,v in json.loads(row["design_counts_json"]).items())
        vals = [row["clinical_node_id"], row["abstract_verified_count"], designs, "0 / 0 / 0", "설명형 지도"]
        for c,v in zip(cells, vals): set_cell_text(c,v)
    para(doc, "K1은 임상시험 중심, K2는 사례군·검토·과학적 의견, K3는 무작위시험과 체계적 문헌고찰, K4는 사례군·코호트·관점 논문, K5는 사례보고와 검토로 구성됐다. 설계와 결과 정의가 달라 메타분석은 수행하지 않았다.")
    heading(doc, "3.4 규칙 및 성능 상태", 2)
    para(doc, "각 노드에서 복용량·기간·병용·증상을 묻는 규칙 초안 1개씩, 총 5개를 생성했다. 22개 source quote가 PMID와 연결됐으나 전문과 독립 검토가 없으므로 released 규칙은 0개다. AI held-out 선별 재현율, 독립 시나리오 위험 탐지 민감도, critical false negative와 전문가 내용타당도는 모두 not_evaluated다.")

    heading(doc, "4. 고찰")
    para(doc, "가장 중요한 결과는 높은 seed 회수율 자체보다 실패를 숨기지 않고 검색식을 교정한 과정이다. 첫 검색은 고전 문헌의 abuse, 최근 연구의 adverse events, 투약을 뜻하는 administered 또는 receiving, 하이픈이 포함된 over-the-counter를 충분히 포착하지 못했다. 누락 PMID를 직접 검사한 뒤 검색식 버전을 올리자 모든 seed가 회수됐다.")
    para(doc, "K4와 K5에서 generic magnesium 또는 zinc를 추가하자 검색량이 크게 늘었다. 민감도 개선의 대가로 비관련 레코드가 증가할 가능성이 있다. 본 연구는 이를 임의의 top-N 절단으로 해결하지 않고 전량 저장한 뒤 계산 우선순위를 제공했다. 최종 특이도는 사람 판정이 없어 계산할 수 없다.")
    para(doc, "초록 근거 지도는 각 노드에 안전성 신호가 존재함을 보여 주지만, 발생률이나 인과 크기를 확정하지 않는다. 특히 사례보고가 많은 K5는 드문 위해를 발견하는 데 유용하지만 분모가 없어 위험률을 제시할 수 없다. K1과 K3의 임상시험도 용량, 대상자, 추적기간과 결과 정의가 달라 초록만으로 통합할 수 없다.")
    para(doc, "소프트웨어 측면에서는 원시 XML, UID, 쿼리, 해시와 정규화 레코드를 연결해 재현성을 높였다. PubmedBookArticle 28건을 누락한 parser 오류도 export-import 불일치 검사로 발견했다. 반면 규칙 출시는 출처 연결만으로 충분하지 않다. 전문 확인, 독립 추출, RoB, GRADE, 전문가 검토와 독립 시나리오 검증이 선행돼야 한다.")
    heading(doc, "4.1 한계", 2)
    para(doc, "첫째, PubMed 이외의 Embase, CENTRAL, Scopus 등은 검색하지 않았다. 둘째, 사람의 이중 선별과 전문 판정이 없다. 셋째, 초록 정보는 용량·기간·분모·결과 정의가 불완전할 수 있다. 넷째, 검색식 검토자가 독립된 정보전문가가 아니다. 다섯째, 성능 평가용 human gold set과 전문가 시나리오가 없어 임상 성능을 주장할 수 없다.")
    heading(doc, "5. 결론")
    para(doc, "권혁찬 연구용 PubMed 타당성 범위에서 5개 노드의 검색 결과를 전량 회수하고 해시 계보를 보존했다. 검색식 오류를 교정해 사전 seed 22건을 모두 회수했고, 15,890개 고유 레코드와 22개 초록 확인 근거, 5개 비출시 규칙 초안을 생성했다. 결과는 탐색과 구현 가능성을 지지하지만 임상 규칙의 정확도나 안전성을 검증하지 않는다. 다음 단계는 사람의 전문 판정과 독립 검증이며, 완료 전에는 draft_ai 상태를 유지해야 한다.")

    heading(doc, "참고문헌")
    for i, row in enumerate(evidence, 1):
        p = doc.add_paragraph(f"{i}. {row['title']} PubMed PMID: {row['pmid']}. {row['source_url']}")
        p.paragraph_format.left_indent = Cm(0.5); p.paragraph_format.first_line_indent = Cm(-0.5); p.paragraph_format.space_after = Pt(3)

    heading(doc, "부록 A. 재현 명령")
    commands = [
        ".venv-research\\Scripts\\python.exe scripts/research/pubmed_full_retrieval.py",
        ".venv-research\\Scripts\\python.exe scripts/research/build_feasibility_screening.py",
        ".venv-research\\Scripts\\python.exe scripts/research/evaluate_seed_recall.py",
        ".venv-research\\Scripts\\python.exe scripts/research/build_abstract_evidence_shortlist.py",
        ".venv-research\\Scripts\\python.exe scripts/research/build_seed_evidence_map.py",
        ".venv-research\\Scripts\\python.exe scripts/research/build_draft_abstract_rules.py",
        ".venv-research\\Scripts\\python.exe -m pytest tests/research_v2 -q",
    ]
    for command in commands:
        p = doc.add_paragraph(command); p.style = doc.styles["Normal"]; p.paragraph_format.left_indent = Cm(0.5)
        for run in p.runs: run.font.name = "Consolas"; run.font.size = Pt(8)
    heading(doc, "부록 B. 공식 미평가 항목")
    for key in ["ai_screening_heldout_recall", "scenario_hazard_sensitivity", "critical_false_negatives", "expert_content_validity"]:
        item = metrics[key]; doc.add_paragraph(f"• {key}: {item['status']} — {item['note']}")

    for section in doc.sections:
        footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run("- ")
        fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE"); footer._p.append(fld); footer.add_run(" -")
    out = OUT / "권혁찬_졸업논문_PubMed_타당성연구.docx"
    doc.save(out)
    print(json.dumps({"docx": str(out), "evidence_references": len(evidence)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
