# Finance-Analysis 프로젝트 지침

## 0. 전역 지침은 필수 참조 대상

모든 작업을 시작하기 전에 반드시 전역 지침 파일 [`C:\Users\Miche\.codex\AGENTS.md`](C:\Users\Miche\.codex\AGENTS.md)을 읽고 적용합니다.

- 전역 지침은 이 파일보다 우선합니다.
- 이 파일은 Finance-Analysis 프로젝트에 필요한 보충 규칙만 정의합니다. 전역 지침과 충돌하면 전역 지침을 따릅니다.
- 전역 지침 파일을 읽을 수 없거나 내용이 불명확하면, 그 사실을 사용자에게 알리고 안전한 범위에서만 진행합니다.
- 사용자 요청, 시스템 지침, 전역 지침, 이 프로젝트 지침의 순서로 우선순위를 판단합니다.

## 1. 현재 프로젝트 단계

- 현재 저장소는 초기화 단계입니다. 서비스 목적, 대상 사용자, 핵심 기능, 기술 스택, 데이터 출처는 아직 확정되지 않았습니다.
- 요구사항과 MVP가 합의되기 전에는 애플리케이션 코드, 외부 금융 API, 데이터베이스, 로그인 기능을 임의로 추가하지 않습니다.
- 요구사항을 확인할 때는 서비스 목적, 대상 사용자, 해결할 문제, 핵심 기능, 부가 기능, 제출물 또는 평가 기준을 정리합니다.

## 2. 기본 작업 흐름

1. 요구사항을 문서로 정리하고 필요한 가정을 명시합니다.
2. 기능을 입력, 처리, 출력, 예외 처리, 테스트 단위로 분해합니다.
3. 핵심 가치만 포함한 MVP 범위와 기술 스택을 합의합니다.
4. 기존 파일과 템플릿을 먼저 확인한 뒤 프로젝트 구조와 기능을 구현합니다.
5. 실행·테스트 결과와 README를 함께 갱신합니다.

## 3. 금융 데이터 작업 원칙

- 데이터 출처, 조회 시점, 통화, 시간대, 단위, 종목 코드 또는 기업 식별자를 결과에 명확히 표시합니다.
- 가격·환율·공시·재무 수치처럼 변할 수 있는 정보는 최신 출처를 확인하고, 추정·계산·원문 데이터를 구분합니다.
- 투자 추천 또는 수익 보장을 표현하지 않습니다. 분석 결과는 정보 제공 목적이며, 계산 가정과 한계를 함께 적습니다.
- API 키, 토큰, 계정 정보는 코드·문서·대화에 기록하지 않습니다. `.env.example`에는 자리표시자만 사용합니다.

## 4. 스킬 사용 규칙

작업 내용이 아래 조건에 해당하면 해당 스킬의 `SKILL.md`를 먼저 읽고 절차를 따릅니다. 관련 없는 스킬을 단지 사용하기 위해 적용하지 않습니다.

### 4.1 전역 개발 워크플로우 스킬

아래 스킬은 전역 지침의 개발 흐름을 실행하기 위한 참조 자료입니다. 경로를 임의로 추정하지 말고, 표의 `SKILL.md`를 읽은 뒤에 적용합니다.

| 작업 단계 | 스킬 | 필수 참조 위치 | 함께 사용할 전역 템플릿 |
| --- | --- | --- | --- |
| 요구사항 정의 | `requirements-definition` | `C:\Users\Miche\.codex\skills\requirements-definition\SKILL.md` | `C:\Users\Miche\.codex\templates\requirements-template.md` |
| 기능 분해 | `function-breakdown` | `C:\Users\Miche\.codex\skills\function-breakdown\SKILL.md` | `C:\Users\Miche\.codex\templates\function-breakdown-template.md` |
| MVP 설계 | `mvp-planning` | `C:\Users\Miche\.codex\skills\mvp-planning\SKILL.md` | `C:\Users\Miche\.codex\templates\mvp-plan-template.md` |
| 프로젝트 구조 생성 | `project-structure-builder` | `C:\Users\Miche\.codex\skills\project-structure-builder\SKILL.md` | 없음 |
| API 서비스 구현 | `api-service-builder` | `C:\Users\Miche\.codex\skills\api-service-builder\SKILL.md` | `C:\Users\Miche\.codex\templates\api-spec-template.md` |
| AI 에이전트 기능 설계 | `ai-agent-workflow-builder` | `C:\Users\Miche\.codex\skills\ai-agent-workflow-builder\SKILL.md` | `C:\Users\Miche\.codex\templates\agent-workflow-template.md` |
| 오류 분석·수정 | `debugging-coach` | `C:\Users\Miche\.codex\skills\debugging-coach\SKILL.md` | 없음 |
| 리팩터링 | `refactoring-coach` | `C:\Users\Miche\.codex\skills\refactoring-coach\SKILL.md` | 없음 |
| 보안 점검 | `security-checker` | `C:\Users\Miche\.codex\skills\security-checker\SKILL.md` | 없음 |
| README·최종 보고서 | `readme-report-writer` | `C:\Users\Miche\.codex\skills\readme-report-writer\SKILL.md` | `C:\Users\Miche\.codex\templates\readme-template.md`, `C:\Users\Miche\.codex\templates\final-report-template.md`, `C:\Users\Miche\.codex\templates\test-scenario-template.md` |

### 4.2 프로젝트 산출물 스킬

| 상황 | 사용할 스킬 | 적용 기준 |
| --- | --- | --- |
| CSV, XLSX, TSV 파일 분석·생성·수정·검증 | `spreadsheets:Spreadsheets` | 수식, 피벗, 차트, 서식, 데이터 정리, 검증이 필요한 파일 기반 분석 |
| 대화형 차트, 수익률 비교, 시나리오 계산기, 탐색 도구 | `visualize:visualize` | 표나 글보다 사용자가 직접 값·조건을 바꾸어 보는 시각화가 적합할 때 |
| 금융 보고서 PDF 읽기·생성·렌더링 검증 | `pdf:pdf` | PDF의 표·레이아웃·입력 양식 확인이 필요할 때 |
| 보고서용 Word 문서 생성·수정·검증 | `documents:documents` | `.docx` 산출물이 필요할 때 |
| 분석 발표 자료 생성·수정 | `presentations:Presentations` | PowerPoint 또는 Google Slides 산출물이 필요할 때 |
| 기존 Google Sheets/Docs/Slides/Drive 파일 작업 | `google-drive:google-drive` 및 해당 하위 스킬 | 사용자가 연결된 Google Drive 파일을 지정하거나 해당 파일을 편집할 때 |
| 분석 대시보드·웹 사이트 제작 | `sites:sites-building` | 특히 `.openai/hosting.json`이 있으면 반드시 사용 |
| 사이트 배포·호스팅 | `sites:sites-hosting` | `sites-building` 이후 배포하거나 호스팅을 관리할 때 |
| 데이터 시각용 이미지·일러스트 생성 또는 편집 | `imagegen` | 코드·SVG보다 비트맵 이미지가 적합할 때 |
| OpenAI API 또는 Codex 사용법 확인 | `openai-docs` | 최신 공식 문서 또는 제품 사용법이 필요할 때 |
| 재사용 가능한 보고서·스프레드시트·프레젠테이션 양식 제작 | `template-creator:template-creator` | 사용자가 한 번 쓰는 결과물이 아니라 재사용 가능한 개인 템플릿을 요청할 때 |

## 5. 템플릿 사용 규칙

- 전역 템플릿의 기준 위치는 `C:\Users\Miche\.codex\templates`입니다. 템플릿 파일이 존재하는지 확인한 뒤 사용합니다.
- 작업 시작 시 기존 프로젝트 파일, 사용자가 제공한 샘플, 템플릿 폴더를 먼저 확인합니다.
- 사용자가 제공한 템플릿은 구조·스타일·필수 항목을 우선 보존합니다. 템플릿을 대체하거나 크게 바꾸려면 이유와 영향을 먼저 설명합니다.
- 재사용 템플릿이 없으면 요청된 산출물에 맞는 최소 구조만 새로 만듭니다. 요구사항이 확정되기 전에는 임의의 보고서·대시보드 양식을 대량 생성하지 않습니다.
- `template-creator:template-creator`는 사용자가 명시적으로 재사용 템플릿을 만들거나 기존 템플릿을 업데이트해 달라고 요청한 경우에만 사용합니다.
- 새 템플릿에는 목적, 입력 데이터 형식, 계산 가정, 사용 방법, 검증 방법을 포함합니다.
- 전역 템플릿을 프로젝트 파일로 복사하거나 수정할 때는 원본 경로와 적용 목적을 문서에 남기며, 원본 자체는 변경하지 않습니다.

## 6. 코드, 테스트, 문서화

- 파일 수정 전 관련 파일과 기존 구조를 확인합니다. 사용자가 요청하지 않은 기능·삭제·대규모 리팩터링은 하지 않습니다.
- 모든 기능 변경에는 실행 방법, 확인할 화면 또는 파일, 입력 예시, 기대 결과, 실패 시 확인할 로그를 안내합니다.
- 테스트를 실행하지 못했으면 완료로 표현하지 않고 사유와 수동 검증 방법을 남깁니다.
- README에는 프로젝트 소개, 주요 기능, 기술 스택, 설치·실행·테스트 방법, 데이터 출처, 환경 변수, 폴더 구조, 한계와 개선 방향을 기록합니다.
