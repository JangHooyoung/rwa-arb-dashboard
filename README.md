# RWA 스프레드 차익 대시보드 (RISEx ↔ TXFlow)

정적 페이지. 서버 없음, 브라우저가 거래소에 직접 연결해.

- `index.html`: 대시보드
- `history.json`: 과거 시점별 두 거래소 종가 `[t, rise_close, tx_close]` (7일 1시간봉, 3일 5분봉)와 RISE 펀딩·24h 거래량 스냅샷. 가격 차이 = rise_close − tx_close (USD)
- `build_history.py`: history.json 재생성 (`python3 build_history.py`)

데이터 출처
- TXFlow 호가 `l2Book`, 펀딩·거래량 `marketTicker`: `POST https://rpc.txflow.com/info` (CORS `*`, 브라우저 직접)
- RISEx 호가: `wss://ws.rise.trade/ws` orderbook 채널 (REST는 rise.trade/localhost 외 CORS 차단)
- RISEx 캔들·펀딩·거래량: REST 전용이라 build_history.py가 미리 받아 history.json에 넣음
- 실시간 샘플은 1분마다 브라우저 localStorage에 3일치까지 쌓임
