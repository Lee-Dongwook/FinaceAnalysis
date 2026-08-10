# Backend

FastAPI 서버입니다. 시작 시 SQLite에 최신 영업일 ETF 스냅샷과 최근 12개월 이력이 있는지 확인하고, 부족한 날짜만 KRX Open API에서 수집합니다.

공개 API:

- `GET /health`
- `POST /api/analyses`
- `POST /api/news-analyses`
- `GET /api/etfs/{ticker}/holdings`

정량 계산은 일반 Python 코드로 처리합니다. NAVER 뉴스 검증, OpenAI 감성 분석, 포트폴리오 산출은 각각 별도 서비스 책임입니다. API 키는 루트 `.env`에서만 읽습니다.

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
