# Finance Analysis MVP

국내 상장 ETF를 대상으로 사용자의 투자 조건, KRX 일별 시세, 정량 지표, 최근 뉴스·감성 정보를 한 화면에서 확인하는 정보 제공용 웹 애플리케이션입니다. 이 서비스는 투자 권유가 아니며, 투자 성과를 보장하지 않습니다.

## 구현 범위

### 투자 조건 입력과 후보 선별

- 투자금(100만 원~10억 원), 투자 기간(1~60개월), 위험 성향, 허용 손실을 입력합니다.
- 선호 자산 유형(주식·채권·배당), 현금성 비중, 관심 테마·산업군 키워드를 선택적으로 반영합니다.
- KRX ETF 데이터에서 가격·거래 데이터가 유효하고 투자금으로 매수 가능한 ETF를 1차 후보로 선별합니다. 후보는 최대 200개입니다.

### 데이터 수집과 보관

- 서버 시작 시 최신 영업일 ETF 스냅샷과 최근 12개월 이력을 확인하고, 없는 날짜만 KRX Open API에서 수집합니다.
- ETF 시세·뉴스·구성 종목 데이터는 SQLite에 저장해 당일 데이터를 재사용합니다.
- 뉴스는 NAVER 뉴스 검색 결과에서 중복 URL, 검색 기간, ETF 관련성을 검증합니다.
- KODEX ETF는 삼성자산운용의 공식 구성 종목 PDF를 조회할 수 있습니다. 지원하지 않는 운용사의 ETF는 구성 종목 조회 결과에 지원 제한이 표시됩니다.

### 분석 결과

- 종가 기준 기간 수익률, 연환산 변동성, 최대 낙폭(MDD), 샤프지수, 평균 거래대금을 계산합니다.
- 위험 성향별 가중치로 0~100점의 적합 점수와 순위를 산출합니다. 주간 표본일과 KOFR 가정은 환경 변수로 설정합니다.
- 상위 정량 후보의 뉴스에 대해 OpenAI 감성 분석을 수행하고, 검증 뉴스 수·감성 점수·핵심 이슈·위험 요인을 표시합니다.
- 정량 점수와 뉴스 근거가 충족되면 투자 가능 금액, 현금 비중, 매수 단위, ETF별 비중을 포함한 정보 제공용 포트폴리오를 구성합니다.
- 웹 화면에서는 분석 단계별 상태, 정량 지표 정렬 표, 추천 ETF 비교 레이더 차트, ETF별 선정·위험 근거, 구성 종목을 확인할 수 있습니다.

## 기술 스택

| 구분        | 사용 기술                                                           |
| ----------- | ------------------------------------------------------------------- |
| Frontend    | TypeScript, Vite                                                    |
| Backend     | Python, FastAPI, Uvicorn                                            |
| 데이터 저장 | SQLite                                                              |
| 외부 데이터 | KRX Open API, NAVER 뉴스 검색 API, 삼성자산운용 공식 구성 종목 자료 |
| AI 분석     | OpenAI API                                                          |
| 테스트      | pytest                                                              |

## 프로젝트 구조

```text
.
├── backend/
│   ├── app/                 # FastAPI 라우트, 수집기, 분석·포트폴리오 서비스
│   ├── tests/               # 단위·통합 테스트
│   └── requirements.txt
├── frontend/
│   └── src/                 # Vite 기반 분석 화면과 API 호출 코드
├── data/                    # 로컬 SQLite 데이터베이스(버전 관리 제외)
├── docs/                    # 요구사항, API 계약, 테스트 계획 등
├── .env.example             # 환경 변수 예시
└── README.md
```

## 실행 전 준비

1. 루트의 `.env.example`을 복사해 `.env`를 만듭니다.
2. 필요한 API 키와 설정값을 `.env`에 입력합니다. 실제 키는 저장소에 커밋하지 않습니다.

```bash
cp .env.example .env
```

분석 파이프라인을 모두 사용하려면 KRX, NAVER, OpenAI 키가 필요합니다. KRX 키가 없으면 ETF 데이터 수집 단계가 실패하며, NAVER 또는 OpenAI 설정이 없으면 해당 뉴스·감성 단계는 오류 또는 제한 상태로 응답될 수 있습니다. KODEX 구성 종목 조회는 별도 API 키가 필요하지 않습니다.

주요 환경 변수는 다음과 같습니다.

| 범주             | 변수                                                                                                        |
| ---------------- | ----------------------------------------------------------------------------------------------------------- |
| KRX ETF 시세     | `KRX_API_KEY`, `ETF_DATABASE_PATH`                                                                          |
| 정량 계산 가정   | `KOFR_ANNUAL_RATE_PERCENT`, `WEEKLY_SAMPLE_WEEKDAY`                                                         |
| NAVER 뉴스       | `NAVER_API_KEY_ID`, `NAVER_API_KEY`, `NEWS_RELEVANCE_THRESHOLD`                                             |
| OpenAI 감성 분석 | `OPENAI_API_KEY`, `OPENAI_SENTIMENT_MODEL`, `SENTIMENT_MINIMUM_ARTICLES`, `SENTIMENT_MAX_PARALLEL_REQUESTS` |
| Frontend 연결    | `VITE_API_BASE_URL`(미설정 시 `http://127.0.0.1:8000`)                                                      |

## 실행 방법

터미널을 두 개 열어 Backend와 Frontend를 각각 실행합니다.

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

- 웹 화면: `http://localhost:5173`
- 상태 확인: `http://127.0.0.1:8000/health`
- API 문서(Swagger UI): `http://127.0.0.1:8000/docs`

## API

| 메서드 | 경로                          | 설명                                                     |
| ------ | ----------------------------- | -------------------------------------------------------- |
| `GET`  | `/health`                     | 서버 상태 확인                                           |
| `POST` | `/api/analyses`               | ETF 수집, 후보 선별, 정량·뉴스·감성·포트폴리오 분석 요청 |
| `POST` | `/api/news-analyses`          | 특정 ETF의 검증 뉴스와 감성 분석 요청                    |
| `GET`  | `/api/etfs/{ticker}/holdings` | ETF 구성 종목 조회                                       |

분석 API 요청 예시는 다음과 같습니다.

```json
{
  "investment_amount_krw": 10000000,
  "investment_period_months": 12,
  "quantitative_analysis_period_months": 12,
  "risk_profile": "moderate",
  "max_loss_percent": 20,
  "preferred_asset_types": ["equity"],
  "theme_industry_keywords": ["반도체"],
  "cash_ratio_percent": 10
}
```

응답의 `status`, `warnings`, `errors`를 함께 확인하세요. 외부 데이터 제공자 또는 AI 분석이 일시적으로 불가능한 경우에도, 가능한 단계까지의 결과를 `partial` 상태로 반환하도록 구성되어 있습니다. 상세 필드 정의는 [API 계약](docs/api-contract.md)을 참고하세요.

## 테스트와 확인 방법

Backend 테스트는 `backend` 디렉터리에서 실행해야 `app` 모듈을 올바르게 찾습니다.

```bash
cd backend
python -m pytest tests -q
```

Frontend 타입 검사와 프로덕션 빌드는 다음과 같습니다.

```bash
cd frontend
npm run build
```

수동 확인 예시:

1. Backend와 Frontend를 실행한 뒤 웹 화면을 엽니다.
2. 투자금 `10,000,000원`, 투자 기간 `12개월`, 위험 성향 `중립형`, 허용 손실 `20%`를 입력하고 분석을 요청합니다.
3. 분석 진행 상태와 1차 후보 정량 표가 표시되는지 확인합니다.
4. 포트폴리오가 생성된 경우 ETF의 `보기` 버튼을 선택해 구성 종목을 확인합니다.
5. 실패하면 Backend 콘솔 로그와 응답의 `errors` 필드를 확인하고, KRX·NAVER·OpenAI 환경 변수 설정을 점검합니다.

## 데이터 기준과 한계

- 가격·거래 데이터는 KRX ETF 일별 데이터, 통화는 KRW, 단위는 원·주입니다. 응답의 `as_of_date`와 `data_origin`으로 기준일과 데이터 출처를 확인할 수 있습니다.
- 정량 지표는 종가를 기준으로 하며, 조정 종가가 아닙니다. 요청 기간보다 저장된 이력이 짧거나 필요한 주간 관측치가 부족하면 일부 지표·점수는 산출되지 않을 수 있습니다.
- KOFR 값과 주간 표본일은 환경 변수의 가정을 사용하므로, 화면의 계산 기준을 함께 확인해야 합니다.
- 뉴스 감성 결과는 수집 시점과 검증된 기사에 의존하는 보조 정보이며, 사실 확인이나 수익 예측을 대체하지 않습니다.
- 최종 투자 판단과 책임은 사용자에게 있습니다.

## 관련 문서

- [요구사항](docs/requirements.md)
- [기능 분해](docs/function-breakdown.md)
- [MVP 계획](docs/mvp-plan.md)
- [프로젝트 구조](docs/project-structure.md)
- [API 계약](docs/api-contract.md)
- [테스트 계획](docs/test-plan.md)
- [분석 API 안정화·비동기 전환 제안](docs/async-analysis-refactoring-proposal.md)
