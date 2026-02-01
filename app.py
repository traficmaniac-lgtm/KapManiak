from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from config import AppConfig
from engine.data_provider import BinanceDataProvider
from engine.decision_engine import DecisionEngine
from engine.logger import LogEmitter, setup_logging
from engine.storage import Storage
from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    config = AppConfig()

    log_emitter = LogEmitter()
    logger = setup_logging(log_emitter)

    storage = Storage(logger=logger)
    data_provider = BinanceDataProvider(logger=logger)
    decision_engine = DecisionEngine(
        config=config,
        data_provider=data_provider,
        storage=storage,
        logger=logger,
    )
    decision_engine.log_startup_history()

    window = MainWindow(
        config=config,
        decision_engine=decision_engine,
        log_emitter=log_emitter,
    )
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
