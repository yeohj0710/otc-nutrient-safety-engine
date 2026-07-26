from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
PICOS_PATH = ROOT / "research_v3/otc/literature/picos/picos_definition.json"
EVIDENCE_PATH = ROOT / "research_v3/otc/literature/evidence_map.csv"
SCREENING_PATH = ROOT / "research_v3/otc/literature/screening/screening_manifest.json"
OTC_METRICS_PATH = ROOT / "research_v3/otc/metrics_manifest.json"
ROOT_METRICS_PATH = ROOT / "research_v3/metrics_manifest.json"
THESIS_DIR = ROOT / "research_v3/thesis"
THESIS_DOCX = THESIS_DIR / "권혁찬_졸업논문_최종본.docx"
REPORTS_DIR = ROOT / "research_v3/reports"

FONT_BODY = "Pretendard"
FONT_LIGHT = "Pretendard Light"
FONT_MEDIUM = "Pretendard Medium"
FONT_SEMIBOLD = "Pretendard SemiBold"
FONT_EXTRABOLD = "Pretendard ExtraBold"
NAVY = RGBColor(18, 43, 67)
BLUE = RGBColor(38, 94, 139)
MUTED = RGBColor(92, 105, 117)
LIGHT_FILL = "EEF3F7"
CAUTION_FILL = "FFF4D6"
TABLE_WIDTH_DXA = 9000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_metrics() -> dict[str, Any]:
    picos = read_json(PICOS_PATH)
    evidence = read_csv(EVIDENCE_PATH)
    screening = read_json(SCREENING_PATH)
    otc = read_json(OTC_METRICS_PATH)
    metrics = otc["metrics"]
    return {
        "products": metrics["analysis_products"]["value"],
        "ingredients": metrics["analysis_ingredients"]["value"],
        "bindings": metrics["runtime_product_ingredient_bindings"]["value"],
        "constraints": metrics["verified_administration_constraints"]["value"],
        "rules_total": metrics["rules_total"]["value"],
        "rules_released": metrics["rules_released"]["value"],
        "questions": len(picos["questions"]),
        "question_rows": [
            {
                "id": question["question_id"],
                "title": question["title_ko"],
                "hits": question.get("observed_hit_count"),
            }
            for question in picos["questions"]
        ],
        "search_hits": picos["last_search"]["total_hits_before_deduplication"],
        "corpus_rows": len(evidence),
        "with_abstract": sum(row["has_abstract"] == "true" for row in evidence),
        "title_only": sum(row["has_abstract"] != "true" for row in evidence),
        "screened": screening["classified_rows"],
        "coverage": screening["coverage"],
        "decision_distribution": screening["decision_distribution"],
        "screening_prompt_sha256": screening["prompt_sha256"],
        "corpus_sha256": screening["input_sha256"],
        "model_id": screening["model"]["id"],
        "model_revision": screening["model"]["revision"],
        "screening_complete": screening["run_complete"],
        "screening_partial_reason": screening["partial_reason"],
    }


def set_run_font(run, family: str, size: float, color: RGBColor | None = None) -> None:
    run.font.name = family
    run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), family)


def configure_style(style, family: str, size: float, color: RGBColor | None = None) -> None:
    style.font.name = family
    style.font.size = Pt(size)
    if color is not None:
        style.font.color.rgb = color
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), family)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run()
    set_run_font(run, FONT_LIGHT, 9, MUTED)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, end])


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), fill)


def set_cell_margins(cell, top: int = 100, start: int = 120, bottom: int = 100, end: int = 120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths: list[int]) -> None:
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    width = tbl_pr.first_child_found_in("w:tblW")
    if width is None:
        width = OxmlElement("w:tblW")
        tbl_pr.append(width)
    width.set(qn("w:w"), str(sum(widths)))
    width.set(qn("w:type"), "dxa")
    indent = tbl_pr.first_child_found_in("w:tblInd")
    if indent is None:
        indent = OxmlElement("w:tblInd")
        tbl_pr.append(indent)
    indent.set(qn("w:w"), "120")
    indent.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for value in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(value))
        grid.append(col)
    for row in table.rows:
        tr_pr = row._tr.get_or_add_trPr()
        if tr_pr.find(qn("w:cantSplit")) is None:
            tr_pr.append(OxmlElement("w:cantSplit"))
        for index, cell in enumerate(row.cells):
            cell.width = Inches(widths[index] / 1440)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            tc_w = cell._tc.get_or_add_tcPr().first_child_found_in("w:tcW")
            tc_w.set(qn("w:w"), str(widths[index]))
            tc_w.set(qn("w:type"), "dxa")


def set_paragraph_font(paragraph, family: str = FONT_BODY, size: float = 10.5) -> None:
    for run in paragraph.runs:
        set_run_font(run, family, size)


def add_body(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph(text)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_after = Pt(8)
    paragraph.paragraph_format.line_spacing = 1.45
    set_paragraph_font(paragraph)


def add_note(doc: Document, label: str, text: str, fill: str = CAUTION_FILL) -> None:
    table = doc.add_table(rows=1, cols=1)
    set_table_geometry(table, [TABLE_WIDTH_DXA])
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(f"{label} ")
    set_run_font(run, FONT_SEMIBOLD, 10.5, NAVY)
    run = paragraph.add_run(text)
    set_run_font(run, FONT_BODY, 10.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_metric_table(doc: Document, rows: list[tuple[str, str, str]]) -> None:
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    set_table_geometry(table, [2500, 1800, 4700])
    headers = ["항목", "값", "해석"]
    for index, value in enumerate(headers):
        cell = table.rows[0].cells[index]
        set_cell_shading(cell, LIGHT_FILL)
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(value)
        set_run_font(run, FONT_SEMIBOLD, 9.5, NAVY)
    for label, value, meaning in rows:
        cells = table.add_row().cells
        for index, text in enumerate((label, value, meaning)):
            paragraph = cells[index].paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if index == 1 else WD_ALIGN_PARAGRAPH.LEFT
            run = paragraph.add_run(text)
            set_run_font(run, FONT_BODY if index else FONT_MEDIUM, 9.3)
    set_table_geometry(table, [2500, 1800, 4700])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def build_thesis(metrics: dict[str, Any]) -> None:
    THESIS_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.4)
    section.bottom_margin = Cm(2.4)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)
    section.header_distance = Cm(1.25)
    section.footer_distance = Cm(1.25)

    styles = doc.styles
    configure_style(styles["Normal"], FONT_BODY, 10.5)
    for name, family, size, color, before, after in (
        ("Title", FONT_EXTRABOLD, 24, NAVY, 0, 12),
        ("Subtitle", FONT_MEDIUM, 12, MUTED, 0, 8),
        ("Heading 1", FONT_SEMIBOLD, 16, BLUE, 18, 10),
        ("Heading 2", FONT_MEDIUM, 13, NAVY, 12, 6),
        ("Heading 3", FONT_MEDIUM, 11.5, NAVY, 8, 4),
    ):
        configure_style(styles[name], family, size, color)
        styles[name].paragraph_format.space_before = Pt(before)
        styles[name].paragraph_format.space_after = Pt(after)
        styles[name].paragraph_format.keep_with_next = True

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = header.add_run("연세대학교 약학대학 | 권혁찬 졸업논문")
    set_run_font(run, FONT_LIGHT, 8.5, MUTED)
    add_page_number(section.footer.paragraphs[0])

    cover = doc.add_paragraph()
    cover.paragraph_format.space_before = Pt(86)
    cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cover.add_run("졸업논문")
    set_run_font(run, FONT_MEDIUM, 11, BLUE)
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(18)
    title.paragraph_format.space_after = Pt(18)
    run = title.add_run("식약처 허가원문 기반 국내 일반의약품\n안전성 조회 시스템과 AI 자율 문헌 근거층 구축")
    set_run_font(run, FONT_EXTRABOLD, 24, NAVY)
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("v4.0 부분 실행 보고")
    set_run_font(run, FONT_MEDIUM, 13, MUTED)
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.paragraph_format.space_before = Pt(76)
    run = meta.add_run("연세대학교 약학대학\n2021194024 권혁찬\n2026년 7월")
    set_run_font(run, FONT_MEDIUM, 11, NAVY)
    doc.add_page_break()

    doc.add_heading("초록", level=1)
    add_note(
        doc,
        "현재 상태",
        f"PubMed 코퍼스 {metrics['corpus_rows']:,}행 중 {metrics['screened']:,}행만 AI 선별을 마쳤다. "
        "AI 참조표준과 규칙엔진 맹검평가는 실행하지 않았으므로 연구 상태는 complete=false다.",
    )
    add_body(
        doc,
        f"이 연구는 국내 일반의약품을 제품명으로 입력하면 중복 성분, 최대용량, 복용 간격, 연령, 질환, 병용약 위험 신호를 허가원문과 함께 보여 주는 조회 시스템을 다룬다. "
        f"결정론적 허가원문 층에는 분석 제품 {metrics['products']}개, 고유 성분 {metrics['ingredients']}개, 제품-성분 연결 {metrics['bindings']}개, 복용 조건 {metrics['constraints']}개가 포함된다. "
        "문헌은 이 판정을 대신하지 않고 위해 연관성을 설명하는 별도 참고 근거층으로 설계했다."
    )
    add_body(
        doc,
        f"AI는 허가원문에서 확인한 성분과 규칙 범위를 입력받아 PICOS 질문 {metrics['questions']}개를 만들고 PubMed를 검색했다. "
        f"검색 결과는 질문 합계 {metrics['search_hits']:,}건이었고, 중복 제거 뒤 PMID {metrics['corpus_rows']:,}개를 확보했다. "
        f"초록 보유 문헌은 {metrics['with_abstract']:,}개, 제목만 있는 문헌은 {metrics['title_only']:,}개였다."
    )
    add_body(
        doc,
        f"로컬 AI 모델은 전체 중 {metrics['screened']:,}행을 판정했다. 커버리지는 {metrics['coverage'] * 100:.2f}%이며, retain {metrics['decision_distribution'].get('retain', 0)}건, "
        f"deprioritize {metrics['decision_distribution'].get('deprioritize', 0)}건, uncertain {metrics['decision_distribution'].get('uncertain', 0)}건이었다. "
        "전체 선별, AI 참조표준 채점, 규칙엔진 맹검 독립평가가 끝나지 않았으므로 민감도·특이도·F1 또는 성능 주장을 제시하지 않는다."
    )
    add_body(
        doc,
        "핵심어: 일반의약품, 식약처 허가원문, 제품명 기반 조회, PubMed, AI 문헌 선별, 계보 분리"
    )

    doc.add_heading("1. 서론", level=1)
    doc.add_heading("1.1 제품명으로 시작하는 안전성 질문", level=2)
    add_body(
        doc,
        "사람은 약을 성분명보다 제품명으로 기억한다. 하지만 같은 성분이 여러 감기약과 해열진통제에 들어가면 제품명만 보고 중복을 알아차리기 어렵다. 이 연구는 제품명을 입력점으로 삼고, 제품에서 성분으로, 성분에서 허가된 용량과 주의사항으로 거슬러 올라가는 구조를 택했다."
    )
    doc.add_heading("1.2 사실과 근거를 섞지 않는 이유", level=2)
    add_body(
        doc,
        "‘이 조합이 허가된 1일 최대량을 넘는다’는 말은 허가원문과 산술로 확인하는 사실 주장이다. 반면 ‘과량 복용이 간손상과 연관된다’는 말은 문헌이 뒷받침하는 근거 주장이다. 이 연구는 두 문장을 한 권한 체계로 합치지 않는다. 허가원문은 판정을 내리고, PubMed 문헌은 판정의 배경을 설명한다."
    )

    doc.add_heading("2. 연구 방법", level=1)
    doc.add_heading("2.1 허가원문 결정층", level=2)
    add_body(
        doc,
        f"식약처 의약품상세정보의 제품·원료약품·용법용량·사용상의주의사항을 구조화했다. 분석 집합은 제품 {metrics['products']}개와 고유 성분 {metrics['ingredients']}개다. "
        f"계산에 사용하는 제품-성분 연결은 {metrics['bindings']}개이며 복용 조건은 {metrics['constraints']}개다. released 규칙은 {metrics['rules_released']}개, 전체 규칙은 {metrics['rules_total']}개다."
    )
    doc.add_heading("2.2 AI 자율 PICOS와 PubMed 검색", level=2)
    add_body(
        doc,
        "AI에는 28개 성분, 16개 규칙의 유형과 범위, PubMed 단일 자료원이라는 제약만 제공했다. 이전 영양성분 검색식이나 결과 수치는 제공하지 않았다. AI는 아세트아미노펜, NSAID, 감기·알레르기 복합성분, 소화제 복합성분, 외용 진통성분의 다섯 질문으로 묶었다. 각 질문에는 대상, 노출, 비교, 결과, 연구설계와 MeSH·제목/초록 검색어를 기록했다."
    )
    question_rows = [(row["title"], f"{row['hits']:,}" if row["hits"] is not None else "null", row["id"]) for row in metrics["question_rows"]]
    add_metric_table(doc, [(title, hits, qid) for title, hits, qid in question_rows])
    doc.add_heading("2.3 원시 응답과 코퍼스 계보", level=2)
    add_body(
        doc,
        "NCBI E-utilities는 API 키 없이 초당 세 번 이하로 호출했다. ESearch로 질문별 건수를 먼저 확인했고, 전체 상한을 넘긴 첫 검색은 EFetch 전에 중단했다. 좁힌 검색식으로 다시 실행한 뒤 query.txt, ESearch·EFetch XML, 응답 메타데이터와 SHA-256을 질문별 실행 폴더에 저장했다."
    )
    doc.add_heading("2.4 로컬 AI 선별", level=2)
    add_body(
        doc,
        f"선별기는 외부 API가 아니라 로컬에 저장된 {metrics['model_id']} 모델을 사용했다. 라벨은 retain, deprioritize, uncertain 세 가지다. "
        "초록이 없으면 title_only로 구분하고 신뢰도 상한을 low로 제한했다. 100행을 한 배치로 처리하고 JSONL 체크포인트를 append-only로 기록했다."
    )
    add_body(
        doc,
        "AI 참조표준은 선별 프롬프트와 다른 PICOS 요소별 프롬프트로 세 번 독립 채점하도록 계획했다. 규칙엔진 맹검평가는 실제 제품 구성에서 무라벨 사례를 만든 뒤 AI 라벨을 먼저 잠그고 엔진 예측을 연결하도록 설계했다. 이번 실행에서는 두 절차를 시작하지 않았다."
    )

    doc.add_heading("3. 결과", level=1)
    doc.add_heading("3.1 허가원문 층", level=2)
    add_metric_table(
        doc,
        [
            ("분석 제품", f"{metrics['products']}개", "제품명 기반 입력 집합"),
            ("고유 성분", f"{metrics['ingredients']}개", "분석 제품에서 확인"),
            ("제품-성분 연결", f"{metrics['bindings']}개", "계산용 선택 연결"),
            ("복용 조건", f"{metrics['constraints']}개", "허가원문 검증 완료, 약사 재검토 별도"),
            ("released 규칙", f"{metrics['rules_released']}개", "source와 locator를 가진 규칙"),
        ],
    )
    doc.add_heading("3.2 문헌 검색층", level=2)
    add_metric_table(
        doc,
        [
            ("AI PICOS 질문", f"{metrics['questions']}개", "28개 성분과 16개 규칙 유형을 포괄"),
            ("질문별 hit 합계", f"{metrics['search_hits']:,}건", "질문 사이 중복 포함"),
            ("고유 PMID", f"{metrics['corpus_rows']:,}개", "중복 제거 뒤 코퍼스"),
            ("초록 보유", f"{metrics['with_abstract']:,}개", "제목과 초록으로 선별 가능"),
            ("제목만 보유", f"{metrics['title_only']:,}개", "title_only, confidence=low 상한"),
        ],
    )
    doc.add_page_break()
    doc.add_heading("3.3 AI 선별 부분 결과", level=2)
    add_metric_table(
        doc,
        [
            ("판정 완료", f"{metrics['screened']:,}/{metrics['corpus_rows']:,}행", "전체 선별 미완료"),
            ("커버리지", f"{metrics['coverage'] * 100:.2f}%", "1.0 미달"),
            ("retain", f"{metrics['decision_distribution'].get('retain', 0)}건", "직접 근거 후보"),
            ("deprioritize", f"{metrics['decision_distribution'].get('deprioritize', 0)}건", "질문 직접성이 낮음"),
            ("uncertain", f"{metrics['decision_distribution'].get('uncertain', 0)}건", "추가 정보 없이는 확정 어려움"),
        ],
    )
    add_note(doc, "성능 지표", "AI 참조표준과 맹검 독립평가를 실행하지 않았으므로 민감도·특이도·정밀도·F1은 null이다.")

    doc.add_heading("4. 고찰", level=1)
    doc.add_heading("4.1 이층 구조가 주는 이점", level=2)
    add_body(
        doc,
        "문헌이 허가 판정을 덮어쓰지 않으므로 사실의 출처가 흐려지지 않는다. 사용자는 제품명으로 위험 신호를 찾고, 판정 근거로 허가원문 locator를 확인하며, 별도 참고 문헌에서 위해 연관성의 배경을 읽을 수 있다. 문헌과 허가사항이 충돌해도 한쪽을 지우지 않고 충돌로 남길 수 있다."
    )
    doc.add_heading("4.2 부분 선별 결과를 해석하는 범위", level=2)
    add_body(
        doc,
        f"현재 {metrics['screened']:,}행 분포는 파이프라인 작동 여부를 확인하는 중간 상태다. 전체 코퍼스를 대표한다고 주장할 수 없고, retain 규모를 외삽해서도 안 된다. "
        "특히 첫 세 배치는 PMID 정렬 순서의 앞부분이므로 무작위 표본이 아니다. 이 수치는 성능이 아니라 진행률이다."
    )

    doc.add_heading("5. 한계", level=1)
    add_body(
        doc,
        "첫째, 사람 판정은 0건이며 AI 참조표준도 아직 만들지 않았다. 둘째, 분류기와 향후 참조표준이 같은 모델 계열이면 독립성이 부분적이다. 셋째, PubMed 단일 자료원만 사용했다. 넷째, 선별 커버리지가 100%에 이르지 않았다. 다섯째, 규칙 16개에 문장 단위 문헌 locator를 연결하지 않았다. 여섯째, 규칙엔진 AI 맹검 독립평가를 실행하지 않았다. 따라서 complete와 performance_claim_allowed를 true로 바꿀 근거가 없다."
    )
    add_body(
        doc,
        f"복용 조건 {metrics['constraints']}개는 허가원문 검증까지 완료됐지만 별도 약사 재검토를 거치지 않았다. 분석 제품은 판매량 순위 집합이 아니라 대표 일반의약품 후보다. 판매량 자료가 없으므로 대표성을 주장하지 않는다."
    )

    doc.add_heading("6. 결론", level=1)
    add_body(
        doc,
        f"이 연구는 식약처 허가원문을 결정층으로 유지하면서 AI가 설계한 PubMed 문헌 근거층을 별도로 만들었다. PICOS {metrics['questions']}개와 고유 PMID {metrics['corpus_rows']:,}개 코퍼스는 재현 가능한 원시 응답과 해시를 가진다. "
        f"다만 AI 선별은 {metrics['screened']:,}행, {metrics['coverage'] * 100:.2f}%에 머물렀다."
    )
    add_body(
        doc,
        "다음 실행은 남은 문헌을 모두 판정해 coverage=1.0을 만든 뒤, AI 참조표준 채점과 규칙엔진 맹검평가를 순서대로 수행해야 한다. 그 전까지 연구 상태는 complete=false, release_ready=false, independent_blinding=false다."
    )

    doc.add_heading("참고 자료", level=1)
    references = [
        "식품의약품안전처 의약품안전나라. 의약품상세정보 및 허가 원문. 연구 원시자료의 source_id와 locator에 기록.",
        "National Center for Biotechnology Information. Entrez Programming Utilities Help. https://www.ncbi.nlm.nih.gov/books/NBK25501/",
        "research_v3/protocol/protocol-v4.0-full-ai.md.",
        "research_v3/otc/literature/picos/picos_definition.json.",
        "research_v3/otc/literature/screening/screening_manifest.json.",
        "research_v3/otc/metrics_manifest.json.",
    ]
    for index, reference in enumerate(references, start=1):
        paragraph = doc.add_paragraph(style="List Number")
        paragraph.paragraph_format.space_after = Pt(4)
        run = paragraph.add_run(reference)
        set_run_font(run, FONT_BODY, 9.5)

    doc.add_page_break()
    doc.add_heading("부록 A. 재현성 식별자", level=1)
    add_metric_table(
        doc,
        [
            ("PICOS 프롬프트 SHA-256", read_json(PICOS_PATH)["prompt_sha256"], "AI 질문 설계 프롬프트"),
            ("선별 프롬프트 SHA-256", metrics["screening_prompt_sha256"], "고정된 P2 프롬프트"),
            ("코퍼스 입력 SHA-256", metrics["corpus_sha256"], "evidence_map.csv"),
            ("로컬 모델 revision", metrics["model_revision"], metrics["model_id"]),
        ],
    )
    doc.core_properties.title = "식약처 허가원문 기반 국내 일반의약품 안전성 조회 시스템과 AI 자율 문헌 근거층 구축"
    doc.core_properties.author = "권혁찬"
    doc.core_properties.subject = "v4.0 부분 실행 보고"
    doc.save(THESIS_DOCX)


def build_markdown(metrics: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    coverage_pct = metrics["coverage"] * 100
    presentation = f"""# 발표원고 v4.0

## 슬라이드 1. 이 연구가 푸는 문제

사람은 약을 성분명보다 제품명으로 기억합니다. 하지만 감기약과 해열진통제를 함께 먹으면 같은 성분이 겹칠 수 있습니다. 이 연구는 제품명을 넣으면 성분, 용량, 복용 간격과 주의사항까지 거슬러 올라가는 조회 도구를 만듭니다. 현재 분석 집합은 제품 {metrics['products']}개, 고유 성분 {metrics['ingredients']}개입니다.

## 슬라이드 2. 왜 연구 주제를 바꿨나

초기 영양성분 자료는 이전 계보로 보존했습니다. 이번 연구는 국내 실제 일반의약품의 허가원문과 제품명 중심 질문으로 옮겼습니다. 이전 영양성분 수치는 새 OTC 결과에 합산하지 않습니다. 같은 창고에 두 상자를 두되 라벨을 섞지 않는 것과 같습니다.

## 슬라이드 3. 허가원문에서 무엇을 뽑았나

식약처 원문에서 제품 {metrics['products']}개, 성분 {metrics['ingredients']}개, 계산 연결 {metrics['bindings']}개를 확인했습니다. 복용 조건은 {metrics['constraints']}개입니다. released 규칙은 {metrics['rules_released']}개이고 모두 source와 locator를 가집니다. 이 층이 실제 위험 신호를 판정합니다.

## 슬라이드 4. 왜 문헌층을 따로 두나

최대용량 초과 여부는 허가사항과 계산으로 결정합니다. 과량이 간손상과 연관된다는 설명은 PubMed 문헌에서 찾습니다. 판정하는 층과 설명하는 층을 분리하면 출처가 흐려지지 않습니다. 문헌이 허가 판정을 바꾸지는 않습니다.

## 슬라이드 5. AI가 PICOS를 어떻게 정했나

PICOS는 누구에게, 어떤 노출을, 무엇과 비교해, 어떤 결과와 연구설계로 볼지 정하는 질문 틀입니다. AI는 28개 성분과 16개 규칙 유형만 받고 질문 {metrics['questions']}개를 만들었습니다. 기존 영양성분 검색식은 읽지 않았습니다. 질문은 아세트아미노펜, NSAID, 감기·알레르기 복합성분, 소화제, 외용 진통성분으로 묶였습니다.

## 슬라이드 6. 문헌을 어떻게 모았나

PubMed ESearch로 건수를 먼저 확인하고 상한을 넘은 검색은 다운로드 전에 좁혔습니다. 최종 질문별 hit 합계는 {metrics['search_hits']:,}건입니다. 중복 제거 뒤 고유 PMID는 {metrics['corpus_rows']:,}개였습니다. 초록이 있는 문헌은 {metrics['with_abstract']:,}개, 제목만 있는 문헌은 {metrics['title_only']:,}개입니다.

## 슬라이드 7. AI 선별은 어디까지 왔나

외부 API 대신 로컬 {metrics['model_id']} 모델을 사용했습니다. 100행씩 판정하고 체크포인트를 계속 덧붙이는 방식으로 저장했습니다. 현재 {metrics['screened']:,}행, {coverage_pct:.2f}%를 판정했습니다. retain {metrics['decision_distribution'].get('retain', 0)}건, deprioritize {metrics['decision_distribution'].get('deprioritize', 0)}건, uncertain {metrics['decision_distribution'].get('uncertain', 0)}건입니다.

## 슬라이드 8. 정확도는 왜 아직 말하지 않나

분류기의 정확도를 재려면 선별 결과를 보지 않은 별도 AI 참조표준이 필요합니다. 그 뒤 실제 제품 사례를 무라벨로 만들고, AI 라벨을 먼저 잠근 다음 엔진 예측을 연결해야 합니다. 이번 실행에서는 두 절차를 시작하지 않았습니다. 그래서 민감도, 특이도와 F1은 모두 null입니다.

## 슬라이드 9. 현재 한계

사람 판정은 0건이고 PubMed 한 자료원만 사용했습니다. 선별 커버리지는 100%가 아닙니다. 문헌 locator를 규칙 16개에 연결하지 않았고 사이트 빌드도 다시 검증하지 않았습니다. 복용 조건 {metrics['constraints']}개는 허가원문 검증까지만 끝났습니다.

## 슬라이드 10. 결론과 다음 실행

허가원문 결정층과 AI 문헌 설명층을 분리하는 구조는 만들어졌습니다. 하지만 연구 완료 게이트는 통과하지 못했습니다. 다음 실행은 남은 {metrics['corpus_rows'] - metrics['screened']:,}행을 모두 판정한 뒤 AI 참조표준과 맹검평가를 순서대로 수행해야 합니다. 그 전까지 complete=false와 release_ready=false를 유지합니다.

Reference basis: Toss `loan-101` explanatory article family.
"""
    (REPORTS_DIR / "발표원고_v4.0.md").write_text(presentation, encoding="utf-8")

    notion = f"""# 현재 상태 - 2026-07-27 v4.0 부분 실행

> 이번 실행은 PubMed 검색까지 완료했고 AI 선별은 {metrics['screened']:,}/{metrics['corpus_rows']:,}행에서 중단했습니다. AI 참조표준과 규칙엔진 맹검평가는 실행하지 않았으므로 `complete=false`, `performance_claim_allowed=false`, `release_ready=false`입니다.

## 핵심 수치

- 허가원문 결정층: 제품 {metrics['products']}개, 성분 {metrics['ingredients']}개, 계산 연결 {metrics['bindings']}개, 복용 조건 {metrics['constraints']}개
- 규칙: 전체 {metrics['rules_total']}개, released {metrics['rules_released']}개
- AI PICOS: {metrics['questions']}개
- PubMed: 질문별 hit 합계 {metrics['search_hits']:,}건, 고유 PMID {metrics['corpus_rows']:,}개
- 문헌 형태: 초록 보유 {metrics['with_abstract']:,}개, 제목만 {metrics['title_only']:,}개
- AI 선별: {metrics['screened']:,}행, 커버리지 {coverage_pct:.2f}%
- 판정 분포: retain {metrics['decision_distribution'].get('retain', 0)}, deprioritize {metrics['decision_distribution'].get('deprioritize', 0)}, uncertain {metrics['decision_distribution'].get('uncertain', 0)}

## 방법 요약 - 두 층을 섞지 않음

식약처 허가원문은 제품, 성분, 함량, 복용 조건과 규칙 판정을 결정합니다. PubMed 문헌은 위해 연관성을 설명하는 참고 근거입니다. 문헌이 허가 판정을 바꾸지 않습니다. 사람 판정 자료는 이전 계보로 보존하고 v4.0 입력이나 정답으로 연결하지 않았습니다.

## 선별 성능과 맹검평가

현재 성능 수치는 없습니다. 선별기의 AI 참조표준 채점과 규칙엔진 AI 맹검 독립평가를 시작하지 않았습니다. 기존 페이지의 “사람 맹검 독립평가 미완료” 조건은 AM-OTC-001에서 AI 평가로 대체됐지만, AI 평가 자체가 아직 끝난 것은 아닙니다.

## 상태 경계와 한계

- `independent_blinding_ai=false`: AI 맹검평가 미실행
- `independent_evaluation_ai_complete=false`: 평가 미실행
- `performance_claim_allowed=false`: 성능 주장 근거 없음
- `complete=false`: P2, P3, P4 미완료
- `release_ready=false`: 임상 배포 준비와 연구 종결은 별개
- 사람 판정 0건, PubMed 단일 자료원, 선별 커버리지 {coverage_pct:.2f}%

## 코드·배포

P0과 P1은 Git 커밋으로 보존했습니다. P2는 append-only 체크포인트 3개까지 저장했습니다. 이번 실행에서는 사이트 코드를 바꾸거나 배포하지 않았습니다. 다음 실행에서 P2 100% 완료 뒤 P3과 P4를 진행합니다.

## 공식 문서 위치

- `research_v3/protocol/protocol-v4.0-full-ai.md`
- `research_v3/otc/literature/picos/picos_definition.json`
- `research_v3/otc/literature/evidence_map.csv`
- `research_v3/otc/literature/screening/screening_manifest.json`
- `research_v3/logs/v40_run_report.json`

## 결론

AI 자율 질문 설계와 PubMed 코퍼스 구축은 끝났습니다. 전체 AI 선별과 독립평가가 남았습니다. 완료하지 않은 수치는 추정하지 않고 null로 남깁니다.

Reference basis: Toss `loan-101` explanatory article family.
"""
    (REPORTS_DIR / "notion_update.md").write_text(notion, encoding="utf-8")

    readme = f"""# 국내 일반의약품 안전성 조회 연구

이 저장소는 국내 일반의약품을 제품명으로 입력해 중복 성분, 최대용량, 복용 간격, 연령, 질환과 병용약 위험 신호를 찾는 연구용 시스템이다.

## 두 근거층

- 식약처 허가원문은 제품, 성분, 함량, 복용 조건과 규칙 판정을 결정한다.
- PubMed 문헌은 위해 연관성을 설명하는 참고 근거다. 문헌은 허가 판정을 바꾸지 않는다.

현재 허가원문 분석 집합은 제품 {metrics['products']}개, 성분 {metrics['ingredients']}개, 계산 연결 {metrics['bindings']}개, 복용 조건 {metrics['constraints']}개다. released 규칙 {metrics['rules_released']}개는 source와 locator를 가진다.

## v4.0 상태

AI가 PICOS 질문 {metrics['questions']}개를 만들고 PubMed에서 고유 PMID {metrics['corpus_rows']:,}개를 수집했다. 로컬 AI 선별은 {metrics['screened']:,}행({coverage_pct:.2f}%)까지 끝났다. 전체 선별과 AI 참조표준·맹검평가가 미완료이므로 `complete=false`, `performance_claim_allowed=false`, `release_ready=false`다.

## 주요 경로

- 허가원문 연구 데이터: `research_v3/otc/`
- AI PICOS: `research_v3/otc/literature/picos/picos_definition.json`
- PubMed 코퍼스: `research_v3/otc/literature/evidence_map.csv`
- AI 선별 체크포인트: `research_v3/otc/literature/screening/`
- 규칙: `research_v3/otc/rules/rules.csv`
- 실행 보고서: `research_v3/logs/v40_run_report.json`

## 코드와 배포

- GitHub: https://github.com/yeohj0710/otc-nutrient-safety-engine
- 기존 공개 주소: https://otc-nutrient-safety-engine.vercel.app
- 이번 실행에서는 사이트를 변경·검증·배포하지 않았다.

## 검증 명령

```powershell
.\\.venv-research\\Scripts\\python.exe -m pytest tests\\research -q
npm run typecheck
npm run lint
npm test
npm run build
```

배포는 별도 승인 범위다. 이 실행에서는 배포하지 않는다.

이 시스템은 연구용 프로토타입이며 의료진의 진단이나 복약 결정을 대체하지 않는다.
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")

    agents = f"""<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Project navigation

Before exploring the repo from scratch, check `docs/project_map.md`.

- Main page: `app/page.tsx`
- Main client UI: `src/components/rule-explorer-client.tsx`
- Result card UI: `src/components/rule-card.tsx`
- Safety engine: `src/lib/safety-engine/index.ts`
- Knowledge loader/normalizer: `src/lib/knowledge/`
- Primary legacy data source: `data/knowledge_pack.json`
- Runtime index: `src/generated/knowledge-index.json`
- Project map: `docs/project_map.md`

## v4.0 research boundary

- The active question is Korean OTC product-name safety lookup.
- MFDS authorization records are the deterministic authority for product, ingredient, amount, administration constraints, and rule decisions.
- PubMed is a separate AI-selected literature layer. It supports evidence claims but cannot override authorization facts or released rule logic.
- Keep authorization evidence and literature evidence in separate fields. Preserve conflicts as `conflict`.
- New literature artifacts belong only under `research_v3/otc/literature/`. Do not modify `research_v3/search/provisional_pubmed_20260710/`.
- Human judgment files are preserved legacy inputs and must not enter the v4.0 chain: `research_v3/screening/`, `research_v3/human_review_minimal/`, expert review artifacts, and `human_reference_label`.
- AI-reference metrics must name their source: `sensitivity_vs_ai_reference`, `specificity_vs_ai_reference`, `agreement_vs_ai_reference`, `ai_reference_standard`, `ai_cross_checked`.
- `independent_blinding` means human blinding and remains false. AI blinding uses `independent_blinding_ai`.
- `release_ready` remains false. Do not deploy from this workflow.
- Current v4.0 screening is partial: {metrics['screened']:,}/{metrics['corpus_rows']:,} rows. Do not claim completion or performance.
- Do not delete `tools/search_pipeline/embase_adapter.py`.
- Keep 신신파스아렉스 source records but exclude it from analysis and runtime.
- Released rules require both source and locator. The {metrics['constraints']} administration constraints and {metrics['rules_released']} released rules are different states.
- The systematic search pipeline is Python-based and separate from the Next.js runtime. Its code is in `tools/search_pipeline/` and its preserved outputs are in `data/systematic_search/`.
- Treat `data/knowledge_pack.json` and prior nutrient search outputs as superseded exploratory material only.

## Verification

Run `npm run typecheck`, `npm run lint`, `npm test`, and `npm run build` after site changes. Do not deploy.
"""
    (ROOT / "AGENTS.md").write_text(agents, encoding="utf-8")

    project_map = f"""# Project map

## 사용자 화면

- `app/page.tsx`: 제품명 중심 조회 화면
- `app/sources/page.tsx`: 허가원문 출처 브라우저
- `app/rules/[id]/page.tsx`: 규칙 상세
- `src/components/rule-explorer-client.tsx`: 제품 선택과 입력 폼
- `src/components/rule-card.tsx`: 위험 신호와 근거 카드
- `src/lib/site.ts`: 사이트명과 설명

## 결정 엔진

- `src/lib/safety-engine/index.ts`: 허가원문 기반 결정 규칙
- `src/lib/knowledge/index.ts`: 런타임 지식 인덱스 로더
- `src/lib/knowledge/normalize.ts`: 연구 데이터를 런타임 구조로 변환
- `src/types/knowledge.ts`: Zod 스키마와 핵심 타입

## 연구 데이터

- `research_v3/otc/normalized/`: 제품 {metrics['products']}개, 성분 {metrics['ingredients']}개, 계산 연결 {metrics['bindings']}개
- `research_v3/otc/rules/`: 전체 규칙 {metrics['rules_total']}개, released {metrics['rules_released']}개
- `research_v3/otc/literature/picos/`: AI 자율 PICOS 질문
- `research_v3/otc/literature/searches/`: PubMed 원시 XML, 메타데이터와 SHA-256
- `research_v3/otc/literature/evidence_map.csv`: 고유 PMID {metrics['corpus_rows']:,}개 코퍼스
- `research_v3/otc/literature/screening/`: 로컬 AI 선별 체크포인트와 부분 매니페스트

## 보존 계보와 런타임 산출물

- `data/knowledge_pack.json`: 이전 영양성분 탐색 자료. 활성 OTC 성과에 합산하지 않음
- `data/systematic_search/`: 이전 검색 파이프라인 산출물
- `src/generated/knowledge-index.json`: 현재 Next.js 런타임 인덱스

## 실행 스크립트

- `tools/v40_literature_pipeline.py`: PICOS 생성, ESearch, EFetch와 코퍼스 정규화
- `tools/screen_v40_literature_local.py`: 로컬 Qwen 선별과 append-only 체크포인트
- `tools/build_v40_reporting.py`: 논문·문서·지표 재생성
- `tools/search_pipeline/`: 보존된 Python 검색 파이프라인

## 검증

```powershell
.\\.venv-research\\Scripts\\python.exe -m pytest tests\\research -q
npm run typecheck
npm run lint
npm test
npm run build
```
"""
    (ROOT / "docs/project_map.md").write_text(project_map, encoding="utf-8")


def update_metrics(metrics: dict[str, Any]) -> None:
    layer = {
        "lineage": "research_v3_otc_v4_ai_literature",
        "status": "partial",
        "ai_picos_questions": metrics["questions"],
        "pubmed_hits_before_deduplication": metrics["search_hits"],
        "corpus_rows": metrics["corpus_rows"],
        "abstract_rows": metrics["with_abstract"],
        "title_only_rows": metrics["title_only"],
        "ai_screened_rows": metrics["screened"],
        "screening_coverage": metrics["coverage"],
        "screening_distribution": metrics["decision_distribution"],
        "screening_run_complete": False,
        "ai_reference": None,
        "blind_engine_evaluation": None,
        "performance_claim_allowed": False,
        "complete": False,
        "evidence_paths": {
            "picos": PICOS_PATH.relative_to(ROOT).as_posix(),
            "corpus": EVIDENCE_PATH.relative_to(ROOT).as_posix(),
            "screening": SCREENING_PATH.relative_to(ROOT).as_posix(),
        },
    }
    for path in (OTC_METRICS_PATH, ROOT_METRICS_PATH):
        manifest = read_json(path)
        manifest["generated_at_utc"] = utc_now()
        manifest["literature_layer"] = layer
        blockers = manifest.setdefault("release_blockers", [])
        blocker = "v4.0 AI 문헌 선별·AI 참조표준·규칙엔진 맹검 독립평가 미완료"
        if blocker not in blockers:
            blockers.append(blocker)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    metrics = collect_metrics()
    build_markdown(metrics)
    update_metrics(metrics)
    build_thesis(metrics)
    print(
        json.dumps(
            {
                "thesis_docx": str(THESIS_DOCX),
                "presentation": str(REPORTS_DIR / "발표원고_v4.0.md"),
                "notion": str(REPORTS_DIR / "notion_update.md"),
                "screening_coverage": metrics["coverage"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
