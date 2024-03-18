from excel.xlsx_io import get_persons_list, output_results

from scraper.scraper import search_inn_
import asyncio

from log import InnSearcherLogger

from datetime import datetime


PERSONS_TABLE_EXCEL_FILE_PATH = 'excel/input/persons_table.xlsx'
OUTPUT_EXCEL_FILE = f'excel/output/search_inn_{datetime.now().strftime(format="%Y-%m-%d_%H-%M-%S")}.xlsx'

PROXY_URL = ''


async def main() -> None:
    logger = InnSearcherLogger()

    persons_list = get_persons_list(PERSONS_TABLE_EXCEL_FILE_PATH)
    search_inn_tasks = [search_inn_(person=person, logger=logger) for person in persons_list]

    for search_inn_task in asyncio.as_completed(search_inn_tasks):
        checked_person = await search_inn_task
        await asyncio.to_thread(output_results, output_excel_file=OUTPUT_EXCEL_FILE, checked_person=checked_person)


if __name__ == '__main__':
    import time

    print('------------- STARTED -------------')
    start_time = time.time()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

    print('------------- FINISHED -------------')
    print(f'Time: {time.time() - start_time}')
