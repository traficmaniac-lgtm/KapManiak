# KapManiak v0.1 — PAPER Rotator (Algorithm + GUI)

KapManiak v0.1 is a desktop GUI app that simulates an Adaptive Capital Rotation strategy on Binance spot data (public HTTP).  
It **does not** place real orders. All switches are paper-only and virtual.

## Install

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
```

On Windows:

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Run

```bash
python app.py
```

## Algorithm (1-page summary)

**Universe**  
Default universe is ~20 liquid USDT pairs. You can edit the universe in the Settings dialog.

**Price sampling**  
Every 10 seconds the app fetches last prices from Binance `/api/v3/ticker/price`.

**Score**  
Weighted momentum vs USDT:

```
score = 0.5*ret_15m + 0.3*ret_1h + 0.2*ret_4h
```

If there isn't enough price history to compute all three returns, a coin is excluded until history is sufficient.

**Switch rules**

1. Leader = highest score (non-blacklisted).
2. Switch only if:
   - **edge >= 0.5%** (leader score - current score).
   - **Confirm N = 3** consecutive checks.
   - **Min hold** time passed (default 15 min).
   - **Cooldown** passed after last switch.
   - **Max switches/day** not exceeded.
3. Optional net edge gate (default ON):
   - Uses trading cost model.
   - Requires net edge >= 0.25%.

**Cost model**

Per trade cost (default):
- Fee: 7.5 bps
- Slippage: 5 bps
- Spread buffer: 2 bps

Switching uses two trades (A → USDT → B):

```
cost_bps_total = 2 * (fee + slippage + spread_buffer)
net_edge = edge - cost_bps_total
```

**Paper execution**

- Single-asset allocation at all times.
- Equity always tracked in USDT using last price.
- Switching simulates two trades and deducts costs.
- “Park to USDT” button sells current asset to USDT (paper).

**Logging**

Every cycle logs a DECISION with reason codes. Logs appear in the GUI and in `./logs/app.log` (rotating).

**Persistence**

Equity curve and switch history are stored in `./data/kapmaniak.sqlite` and loaded on restart.

## Reason codes

- `HOLD_MIN_HOLD` — Still within min-hold window.
- `HOLD_COOLDOWN` — Cooldown window is active.
- `HOLD_EDGE_TOO_SMALL` — Leader edge is below 0.5% threshold.
- `HOLD_NET_EDGE_TOO_SMALL` — Net edge below configured net-edge gate.
- `HOLD_CONFIRMING` — Waiting for confirm-N consistency.
- `HOLD_MAX_SWITCHES` — Daily switch limit reached.
- `SWITCH` — Switch executed.
- `DATA_STALE` — Data is stale; safe mode, no switching.
- `ERROR` — Data or scoring unavailable.

## Files & structure

```
app.py
config.py
engine/
  data_provider.py
  scoring.py
  cost_model.py
  paper_broker.py
  decision_engine.py
  storage.py
  logger.py
ui/
  main_window.py
```
