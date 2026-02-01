from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QObject, Signal


class LogEmitter(QObject):
    new_log = Signal(str, int)


class QtLogHandler(logging.Handler):
    def __init__(self, emitter: LogEmitter) -> None:
        super().__init__()
        self._emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        self._emitter.new_log.emit(message, record.levelno)


def setup_logging(emitter: LogEmitter) -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("kapmaniak")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        os.path.join("logs", "app.log"), maxBytes=1_000_000, backupCount=3
    )
    file_handler.setFormatter(formatter)

    qt_handler = QtLogHandler(emitter)
    qt_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(qt_handler)

    return logger
