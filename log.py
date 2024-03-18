from __future__ import annotations

from logging import Logger, FileHandler, Formatter, INFO
from datetime import datetime


def _get_file_handler(level: int | str = INFO) -> FileHandler:
    logs_filename = f'logs/inn_searcher_{datetime.now().strftime(format="%Y-%m-%d_%H-%M-%S")}.log'
    file_handler = FileHandler(filename=logs_filename, encoding='utf-8')

    file_handler.setLevel(level)
    file_handler.setFormatter(Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    return file_handler


class InnSearcherLogger(Logger):
    def __init__(self, name: str = 'InnSearcher', level: int | str = INFO):
        Logger.__init__(self, name=name, level=level)
        self.addHandler(_get_file_handler(level=level))
