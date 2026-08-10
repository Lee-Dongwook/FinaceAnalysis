# 공개 분석 API 계약 초안

## Endpoint

`POST /api/analyses`

분석은 동기식이며 최대 180초 안에 `completed`, `partial`, `failed` 중 하나의 최종 응답을 반환한다.

## 요청 모델: `AnalysisRequest`

| 필드 | 형식 | 필수 | 검증 규칙 |
| --- | --- | --- | --- |
| `client_request_id` | 문자열 | 선택 | 비어 있지 않은 값만 허용; 로그 연결 보조용 |
| `investment_amount_krw` | 정수 | 필수 | 1,000,000~1,000,000,000 |
| `investment_period_months` | 정수 | 필수 | 1~60 |
| `risk_profile` | 열거형 | 필수 | `conservative`, `moderate`, `aggressive` |
| `max_loss_percent` | 숫자 | 필수 | 0~100 |
| `preferred_asset_types` | 문자열 배열 | 선택 | 확정된 선택값만; 미입력 허용 |
| `theme_industry_keywords` | 문자열 배열 | 선택 | 최대 5개; ETF명 또는 KRX 기초지수·분류 텍스트에 하나 이상 일치하는 후보만 유지 |
| `cash_ratio_percent` | 숫자 또는 null | 선택 | 입력 시 0~100, 미입력에 기본값 적용 금지 |

## 응답 모델: `AnalysisResponse`

| 필드 | 모든 상태 | 설명 |
| --- | --- | --- |
| `request_id` | 예 | 서버 생성 요청 식별자 |
| `status` | 예 | `completed`, `partial`, `failed` |
| `analysis` | 완료·부분 | 후보, 정량, 주요 종목 편입 현황, 뉴스, 종합 결과, 구성 후보 |
| `data_context` | 완료·부분 | 출처, 수집 시점, 기준일, 통화, 단위, DB 캐시 사용 또는 KRX 갱신 상태 |
| `candidate_filtering` | 부분 | KRX 수집 건수, 규칙 기반 1차 후보 최대 200개, 제외 건수 |
| `quantitative_analysis` | 부분 | 요청 분석 기간의 지표와 적합 점수·순위 |
| `news_collection` | 부분 | 정량 적합점수 상위 30개 ETF를 검색어로 한 최근 30일 NAVER 뉴스 원천; 감성·요약은 포함하지 않음 |
| `warnings` | 부분 | 누락 데이터·보류 정책·제한 사항 |
| `errors` | 부분·실패 | 필드 또는 처리 단계, 안전한 오류 코드와 사용자 메시지 |
| `disclaimer` | 예 | 정보 제공 목적, 성과 비보장, 최종 판단 책임 |

## 분석 하위 모델의 책임

| 모델 | 소유 모듈 | 핵심 내용 |
| --- | --- | --- |
| `ValidatedInvestmentConditions` | `models`, `services` | 검증·정규화된 투자 조건 |
| `EtfMetadata`, `EtfDetail`, `PriceSeries` | `models`, `collectors` | 식별자·원천 데이터·출처 메타데이터 |
| `QuantitativeMetrics`, `ScoreResult` | `models`, `quantitative` | 지표, 정규화 값, 점수, 순위, 산출 불가 사유 |
| `HoldingExposure` | `models`, `quantitative` | 주요 종목의 ETF 편입률·총 ETF 자산 비중, 계산 모집단·기준일·제외 사유 |
| `NewsItem`, `NewsAnalysis` | `models`, `news`, `ai` | 원문 근거, 감성·요약, `no_news` 또는 AI 실패 상태 |
| `NewsCollectionResult`, `EtfNewsCollection`, `NewsArticle` | `api/schemas`, `collectors`, `services` | NAVER 원천 기사와 ETF별 검색어·순위 연결; 감성·요약은 미포함 |
| `IntegratedCandidate` | `models`, `services` | 정량과 뉴스의 근거·위험·한계를 분리한 후보 결과 |
| `PortfolioPreparation` | `models`, `portfolio` | 구성 후보·제약·현금성 비중·`allocation_pending` |
| `AnalysisError`, `AnalysisWarning` | `core`, `models` | 공개 가능한 오류·경고와 단계 정보 |
| `EtfCandidate`, `CandidateFilteringResult` | `api/schemas`, `quantitative` | 1차 후보의 KRX 원천 요약과 규칙 적용 결과 |

## 오류 모델: `AnalysisError`

`scope`(필드 또는 단계), `code`, `message`, `retryable`만 외부에 제공한다. HTTP 상태, 공급자 이름, 원본 예외, API 키·토큰은 로그에만 안전하게 기록하며 응답에 포함하지 않는다.

## ETF 구성 종목 조회

| 항목 | 내용 |
| --- | --- |
| Method | `GET` |
| Endpoint | `/api/etfs/{ticker}/holdings` |
| 설명 | 결과 화면에서 선택한 ETF의 운용사 공식 구성종목 PDF 데이터를 조회한다. 현재는 KODEX만 지원한다. |
| 성공 상태 코드 | `200 OK` |
| 실패 상태 코드 | `404 Not Found`(현재 KRX ETF 데이터에 없는 종목), `400 Bad Request`(잘못된 코드) |

응답은 `ticker`, `etf_name`, `as_of_date`, `source`, `source_url`, `data_origin`, `cache_status`, `constituents`를 포함한다. 각 구성 종목은 `constituent_code`, `constituent_name`, `weight_percent`, 수량·현재가·평가액(원천 제공 시)을 가진다.

- 같은 날 다시 조회하면 SQLite의 `etf_constituent_snapshots`를 사용한다.
- 해당일의 첫 조회는 삼성자산운용 KODEX 공식 구성종목(PDF) 원천을 확인해 저장한다.
- 비중이 없거나 0인 현금성 항목은 제외하고, 원천 건수와 제외 건수를 응답에 남긴다.
- KODEX 이외 ETF는 `unsupported_provider`, 공식 원천 장애는 `source_unavailable` 상태로 구분한다.

## 금지 필드

MVP 응답에는 사용자 계정, 분석 이력, 주문 정보, 증권 계좌 정보, ETF별 실제 비중·금액, 포트폴리오 기대수익률·샤프지수, 확정 수익 또는 매매 지시를 넣지 않는다.
