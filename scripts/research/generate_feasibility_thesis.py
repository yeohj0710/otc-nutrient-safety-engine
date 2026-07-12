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
TITLE = "고함량 영양성분의 안전성 근거 검토와 개인맞춤형 정보제공 도구의 개발"
TITLE_EN = "Safety Evidence Review of High-Dose Nutrients and Development of a Personalized Information Tool"


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
    r = p.add_run("졸 업 논 문"); r.bold = True; r.font.size = Pt(18)
    doc.add_paragraph("")
    cover = doc.add_table(rows=8, cols=2); cover.style = "Table Grid"; cover.alignment = WD_TABLE_ALIGNMENT.CENTER
    cover_data = [
        ("연구 주제명", f"국문: {TITLE}\n영문: {TITLE_EN}"),
        ("성 명", "권혁찬"), ("학 번", "2021194024"),
        ("실습기간", "2026년 3월 3일 ~ 2026년 6월 19일"),
        ("실습장소", "연세대학교 약학대학"), ("논문양식", "종설논문"),
        ("담당교수", "장민정 교수님  (서명)"), ("제출일", "2026년 6월"),
    ]
    for row, (label, value) in zip(cover.rows, cover_data):
        set_cell_text(row.cells[0], label, True); set_cell_text(row.cells[1], value)
        shade(row.cells[0], "E7E6E6")
    doc.add_paragraph("")
    p = doc.add_paragraph("연세대학교 약학대학 전공심화실습(1)"); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].bold = True; p.runs[0].font.size = Pt(12)

    page(doc); heading(doc, "국문초록")
    para(doc, f"본 연구는 일반의약품 및 건강기능식품으로 접하기 쉬운 비타민 D, 비타민 B6, 철분, 마그네슘 및 아연을 대상으로 안전성 근거를 검토하고, 복용자의 상태에 따라 확인해야 할 정보를 제시하는 조회 도구를 개발하고자 수행하였다. 문헌검색은 PubMed를 이용하였으며, 각 성분에서 임상적으로 문제가 될 수 있는 이상반응과 위험요인을 중심으로 검색식을 구성하였다.")
    para(doc, f"다섯 성분의 검색 결과는 모두 {metrics['pubmed_occurrences']['value']:,}건이었고, 성분 간 중복 문헌 {metrics['duplicates_removed']['value']:,}건을 제외한 뒤 {metrics['unique_records']['value']:,}건을 분석 자료로 정리하였다. 검색식의 누락 여부를 확인하기 위해 미리 선정한 핵심문헌 22편의 회수 여부를 평가하였다. 최초 검색에서는 15편이 확인되었으나 누락 원인을 분석해 검색어를 보완한 뒤 22편을 모두 회수하였다.")
    para(doc, "핵심문헌의 초록을 검토한 결과, 비타민 D에서는 고칼슘혈증·고칼슘뇨·요로결석, 비타민 B6에서는 감각신경병증, 철분에서는 위장관 이상반응, 마그네슘에서는 설사와 고마그네슘혈증, 아연에서는 구리결핍에 따른 혈액학적·신경학적 이상이 주요 안전성 문제로 확인되었다. 이를 바탕으로 성분별 복용량, 복용기간, 병용제품, 기저질환 및 증상을 확인하는 정보제공 문안을 작성하였다.")
    para(doc, "본 연구는 안전성 문헌을 성분별 상담 질문과 연결했다는 점에서 의의가 있다. 다만 PubMed 이외의 데이터베이스 검색과 독립적인 전문 검토를 시행하지 않았으므로, 개발한 문안은 약사의 판단을 보조하는 연구용 자료로 사용되어야 한다.")
    para(doc, "주요어: 일반의약품, 영양제, 안전성, PubMed, 비타민 D, 비타민 B6, 철분, 마그네슘, 아연")

    heading(doc, "영문초록")
    para(doc, "This study reviewed safety evidence for vitamin D, vitamin B6, oral iron, magnesium, and zinc and developed a personalized information tool. Five PubMed searches identified 16,194 records in total, and 15,890 unique records remained after removal of 304 duplicates. Search terms were revised after an initial check retrieved 15 of 22 prespecified key articles; the revised searches retrieved all 22 articles. Major safety concerns were hypercalcemia and urinary stones for vitamin D, sensory neuropathy for vitamin B6, gastrointestinal adverse events for oral iron, diarrhea and hypermagnesemia for magnesium, and copper-deficiency-related hematologic and neurologic abnormalities for zinc. The resulting information statements prompt users to confirm dose, duration, concurrent products, underlying disease, and relevant symptoms. The tool is intended to support, not replace, professional judgment.")
    para(doc, "Keywords: over-the-counter products, dietary supplements, safety, PubMed, evidence traceability")

    page(doc); heading(doc, "목차")
    for item in ["국문초록", "영문초록", "1. 서론", "2. 연구 방법", "  2.1 연구설계와 범위", "  2.2 검색과 계보", "  2.3 중복 제거와 계산 선별", "  2.4 초록 근거와 규칙", "3. 연구 결과", "4. 고찰", "5. 결론", "6. 참고문헌", "부록"]:
        doc.add_paragraph(item)

    page(doc); heading(doc, "1. 서론")
    para(doc, "비타민과 무기질 보충제는 처방전 없이 구입할 수 있어 비교적 안전한 제품으로 인식되기 쉽다. 그러나 같은 성분을 여러 제품으로 복용하거나 고함량 제품을 장기간 사용하는 경우에는 이상반응이 나타날 수 있다. 특히 신기능 저하, 결석 병력, 빈혈 또는 신경학적 증상이 있는 복용자에서는 제품명만으로 안전성을 판단하기 어렵다.")
    para(doc, "영양성분의 안전성은 성분의 유무보다 실제 섭취량과 기간, 병용제품 및 복용자의 임상적 특성에 의해 달라진다. 비타민 D의 과량 섭취는 칼슘대사 이상과 결석 위험을, 비타민 B6의 장기 복용은 감각신경병증을 일으킬 수 있다. 철분은 위장관 이상반응이 흔하고, 마그네슘은 신기능이 저하된 환자에서 축적될 수 있으며, 아연의 과량 섭취는 구리 흡수를 방해할 수 있다.")
    para(doc, "따라서 영양성분 상담에서는 단순히 복용 가능 여부를 답하기보다 제품별 함량을 합산하고, 복용기간과 위험요인을 확인하며, 판단의 근거가 되는 문헌을 함께 제시할 필요가 있다. 본 연구의 목적은 다섯 영양성분의 주요 안전성 근거를 정리하고, 이를 실제 상담에서 확인할 질문으로 전환한 개인맞춤형 정보제공 도구를 개발하는 것이다.")

    heading(doc, "2. 연구 방법")
    heading(doc, "2.1 연구설계와 범위", 2)
    para(doc, "본 연구는 문헌고찰과 정보제공 도구 개발을 결합한 탐색적 연구로 수행하였다. 연구대상 성분은 비타민 D, 비타민 B6, 철분, 마그네슘 및 아연으로 정하였다. 각 성분에서 용량 또는 장기 복용과 관련성이 알려진 안전성 결과를 별도의 연구주제로 설정하였다.")
    heading(doc, "2.2 검색과 계보", 2)
    para(doc, "각 노드 검색식은 MeSH와 제목·초록 자유어를 조합하고 언어·기간·연구설계 필터를 적용하지 않았다. NCBI E-utilities를 사용해 UID와 XML을 전량 저장했다. 각 원시 파일의 SHA-256, 쿼리 해시, hit·export·import 수를 manifest에 기록하고 세 수가 일치하지 않으면 실행을 실패시켰다.")
    para(doc, "검색식의 민감도를 점검하기 위해 연구 시작 전에 성분별 핵심문헌 22편을 선정하였다. 최초 검색에서 확인되지 않은 7편은 제목, 초록 및 MeSH 용어를 다시 검토하였다. 그 결과 과량복용, 이상반응, 투여 및 일반 성분명을 나타내는 표현이 충분히 포함되지 않은 것으로 확인되어 검색어를 보완한 뒤 다시 검색하였다.")
    heading(doc, "2.3 중복 제거와 계산 선별", 2)
    para(doc, "검색 결과는 PMID를 기준으로 중복을 제거하였다. 제목과 초록에 동물실험, 시험관 연구 또는 소아 연구임이 명확하게 제시된 문헌은 우선순위를 낮추었고, 성인에서 경구로 섭취한 영양성분의 이상반응을 다룬 연구를 우선 검토 대상으로 분류하였다. 정보가 충분하지 않은 문헌은 임의로 제외하지 않았다.")
    heading(doc, "2.4 초록 근거와 규칙", 2)
    para(doc, "핵심문헌에서 연구설계, 대상 성분, 주요 안전성 결과와 근거 문장을 추출하였다. 추출한 내용은 PubMed PMID 및 원문 연결주소와 함께 저장하였다. 이후 성분별로 복용자에게 확인할 항목과 상담 시 설명할 내용을 작성하였다. 전문 확인이 끝나지 않은 내용은 확정적인 인과관계나 치료 권고로 표현하지 않았다.")

    heading(doc, "3. 연구 결과")
    heading(doc, "3.1 검색과 선별", 2)
    table = doc.add_table(rows=1, cols=5); table.alignment = WD_TABLE_ALIGNMENT.CENTER; table.style = "Table Grid"
    for c, t in zip(table.rows[0].cells, ["성분", "검색 문헌 수", "핵심문헌", "우선 검토 문헌", "전문 검토"]): set_cell_text(c, t, True); shade(c, "DCE6F1")
    node_counts = screening["node_membership_counts"]
    node_labels = {"K1": "비타민 D", "K2": "비타민 B6", "K3": "철분", "K4": "마그네슘", "K5": "아연"}
    design_labels = {"clinical_trial": "임상시험", "randomized_controlled_trial": "무작위배정시험", "case_series": "증례군", "scientific_opinion": "과학적 의견서", "systematic_review": "체계적 문헌고찰", "systematic_review_meta_analysis": "체계적 문헌고찰·메타분석", "cohort": "코호트 연구", "perspective_with_structured_review": "서술적 고찰", "case_report": "증례보고", "review": "종설"}
    for map_row in evidence_map:
        node = map_row["clinical_node_id"]
        cells = table.add_row().cells
        vals = [node_labels[node], f"{node_counts[node]:,}", map_row["prespecified_seed_count"], str(json.loads((ROOT / "extraction" / "abstract_evidence_shortlist_summary.json").read_text())["node_counts"][node]), "미시행"]
        for c, v in zip(cells, vals): set_cell_text(c, v)
    para(doc, f"다섯 성분의 검색 건수는 모두 {screening['identified_occurrences']:,}건이었다. 성분 간 PMID 중복 {screening['duplicates_removed']:,}건을 제외한 고유 문헌은 {screening['unique_records']:,}건이었다. 제목과 초록을 이용한 우선순위 분류에서 {screening['proposal_counts']['priority_include_candidate']:,}건을 우선 검토 대상으로, {screening['proposal_counts']['retain_uncertain']:,}건을 추가 확인 대상으로 분류하였다. 연구범위에서 명백히 벗어난 것으로 판단된 문헌은 {screening['proposal_counts']['explicit_exclude_candidate']:,}건이었다.")
    heading(doc, "3.2 핵심문헌 회수율", 2)
    para(doc, "최초 검색에서는 핵심문헌 22편 중 15편이 확인되어 회수율은 68.2%였다. 비타민 B6와 철분에서 각각 1편, 마그네슘에서 3편, 아연에서 2편이 누락되었다. 누락 문헌에 사용된 표현을 반영해 검색식을 수정한 결과 22편이 모두 검색되어 최종 회수율은 100%였다.")
    page(doc); heading(doc, "3.3 성분별 안전성 근거", 2)
    table = doc.add_table(rows=1, cols=5); table.style = "Table Grid"; table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, t in zip(table.rows[0].cells, ["성분", "확인 문헌", "주요 연구설계", "전문 확인", "근거 정리 방식"]): set_cell_text(c, t, True); shade(c, "DCE6F1")
    for row in evidence_map:
        cells = table.add_row().cells; designs = ", ".join(f"{design_labels.get(k, k)} {v}편" for k,v in json.loads(row["design_counts_json"]).items())
        vals = [node_labels[row["clinical_node_id"]], row["abstract_verified_count"], designs, "미시행", "서술적 정리"]
        for c,v in zip(cells, vals): set_cell_text(c,v)
    para(doc, "K1은 임상시험 중심, K2는 사례군·검토·과학적 의견, K3는 무작위시험과 체계적 문헌고찰, K4는 사례군·코호트·관점 논문, K5는 사례보고와 검토로 구성됐다. 설계와 결과 정의가 달라 메타분석은 수행하지 않았다.")
    heading(doc, "3.4 정보제공 도구의 구성", 2)
    para(doc, "조회 도구는 성분별로 복용량, 복용기간, 병용제품, 기저질환 및 현재 증상을 확인하도록 구성하였다. 비타민 D에서는 칼슘 병용과 결석 병력, 비타민 B6에서는 여러 제품의 중복 섭취와 감각 이상, 철분에서는 제제와 복용 횟수 및 위장관 증상, 마그네슘에서는 신기능과 설사·저혈압·의식 변화, 아연에서는 장기 복용과 빈혈·보행 이상을 주요 확인 항목으로 제시하였다. 모든 문안에는 근거가 된 PubMed 문헌을 연결하였다.")

    heading(doc, "4. 고찰")
    para(doc, "본 연구에서는 고함량 영양성분의 안전성 문제를 성분별로 구분하고, 문헌에서 확인된 위해를 실제 상담 질문으로 연결하였다. 검색식 보완 전에는 오래된 증례보고나 최근에 색인된 문헌이 누락되었으나, 누락 문헌의 표현을 직접 확인하여 검색어를 수정함으로써 사전에 선정한 핵심문헌을 모두 회수할 수 있었다.")
    para(doc, "마그네슘과 아연 검색에서는 구체적인 제형명뿐 아니라 일반 성분명을 포함한 뒤 검색량이 증가하였다. 이는 관련 문헌을 놓칠 가능성을 줄이는 대신 검토해야 할 비관련 문헌도 늘어날 수 있음을 의미한다. 본 연구에서는 검색 결과의 일부만 선택하지 않고 전체 결과를 보존한 뒤, 연구대상과 노출 및 안전성 결과가 명확한 문헌부터 검토하였다.")
    para(doc, "초록 근거 지도는 각 노드에 안전성 신호가 존재함을 보여 주지만, 발생률이나 인과 크기를 확정하지 않는다. 특히 사례보고가 많은 K5는 드문 위해를 발견하는 데 유용하지만 분모가 없어 위험률을 제시할 수 없다. K1과 K3의 임상시험도 용량, 대상자, 추적기간과 결과 정의가 달라 초록만으로 통합할 수 없다.")
    para(doc, "조회 도구의 장점은 안전성 문안을 근거문헌과 직접 연결하고, 새로운 문헌이 추가될 때 출처를 다시 확인할 수 있다는 점이다. 그러나 출처가 연결되어 있다는 사실만으로 문안의 임상적 타당성이 보장되는 것은 아니다. 실제 상담에 적용하려면 전문 검토와 약사 평가를 거쳐 표현의 정확성과 위해 누락 여부를 확인해야 한다.")
    heading(doc, "4.1 한계", 2)
    para(doc, "첫째, PubMed 이외의 Embase, CENTRAL, Scopus 등은 검색하지 않았다. 둘째, 사람의 이중 선별과 전문 판정이 없다. 셋째, 초록 정보는 용량·기간·분모·결과 정의가 불완전할 수 있다. 넷째, 검색식 검토자가 독립된 정보전문가가 아니다. 다섯째, 성능 평가용 human gold set과 전문가 시나리오가 없어 임상 성능을 주장할 수 없다.")
    heading(doc, "5. 결론")
    para(doc, "본 연구는 비타민 D, 비타민 B6, 철분, 마그네슘 및 아연의 주요 안전성 문제를 문헌에 근거하여 정리하고, 복용량과 기간, 병용제품, 기저질환 및 증상을 확인하는 개인맞춤형 정보제공 도구를 개발하였다. 수정한 검색식은 사전에 선정한 핵심문헌 22편을 모두 회수하였으며, 각 안전성 문안은 근거문헌과 연결되었다. 향후 전문 검토와 독립적인 사례 평가를 통해 문안의 정확성과 상담 활용성을 확인할 필요가 있다.")

    heading(doc, "6. 참고문헌")
    for i, row in enumerate(evidence, 1):
        p = doc.add_paragraph(f"{i}. {row['title']} PubMed PMID: {row['pmid']}. {row['source_url']}")
        p.paragraph_format.left_indent = Cm(0.5); p.paragraph_format.first_line_indent = Cm(-0.5); p.paragraph_format.space_after = Pt(3)

    heading(doc, "부록. 성분별 상담 확인 항목")
    for text_value in ["비타민 D: 총 섭취량, 칼슘 병용, 결석 병력, 고칼슘혈증 관련 증상", "비타민 B6: 복수 제품의 중복 섭취, 복용기간, 저림·감각저하·보행 이상", "철분: 제제명, 1일 복용 횟수, 치료 목적, 오심·변비·설사·복통", "마그네슘: 제제와 용량, 신기능, 설사, 저혈압·서맥·의식 변화", "아연: 용량과 복용기간, 빈혈·호중구감소증, 감각 또는 보행 이상"]:
        doc.add_paragraph(text_value, style="List Bullet")

    for section in doc.sections:
        footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run("- ")
        fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE"); footer._p.append(fld); footer.add_run(" -")
    out = OUT / "권혁찬_졸업논문_전면개작_최종본.docx"
    doc.save(out)
    print(json.dumps({"docx": str(out), "evidence_references": len(evidence)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
