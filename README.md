# Finance Analysis MVP

국내 상장 ETF를 대상으로 투자 조건, KRX 일별 데이터, 정량 분석, 최근 뉴스 감성 분석을 종합해 정보 제공용 포트폴리오를 보여주는 MVP입니다. 투자 성과를 보장하거나 투자 권유를 하지 않습니다.

## 현재 구현 범위

- FastAPI 분석 API 및 Vite 기반 웹 화면
- KRX Open API ETF 일별 데이터 수집과 SQLite 12개월 이력 보관
- 규칙 기반 1차 후보 필터링, 정량 지표·적합 점수 계산
- NAVER 뉴스 검색, 중복·기간·관련성 검증, OpenAI 감성 분석 결과 저장
- 포트폴리오 결과와 KODEX 공식 구성 종목 조회

## 실행

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Backend 상태 확인은 `http://127.0.0.1:8000/health`, API 문서는 `http://127.0.0.1:8000/docs`, 기본 Frontend 주소는 `http://localhost:5173`입니다.

## 환경 변수

루트의 `.env.example`을 복사해 `.env`를 만들고 KRX, NAVER, OpenAI 키를 입력합니다. 실제 키와 `data/finance_analysis.db`는 저장소에 포함하지 않습니다.

## 주요 문서

- [요구사항](docs/requirements.md)
- [기능 분해](docs/function-breakdown.md)
- [MVP 계획](docs/mvp-plan.md)
- [API 계약](docs/api-contract.md)
- [테스트 계획](docs/test-plan.md)
