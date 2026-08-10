# MVP 프로젝트 구조

## 설계 원칙

- 공개 API는 `POST /api/analyses` 하나이며, 요청 안에서 동기식으로 분석을 끝낸다.
- 사용자 입력·중간 결과·최종 결과는 응답 조립 중에만 사용하고 영구 저장하지 않는다.
- 정량 계산·필터링·점수화는 결정적 일반 코드의 책임이다. AI는 뉴스 해석과 근거 기반 설명만 담당한다.
- 데이터마다 출처, 수집 시점, 기준일, 통화, 단위를 모델에 보존한다.
- ETF별 실제 배분 비중·금액은 MVP 범위 밖이다. 포트폴리오 모듈은 구성 후보와 제약조건, `allocation_pending` 상태만 반환한다.

## 전체 폴더 구조

```text
FinanceAnalysis/
|- README.md                         # 프로젝트 목적과 현재 단계
|- AGENTS.md                         # 프로젝트 작업 규칙(기존 파일)
|- .env.example                      # 비밀값 없는 환경 변수 이름·예시
|- .gitignore                        # 비밀값, 캐시, 로그, 빌드 산출물 제외
|- docs/
|  |- requirements.md                # 확정 요구사항(기존 파일)
|  |- function-breakdown.md          # 기능 분해(기존 파일)
|  |- mvp-plan.md                    # MVP 범위·정책(기존 파일)
|  |- project-structure.md           # 구조·책임·연결 위치
|  |- api-contract.md                # 공개 API와 요청·응답 모델
|  `- test-plan.md                   # 테스트 범위와 시나리오
|- frontend/
|  |- README.md                      # 프론트엔드 경계
|  |- public/                        # 정적 자산
|  `- src/
|     |- components/
|     |  |- analysis-form/           # 조건 입력·필드 오류 UI
|     |  `- analysis-result/         # 결과·출처·위험·책임 제한 UI
|     |- features/analysis/          # 분석 화면 상태와 UI 조합
|     |- services/                   # 단일 공개 API 클라이언트
|     |- types/                      # API 요청·응답 화면용 타입
|     |- styles/                     # 전역·화면 스타일
|     `- utils/                      # 표시 형식 등 순수 UI 보조 함수
|- backend/
|  |- README.md                      # 백엔드 경계
|  |- app/
|  |  |- api/
|  |  |  |- routes/                 # POST /api/analyses 공개 라우트
|  |  |  `- schemas/                # HTTP 요청·응답 검증 모델
|  |  |- core/                      # 설정·오류·로그·요청 컨텍스트·SQLite ETF 캐시
|  |  |- collectors/                # KRX·운용사·DART·뉴스 공급자 어댑터
|  |  |- services/                  # 분석 조정·결과 조립·내부 서비스 계약
|  |  |- quantitative/              # 필터·지표·정규화·점수화 계산
|  |  |- news/                      # 뉴스 정제·관련성·근거 연결
|  |  |- ai/                        # AI 호출·응답 검증·근거 기반 설명
|  |  |- portfolio/                 # 구성 후보·제약조건·보류 상태
|  |  `- models/                    # 내부 도메인 데이터 모델
|  `- tests/
|     |- unit/                      # 순수 계산·검증·정제 단위 테스트
|     |- integration/                # 분석 흐름과 공급자 실패 격리 테스트
|     |- contract/                   # 공개 API 요청·응답 계약 테스트
|     `- fixtures/                   # 고정 ETF·가격·뉴스 테스트 데이터
`- data/                             # ETF 기준 데이터의 로컬 SQLite 운영 캐시(추적 제외)
```

## 폴더와 파일의 책임

| 위치 | 책임 | 포함하지 않는 것 |
| --- | --- | --- |
| `frontend/src/components/analysis-form` | 투자금·기간·위험 성향·허용 손실·선호 자산·현금성 비중 입력 및 오류 표시 | 서버 분석 로직 |
| `frontend/src/features/analysis` | 입력 대기·분석 중·완료·부분 결과·실패 상태 전환 | 스트리밍·폴링 |
| `frontend/src/services` | `POST /api/analyses` 요청·응답 변환 | 내부 Backend 서비스 직접 호출 |
| `backend/app/api/routes` | 공개 HTTP 엔드포인트, 상태 코드 변환 | 수집·계산 로직 |
| `backend/app/api/schemas` | 외부 요청·응답과 필드 오류 모델 검증 | DB 모델·계산식 |
| `backend/app/core` | 환경 설정 로딩, 구조화 로그, 안전한 오류 변환, SQLite ETF 캐시의 현재성 확인·저장 | 인증·사용자 세션·사용자 분석 이력 |
| `backend/app/collectors` | ETF 기초·상세·구성 종목·편입 비중·순자산, DART·뉴스 원천 수집과 출처 메타데이터 | 후보 순위·AI 요약·편입 현황 계산 |
| `backend/app/services` | 전체 단계 조정, 완료·부분·실패 판단, 결과 조립 | 공개 URL 추가 |
| `backend/app/quantitative` | 1차 필터, 지표 산출, MDD 제한, 정규화, 위험 성향별 점수·순위, 주요 종목의 ETF 편입률·총 ETF 자산 비중 계산 | AI 호출·투자 비중 생성 |
| `backend/app/news` | 기간·중복·출처·관련성 검증과 최대 100건 근거 묶음 생성 | 정량 점수 변경 |
| `backend/app/ai` | 뉴스 요약·감성·선정 근거 문안 생성, 형식·근거 검증, 재시도 | 수치 계산·순위·ETF 배분 |
| `backend/app/portfolio` | ETF 3~8개 구성 후보, 테마·운용사 제약, 현금성 비중, 보류 상태 | ETF별 실제 비중·금액·성과 예측 |
| `backend/app/models` | ETF, 가격, 지표, 주요 종목 편입 현황, 뉴스, 출처, 분석 단계 결과의 내부 불변 모델 | ORM·사용자 이력 |
| `backend/tests` | 단위·통합·계약 테스트와 고정 원천 데이터 | 외부 실서비스 의존 테스트 |
| `data/finance_analysis.db` | KRX ETF 기준·일별 거래 데이터의 운영 캐시 | 사용자 요청·분석 이력 |

## 기능별 연결 위치

```text
조건 입력
  frontend/components/analysis-form
  -> frontend/services
  -> backend/api/routes + api/schemas
입력값 검증
  -> frontend/features/analysis (사용자 안내)
  -> backend/services (서버 재검증)
ETF 데이터 확인
  -> backend/collectors
후보 필터링·정량 분석
  -> backend/quantitative
뉴스·공시 수집·분석
  -> backend/collectors -> backend/news -> backend/ai
  (최근 1주일 영업일 기준으로 수집하고, 정제 후 100건 미만이면 최근 1개월까지 확장; 전체 최대 100건)
결과 종합
  -> backend/services + backend/ai (근거 검증 후)
포트폴리오 계산 준비
  -> backend/portfolio (비중·금액은 보류)
결과 화면 출력
  -> backend/api/schemas -> frontend/types -> frontend/components/analysis-result
```

## 오류 및 로그 위치

- `backend/app/core`: 오류 코드, 공개 가능 메시지, 예외 변환, `request_id`와 단계별 구조화 로그의 공통 규칙을 둔다.
- `backend/app/api/schemas`: 필드 오류와 분석 단계 오류를 응답 모델로 제한한다. API 키·토큰·내부 예외 상세는 절대 노출하지 않는다.
- `backend/app/services`: 수집·뉴스·AI의 실패를 구분하고, 검증된 정량 결과가 남아 있으면 `partial` 결과를 조립한다.
- `backend/tests`: 입력 오류, 데이터 결측, 주요 종목 편입 현황, 최근 1주일·1개월 뉴스 기간 확장, `no_news`, AI 실패, 180초 초과의 계약을 검증한다.

## 구현 순서

1. `docs/mvp-plan.md`의 필수 정책(주간 표본일, 동일값 정규화, 위험 성향 규칙, 뉴스·AI 정책)을 확정한다.
2. `docs/api-contract.md`에 맞춰 Frontend 입력 모델과 Backend 검증 모델을 구현한다.
3. 공개 라우트와 분석 조정 서비스를 연결하고 완료·부분·실패의 빈 결과 골격을 검증한다.
4. ETF 기초 데이터 수집·캐시와 1차 필터를 구현한다.
5. 상세 데이터 검증, 결정적 정량 계산, 점수화, 상위 30개 선정을 구현한다.
6. 뉴스·DART 수집, 정제, 관련성 판정과 근거 묶음을 구현한다.
7. AI 뉴스 분석과 근거 검증을 구현한다.
8. 구성 후보·제약조건·`allocation_pending`을 조립한다.
9. 한 페이지 결과 화면을 연결하고 단위·통합·계약 테스트 및 README 실행 안내를 보완한다.

## 구조 단계에서 확정하지 않은 사항

- 실제 Frontend 프레임워크와 Backend 의존성 버전
- KRX·운용사·DART·뉴스 API의 구체 공급자, 이용 약관, 필드 매핑, 호출 한도
- 주간 가격 표본일 및 휴장일 처리
- 최소–최대 정규화에서 최솟값과 최댓값이 같은 경우의 규칙
- 투자금 적합도와 위험 성향별 ETF 유형 허용·제외표
- 뉴스 관련성 임계값, 최근 1주일·1개월의 날짜 경계, ETF별 뉴스 배분
- AI 재시도 횟수·제한 시간·30개 ETF와 100건 뉴스의 180초 내 처리 단위
- 기대수익률 추세 조정, 시나리오 범위, 과거 검증 오차 정책
- 포트폴리오 화면의 최종 명칭과 ETF별 실제 배분 산식·반올림·잔여금 처리
- 최종 제출물과 평가 기준
