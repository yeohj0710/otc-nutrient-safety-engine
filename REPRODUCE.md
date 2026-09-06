# 권혁찬 연구 재현

현재 결과의 기준은 `research/final/manifest.json`이다. 저장소 상위의 `evidence-recollect`에서 실행한다.

```powershell
python -m unittest discover -s tests
python corrections.py verify kwon
python reproduce.py verify kwon
```

검사는 원본과 최종 문헌 자료의 해시, 복원한 행의 판정 누락, 입력 ID, 인용문, 정정 전후 판정의 재현, 고정 표본·채점의 통계를 대조한다. 새 검색이나 모델 호출은 없다. `data/kwon/final/effective.decisions.jsonl`이 현재 판정이며, 과거 `screen/` 판정을 최종 사이트 입력으로 사용하지 않는다.

제목만 있는 문헌은 사후 기준으로 검토했다. 기존 설명 연결 10건의 인용·요약·적합성을 확인하고 8건을 정정했다. 전체 문헌 후보와 직접 검토한 설명 연결을 구분한다. 허가원문 규칙의 권한과 제품별 지원 범위는 문헌 수와 무관하다.

철회된 논문과 철회 공지는 수집 기록에 보존한다. 공개 화면에는 철회 상태와 서지정보만 표시하며 결과 인용과 AI 요약에는 사용하지 않는다.

ZIP은 최종 판정과 통계의 재현용이다. 웹사이트 전체 소스, 모든 원본 XML과 외부 원문 PDF를 포함하지 않는다. 전체 수집 원본은 `data/kwon/raw/`에 있으며 최종 메타데이터 명세에 원본별 해시를 남겼다. 사후 정정을 재검증한 새 맹검 성능 지표는 산출하지 않았다.
