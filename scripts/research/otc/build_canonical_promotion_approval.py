from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OTC = ROOT / "research_v3" / "otc"
OUTPUT = OTC / "review" / "OTC_canonical_승격승인.html"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def build() -> str:
    files = [
        (ROOT / "research_v3/thesis/권혁찬_졸업논문_OTC_작업본.docx", "research_v3/thesis/권혁찬_졸업논문_최종본.docx"),
        (ROOT / "research_v3/thesis/권혁찬_졸업논문_OTC_작업본.pdf", "research_v3/thesis/권혁찬_졸업논문_최종본.pdf"),
        (ROOT / "research_v3/protocol/권혁찬_OTC_연구계획서_작업본.docx", "research_v3/protocol/권혁찬_OTC_연구계획서_최종본.docx"),
        (ROOT / "research_v3/protocol/권혁찬_OTC_연구계획서_작업본.pdf", "research_v3/protocol/권혁찬_OTC_연구계획서_최종본.pdf"),
    ]
    payload = {
        "schema_version": "1.0.0",
        "research_direction": "korean_otc_product_safety",
        "reviewer_id": "CANONICAL-PROMOTION-001",
        "authorize_canonical_document_promotion": True,
        "accept_blinded_independent_evaluation_not_completed": True,
        "claim_boundary": "codex_prefilled_external_human_confirmation_not_blinded_independent_evaluation",
        "authorize_production_deployment": False,
        "files": [{"source": source.relative_to(ROOT).as_posix(), "source_sha256": digest(source), "target": target} for source, target in files],
        "approved_at": "",
    }
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>OTC 최종본 승격 승인</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f7f8fa;color:#191f28;font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Noto Sans KR",sans-serif}}main{{max-width:720px;margin:auto;padding:52px 22px}}h1{{font-size:38px;line-height:1.35}}.card{{margin:24px 0;padding:24px;border-radius:18px;background:#fff}}li{{margin:14px 0;line-height:1.6}}.warn{{padding:16px;border-radius:12px;background:#fff4e5;color:#8b5a00;line-height:1.7}}button{{width:100%;height:60px;border:0;border-radius:14px;background:#3182f6;color:#fff;font-size:18px;font-weight:800}}#done{{display:none;color:#1b64da;font-weight:700}}</style></head><body><main><p style="color:#3182f6;font-weight:800">CANONICAL-PROMOTION-001</p><h1>최종본 승격과 연구 한계를 한 번에 확인하세요</h1><div class="card"><ul><li>현재 OTC 논문·연구계획서 작업본 4개를 canonical 최종본으로 승격합니다.</li><li>기존 최종본은 삭제하지 않고 G 드라이브와 저장소의 etc에 백업합니다.</li><li>외부 확인 13건은 Codex 사전판정 확인형이며 블라인드 독립평가가 아님을 논문·보고서에 유지합니다.</li><li>공개 production 배포는 승인 범위에 포함하지 않습니다.</li></ul></div><p class="warn">이 버튼은 블라인드 평가를 완료 처리하지 않습니다. 블라인드 평가 미완료 한계를 수용하고 현재 근거 범위의 최종본 승격만 승인합니다.</p><p id="done">승인 결과가 저장되었습니다. Codex에 “승인완료”라고 알려주세요.</p><button id="approve">위 조건으로 최종본 승격 승인</button><script id="payload" type="application/json">{data}</script><script>
approve.onclick=()=>{{const d=JSON.parse(payload.textContent);d.approved_at=new Date().toISOString();const b=new Blob([JSON.stringify(d,null,2)],{{type:'application/json'}}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='otc_canonical_promotion_approval.json';a.click();URL.revokeObjectURL(a.href);done.style.display='block';approve.disabled=true;approve.textContent='승인 완료';}};</script></main></body></html>'''


def main() -> int:
    OUTPUT.write_text(build(), encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
