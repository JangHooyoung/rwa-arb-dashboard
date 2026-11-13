#!/usr/bin/env python3
"""Build history.json for the RWA arb dashboard (read-only public APIs, no auth).

RISEx REST blocks CORS from non-rise.trade origins, so its candles, funding and
24h volume cannot be fetched by the browser. This script fetches them server-side
and writes a static history.json next to index.html. Re-run to refresh.
"""
import json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent / "history.json"
TX_INFO = "https://rpc.txflow.com/info"
TX_VER = "2026-08-16"
RISE_TV = "https://api.rise.trade/v1/markets/id/{mid}/trading-view-data?interval={iv}&from={a}&to={b}"
RISE_MARKETS = "https://api.rise.trade/v1/markets"

PAIRS = [  # symbol, rise market_id, txflow instrument id
    ("XAU", 17, 51), ("META", 37, 78), ("MSTR", 29, 54), ("SPY", 27, 80), ("TSLA", 32, 59),
    ("QQQ", 26, 126), ("GOOGL", 42, 101), ("CL", 19, 53), ("XAG", 18, 52),
]
WINDOWS = {"h1": (3600, 7 * 86400, "1h"), "m5": (300, 3 * 86400, "5m")}
UA = {"User-Agent": "rwa-arb-dashboard/1.0", "Accept": "application/json"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.loads(r.read())


def tx(body):
    req = urllib.request.Request(TX_INFO, data=json.dumps(body).encode(), method="POST",
                                 headers={**UA, "Content-Type": "application/json", "x-api-version": TX_VER})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rise_candles(mid, step, start, end):
    b = get(RISE_TV.format(mid=mid, iv=step * 10**9, a=start * 10**9, b=end * 10**9))
    rows = (b.get("data") or {}).get("data") or []
    out = {}
    for r in rows:
        t = int(int(r["time"]) // 10**9)
        out[t] = float(r["close"])
    return out


def tx_candles(iid, iv, start, end):
    b = tx({"type": "candleSnapshot", "req": {"coin": str(iid), "interval": iv,
                                               "startTime": start * 1000, "endTime": end * 1000}})
    return {int(r["t"]) // 1000: float(r["c"]) for r in (b.get("data") or [])}


def series(sym, rid, tid, key):
    step, span, iv = WINDOWS[key]
    end = int(time.time()) // step * step
    start = end - span
    rc = rise_candles(rid, step, start, end + step)
    tc = tx_candles(tid, iv, start, end + step)
    pts = []
    for t in sorted(set(rc) & set(tc)):
        r, x = rc[t], tc[t]
        pts.append([t, r, x])
    return sym, key, pts, len(rc), len(tc)


def diffs(pts):
    return [p[1] - p[2] for p in pts]


def stats(vals, nd=6):
    n = len(vals)
    if n < 2:
        return None
    m = sum(vals) / n
    sd = (sum((v - m) ** 2 for v in vals) / (n - 1)) ** 0.5
    return {"n": n, "mean": round(m, nd), "std": round(sd, nd)}


def main():
    markets = {m["market_id"]: m for m in get(RISE_MARKETS)["data"]["markets"]}
    jobs = [(s, r, t, k) for s, r, t in PAIRS for k in WINDOWS]
    res = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for sym, key, pts, nr, nt in ex.map(lambda a: series(*a), jobs):
            res.setdefault(sym, {})[key] = pts
            print(f"{sym:6} {key}: rise={nr} tx={nt} joined={len(pts)}")
    pairs = []
    for s, r, t in PAIRS:
        m = markets.get(str(r), {})
        h1 = res[s]["h1"]
        pairs.append({
            "symbol": s, "rise_id": r, "tx_id": t,
            "rise_name": (m.get("config") or {}).get("name"),
            "rise_funding_1h": float(m.get("current_funding_rate") or 0),
            "rise_vol24h": float(m.get("quote_volume_24h") or 0),
            "stats_h1_usd": stats(diffs(h1)),
            "stats_m5_usd": stats(diffs(res[s]["m5"])),
            "h1": h1, "m5": res[s]["m5"],
        })
    now = int(time.time())
    OUT.write_text(json.dumps({
        "generated_at": now,
        "generated_at_iso": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "note": "per-timestamp candle closes of both venues; diff_usd = rise_close - tx_close (approx, not fills)",
        "fields": ["t_sec", "rise_close", "tx_close"],
        "pairs": pairs,
    }, separators=(",", ":")))
    print("wrote", OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
