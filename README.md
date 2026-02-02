# KapManiak — L2 Trade Helper Calculator (PySide6)

Профессиональный калькулятор торговли Lineage2 (Einhasad → Adena → FunPay) на PySide6.

## Установка и запуск

```bash
python -m pip install -r requirements.txt
python -m src.main
```

Также можно использовать готовые файлы запуска:

```bash
./run.sh
```

```bat
run.bat
```

## Где хранятся данные

- Настройки сохраняются через `QSettings` (реестр Windows).
- Таблица товаров хранится в `data/goods.json` в корне проекта.

## Настройка темы

Тёмная тема задаётся в `src/app_window.py` в блоке `APP_QSS`.

## Структура проекта

```
src/
  main.py
  app_window.py
  widgets/
    metric_card.py
    params_panel.py
    goods_panel.py
  services/
    rate_service.py
    storage.py
  core/
    calc.py
```
