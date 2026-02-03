# BTC “Schumann Resonance” Market Visualizer

A PySide6 desktop visualizer that renders BTC market activity as a standing-wave field. It uses Binance WebSocket multi-streams and draws a 1px time slice per frame.

## Run
```bash
python -m pip install -r requirements.txt
python main.py
```

## Controls
- **Space** — Pause / Resume
- **C** — Clear canvas
- **F** — Toggle stacked vs wave mode
- **S** — Save PNG (to `out/`)

## Notes
- WebSocket reconnect is automatic.
- Rendering runs at ~30–60 FPS.
- No computations occur inside `paintEvent`.
