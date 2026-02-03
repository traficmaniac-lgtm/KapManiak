# BTC Schumann Resonance — LIVE

Real-time visualizer inspired by Schumann resonance and classic spectrum analyzers.

## How to run

```bash
python -m btc_schumann_resonance.main
```

## Notes

- Each tick draws a 1-pixel column and scrolls the buffer to maintain an infinite ribbon of time.
- Auto-exposure maintains target brightness to prevent long-run dimming.
- The crown (top 27%) uses a Hann-windowed spectrum over energy history.
- Modes: CALM, FLOW, NOISE, SHOCK.
