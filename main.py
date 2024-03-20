from excel.xlsx_io import get_persons_list, output_results

from scraper.scraper import search_inn_
import asyncio

from log import InnSearcherLogger

from datetime import datetime


INPUT_FILE = 'excel/input/persons_table.xlsx'
OUTPUT_FILE = f'excel/output/search_inn_{datetime.now().strftime(format="%Y-%m-%d_%H-%M-%S")}.xlsx'


async def main() -> None:
	logger = InnSearcherLogger()

	try:
		persons_list = get_persons_list(input_excel_file=INPUT_FILE)
	except Exception as e:
		logger.error(f'Failed to get persons list: {type(e)} - {e}')
		return

	search_inn_tasks = [search_inn_(person=person, logger=logger, output_file=OUTPUT_FILE) for person in persons_list]
	for search_inn_task in asyncio.as_completed(search_inn_tasks):
		await search_inn_task


if __name__ == '__main__':
	import time

	print('------------- STARTED -------------')
	start_time = time.time()

	loop = asyncio.get_event_loop()
	loop.run_until_complete(main())

	print('------------- FINISHED -------------')
	print(f'Time: {time.time() - start_time}')
