# BTC Infinite Resonance Strip

Desktop-приложение на PySide6, которое рисует «бесконечную ленту» из 1px колонок, кодируя параметры рынка BTCUSDT.

## Запуск

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Управление

- **Space** — Pause/Resume (остановка прокрутки, WS продолжает работать)
- **C** — Clear (очистить ленту)
- **F** — Переключить режимы **STACKED** / **BANDS**
- **S** — Сохранить PNG скриншот в `apps/btc_resonance_strip/out/`

## Примечания

- В заголовке окна показывается режим.
- В HUD отображаются: статус WS, age_ms, mid, tps, volps, spread_bps, imbalance, micro_vol.
