# Yeo Research Redesign and Execution Package

`00_START_HERE.md`부터 읽는다. 이 패키지는 단순 연구계획서가 아니라 여형준 졸업논문의 연구 질문, 체계적 근거 수집, AI 보조 선별·추출 평가, 근거평가, 규칙 엔진, 독립 검증, 논문 집필을 하나의 데이터 계보로 연결하는 실행 명세다.

기본 분기는 여형준 연구다. 사용자가 제시한 `otc-nutrient-safety-engine` 공개 프로젝트는 다른 권혁찬 연구와 연결되어 있으므로, 범용 코드만 분리해 사용할 수 있고 학생 정보·규칙·수치·문헌을 여형준 연구에 혼합하면 안 된다.

대상 저장소에 이 폴더를 `execution_package/`로 복사한 뒤 다음으로 시작한다.

```bash
python execution_package/scripts/bootstrap_research_v2.py --repo-root . --package-root execution_package
python execution_package/scripts/check_project_identity.py --root .
```

그다음 `13_CODEX_MASTER_PROMPT.md`를 Codex GPT-5.6의 첫 지시로 사용한다. 최종 완료 선언 전에는 `scripts/validate_release.py`를 통과해야 한다.
