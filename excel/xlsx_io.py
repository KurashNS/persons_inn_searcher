from urllib.parse import urlencode
from itertools import product

from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows

from datetime import datetime

from openpyxl.workbook.workbook import Workbook
import pandas as pd

import threading


_thread_lock = threading.Lock()


class Person:
    def __init__(self) -> None:
        self.last_name: str = ''
        self.first_name: str = ''
        self.patronymic: str = ''
        self.birthday: str = ''

        self.passport_series: str = ''
        self.passport_number: str = ''

        self.inn: str = ''
        self.inn_search_status: str = ''

    @property
    def person_id(self) -> str:
        return f'{self.passport_series} {self.passport_number}'

    @property
    def ogu_form_data(self) -> str:
        return urlencode({
            'last_name': self.last_name,
            'first_name': self.first_name,
            'patronymic': self.patronymic,
            'birthday': self.birthday,
            'document_type': '21',
            'document_value': f'{self.passport_series[:2]} {self.passport_series[2:]} {self.passport_number}'
        })

    @property
    def nalog_ru_form_data(self) -> dict[str, str]:
        search_inn_form = {
            'c': 'find',
            'captcha': '',
            'captchaToken': '',
            'fam': self.last_name,
            'nam': self.first_name,
            'otch': self.patronymic,
            'opt_otch': '1',
            'bdate': self.birthday,
            'doctype': '21',
            'docno': f'{self.passport_series[:2]} {self.passport_series[2:]} {self.passport_number}',
            'docdt': '',
        }
        key_to_pop = 'opt_otch' if self.patronymic else 'otch'
        search_inn_form.pop(key_to_pop)
        return search_inn_form

    @classmethod
    def from_json(cls, person_json: dict[str: str]) -> 'Person':
        attributes_map = {
            'Фамилия': 'last_name',
            'Имя': 'first_name',
            'Отчество': 'patronymic',
            'Дата рождения': 'birthday',
            'Серия': 'passport_series',
            'Номер': 'passport_number',
            'ИНН': 'inn',
            'Статус': 'inn_search_status'
        }

        person = cls()
        for json_attr_name, cls_attr_name in product(person_json, attributes_map):
            if cls_attr_name in json_attr_name:
                setattr(person, attributes_map[cls_attr_name], person_json[json_attr_name])

        return person

    def to_json(self) -> dict[str, str]:
        return {
            'Фамилия': self.last_name,
            'Имя': self.first_name,
            'Отчество': self.patronymic,
            'Дата рождения': self.birthday,
            'Серия': self.passport_series,
            'Номер': self.passport_number,
            'ИНН': self.inn,
            'Статус': self.inn_search_status
        }


def get_persons_list(input_excel_file: str) -> list[Person]:
    persons_table_workbook = load_workbook(input_excel_file)
    persons_table_sheet = persons_table_workbook.active

    attributes_map = {
        'Фамилия': 'last_name',
        'Имя': 'first_name',
        'Отчество': 'patronymic',
        'Дата рождения': 'birthday',
        'Серия': 'passport_series',
        'Номер': 'passport_number'
    }

    persons_list = []
    for row in persons_table_sheet.iter_rows(min_row=2, values_only=True):
        person = Person()
        for cell, col in zip(row, range(persons_table_sheet.min_column, persons_table_sheet.max_column + 1)):
            col_name = persons_table_sheet.cell(row=1, column=col).value
            if col_name in attributes_map and cell:
                attribute = attributes_map[col_name]
                value = str(cell).strip().capitalize()
                if 'Дата рождения' in col_name and isinstance(cell, datetime):
                    value = cell.strftime(format='%d.%m.%Y')
                elif 'Серия' in col_name or 'Номер' in col_name:
                    value = '0' * (4 - len(value) if 'Серия' in col_name else 6 - len(value)) + value
                setattr(person, attribute, value)
            else:
                break
        else:
            persons_list.append(person)

    return persons_list


def output_results(output_excel_file: str, checked_person: Person) -> None:
    with _thread_lock:
        try:
            wb = load_workbook(output_excel_file)
            header = False
        except FileNotFoundError:
            wb = Workbook()
            header = True

        ws = wb.active

        person_json = checked_person.to_json()
        for row in dataframe_to_rows(pd.json_normalize(data=person_json), index=False, header=header):
            ws.append(row)

        wb.save(output_excel_file)
