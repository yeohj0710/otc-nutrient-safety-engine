# 실행 환경과 재현성 명세

## 1. 원칙

재현성은 같은 코드를 다시 실행하는 것만 뜻하지 않는다. 같은 입력 데이터, 같은 검색 기록, 같은 판정 버전, 같은 분석 환경에서 동일한 표·그림·수치가 생성되어야 한다. 원문 접근권한이나 외부 데이터베이스가 달라질 수 있으므로, 검색·원문·분석·배포의 재현 범위를 구분한다.

## 2. 권장 도구 체계

- 애플리케이션: 현재 저장소의 Node.js/Next.js 버전을 먼저 감사하고 lockfile을 유지한다.
- 연구 데이터 처리: Python 3.12 이상을 기본으로 하되 저장소에서 실제 사용한 정확한 버전을 고정한다.
- 환경 관리자: `uv` 또는 `venv`; 한 프로젝트에서 둘을 혼용하지 않는다.
- 분석 산출물: CSV는 교환용, Parquet은 분석용, JSON/JSONL은 규칙·스키마 검증용으로 사용한다.
- 통계: Python 또는 R 중 하나를 주 분석 언어로 고정한다. 메타분석 기능이 부족해 다른 언어를 쓰면 원자료와 결과를 자동 교환하고 실행 명령을 기록한다.
- 문서: 학교 제출본은 DOCX를 기준으로 만들고 PDF로 변환한 뒤 페이지 렌더링 검수한다.

`requirements-research.in`은 초기 의존성 목록이다. 실행 환경에서 실제 버전을 해결한 후 `requirements-research.lock` 또는 동등한 lockfile을 생성하고 커밋한다.

## 3. 디렉터리와 데이터 불변성

- `search/raw/`: 다운로드 직후의 원시 export. 수정 금지.
- `full_text/private/`: 접근권한이 있는 원문. 공개 git에서 제외.
- `search/normalized/`: 원시 export에서 재생성 가능해야 함.
- `screening/`, `extraction/`, `risk_of_bias/`: 사람 판정이 포함되므로 행 단위 reviewer·timestamp·version을 보존.
- `synthesis/`, `ai_eval/`, `validation/`, `thesis/`: 상위 데이터와 스크립트에서 생성.
- `legacy_untrusted/`: 기존 자료의 감사 보관소. v2 분석 입력에서 제외.

원시 파일을 덮어쓰지 않는다. 수정이 필요하면 새 버전을 만들고 이전 버전과 해시를 연결한다.

## 4. 파일별 필수 메타데이터

각 파생 산출물은 가능한 경우 sidecar JSON 또는 파일 내부 메타데이터로 다음을 기록한다.

- artifact ID와 schema version
- 생성 시각(UTC)
- 생성 명령
- git commit
- 입력 파일 경로와 SHA-256
- 실행 스크립트와 버전
- 환경 lockfile 해시
- 수동 수정 여부
- 검토자와 검증 상태

## 5. 한 명령 재생성 목표

최종 저장소에는 다음과 유사한 명령을 제공한다.

```bash
make audit
make validate-data
make analyze
make figures
make thesis
make validate-release
```

`make thesis`는 표·그림·metrics manifest가 먼저 성공해야 실행된다. `make validate-release`가 실패하면 배포·제출 태그를 만들지 않는다.

## 6. 외부 서비스와 모델 버전

문헌 데이터베이스, LLM API, 배포 서비스는 시간이 지나면 결과나 버전이 바뀔 수 있다. 따라서 다음을 고정한다.

- 검색: 정확한 플랫폼, 검색식, 실행 시각, hit/export/import 수, 원시 export
- LLM: 모델 식별자, 제공 가능한 snapshot/version, 프롬프트 해시, 매개변수, 입력 해시, 원시 응답
- 배포: commit SHA, ruleset version, 데이터 freeze tag, 배포 ID

모델 이름만 같고 snapshot이 달라지면 별도 실험 조건으로 취급한다.

## 7. 민감·비공개 자료

다음은 공개 저장소에 커밋하지 않는다.

- 유료 원문 PDF
- 기관 인증 토큰과 API key
- 개인식별 가능한 전문가·사용자 자료
- IRB 승인 전 수집한 사람 대상 자료
- 원문 전체가 포함된 외부 모델 요청 로그

공개 릴리스에는 서지정보, 합법적으로 인용 가능한 짧은 근거 구절 또는 위치, 파생 데이터, 코드만 포함한다.

## 8. 최종 재현성 시험

깨끗한 새 환경에서 다음을 확인한다.

1. 저장소 clone 및 환경 설치
2. 비공개 파일 없이 공개 분석이 어디까지 재생성되는지 확인
3. 비공개 원문 경로를 제공했을 때 전체 검증 재실행
4. 표·그림·metrics manifest 해시 비교
5. DOCX/PDF 재생성과 페이지 렌더링
6. 앱 build·test·ruleset checksum 확인
7. `scripts/validate_release.py` 통과
