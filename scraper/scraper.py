from logging import Logger
from log import InnSearcherLogger

from excel.xlsx_io import Person

import ua_generator
from aiohttp_socks import ProxyConnector, ProxyType, ProxyError, ProxyConnectionError, ProxyTimeoutError
from scraper.tor_proxy import get_proxy_connector

from aiohttp import ClientSession, ClientError, ClientResponseError
import asyncio

from tenacity import retry, retry_if_exception_type, wait_fixed, wait_random, stop_after_attempt

from bs4 import BeautifulSoup
import re

from excel.xlsx_io import output_results


_semaphore = asyncio.Semaphore(15)


class BaseClient:
	def __init__(self, person: Person, session: ClientSession,
	             headers: dict[str: str], logger: Logger) -> None:
		self._person = person
		self._person_id = person.person_id

		ua = ua_generator.generate(device='desktop')
		self._headers = {
			'Accept': '*/*',
			'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
			'Accept-Language': 'ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
			'Connection': 'keep-alive',
			'DNT': '1',
			'Sec-Fetch-Dest': 'empty',
			'Sec-Fetch-Mode': 'cors',
			'Sec-Fetch-Site': 'same-origin',
			'X-Requested-With': 'XMLHttpRequest',
			'User-Agent': ua.text,
			'sec-ch-ua': ua.ch.brands,
			'sec-ch-ua-mobile': ua.ch.mobile,
			'sec-ch-ua-platform': ua.ch.platform
		}
		self._headers.update(headers)

		self._session = session
		self._session.headers.update(self._headers)

		self._logger = logger


class NalogRuClient(BaseClient):
	def __init__(self, person: Person, session: ClientSession, logger: Logger) -> None:
		self._base_url = 'https://service.nalog.ru/'
		self._headers = {'Origin': 'https://service.nalog.ru', 'Referer': 'https://service.nalog.ru/inn.do'}
		super().__init__(person=person, session=session, headers=self._headers, logger=logger)

	async def _create_search_inn_request(self) -> str:
		create_request_url = self._base_url + 'inn-new-proc.json'
		self._logger.info(self._person.nalog_ru_form_data)
		async with self._session.post(url=create_request_url, data=self._person.nalog_ru_form_data) as create_request_resp:
			create_request_resp_json = await create_request_resp.json()

			self._logger.info(
				f'Create search INN request response (nalog.ru | person ID: {self._person_id}): {create_request_resp_json}'
			)

			try:
				request_id = create_request_resp_json['requestId']
				return request_id
			except KeyError as e:
				raise ClientResponseError(
					request_info=create_request_resp.request_info,
					history=create_request_resp.history,
					message=f'Unexpected JSON in request ID response (nalog.ru | person ID: {self._person_id}): {type(e)} - {e}'
				)

	@retry(retry=retry_if_exception_type((ProxyError, ProxyConnectionError, ProxyTimeoutError, ClientError)),
	       wait=wait_fixed(3) + wait_random(min=0, max=2), sleep=asyncio.sleep, stop=stop_after_attempt(10), reraise=True)
	async def search_inn(self) -> tuple[str, str]:
		search_inn_url = self._base_url + 'inn-new-proc.json'
		search_inn_data = {
			'c': 'get',
			'requestId': await self._create_search_inn_request(),
		}
		async with self._session.post(url=search_inn_url, data=search_inn_data) as search_inn_resp:
			search_inn_resp_json = await search_inn_resp.json()

			self._logger.info(f'Search INN response (nalog.ru | person ID: {self._person_id}): {search_inn_resp_json}')

			try:
				inn = str()
				search_status = str()
				search_inn_result_state = search_inn_resp_json['state']
				if search_inn_result_state == 0:
					search_status = 'ИНН не найден'
				elif search_inn_result_state == 1:
					inn = search_inn_resp_json['inn']
					search_status = 'Успешно'
				elif search_inn_result_state == -1:
					raise ClientResponseError(
						request_info=search_inn_resp.request_info,
						history=search_inn_resp.history,
						message=f'nalog.ru unavailable (person ID: {self._person_id})'
					)

				return inn, search_status
			except KeyError as e:
				raise ClientResponseError(
					request_info=search_inn_resp.request_info,
					history=search_inn_resp.history,
					message=f'Unexpected JSON in search INN response (nalog.ru | person ID: {self._person_id}) - {e}'
				)


class OGUClient(BaseClient):
	def __init__(self, person: Person, session: ClientSession, logger: Logger) -> None:
		self._base_url = 'https://oplatagosuslug.ru/'
		self._headers = {'Origin': 'https://oplatagosuslug.ru', 'Referer': 'https://oplatagosuslug.ru/inn/'}
		super().__init__(person=person, session=session, headers=self._headers, logger=logger)

	async def _get_stoken(self) -> str:
		async with self._session.get(url=self._base_url + 'inn/') as get_stoken_resp:
			ogu_inn_service_page = await get_stoken_resp.text()

			ogu_inn_service_page_soup = BeautifulSoup(ogu_inn_service_page, features='html.parser')
			page_scripts = ogu_inn_service_page_soup.find_all(name='script', attrs={'type': 'text/javascript'})
			for script in page_scripts:
				script_text = script.get_text()
				stoken_pattern = re.compile(r"var _stoken = '([^']+)';")
				match = stoken_pattern.search(script_text)
				if match:
					stoken = match.group(1)
					return stoken
			else:
				raise ClientResponseError(
					request_info=get_stoken_resp.request_info,
					history=get_stoken_resp.history,
					message=f'No stoken was found'
				)

	@retry(retry=retry_if_exception_type((ProxyError, ProxyConnectionError, ProxyTimeoutError, ClientError)),
	       wait=wait_fixed(3) + wait_random(min=0, max=2), sleep=asyncio.sleep, stop=stop_after_attempt(10), reraise=True)
	async def search_inn(self) -> tuple[str, str]:
		search_inn_data = {
			'data': self._person.ogu_form_data,
			'_stoken': await self._get_stoken()
		}
		async with self._session.post(url=self._base_url + 'ufns/searchinn/', data=search_inn_data) as search_inn_resp:
			search_inn_resp_json = await search_inn_resp.json()

			self._logger.info(f'Search INN response (OGU | person ID: {self._person_id}): {search_inn_resp_json}')

			try:
				if search_inn_resp_json['status'] == 'success':
					inn = search_inn_resp_json['individualInn']
					search_status = 'Успешно'
				else:
					inn = str()
					search_status = 'ИНН не найден'

				return inn, search_status
			except KeyError as e:
				raise ClientResponseError(
					request_info=search_inn_resp.request_info,
					history=search_inn_resp.history,
					message=f'Unexpected JSON in search INN response - {e}'
				)


async def search_inn_(person: Person, logger: Logger, output_file: str) -> None:
	async with _semaphore:
		inn = str()

		# async with ProxyConnector(proxy_type=ProxyType.HTTP, host='94.103.188.163', port='13811',
		#                           username='yfy5n4', password='s4SsUv') as proxy_conn:
		proxy_conn = TCPConnector()
		async with ClientSession(connector=proxy_conn, raise_for_status=True) as session:
			try:
				inn, search_status = await NalogRuClient(person=person, session=session, logger=logger).search_inn()
			except Exception as e:
				search_status = 'Ошибка'

				logger.error(f'Failed to search INN (nalog.ru | person ID - {person.person_id}): {type(e)} - {e}')
				print(f'Failed to search INN (nalog.ru | person ID - {person.person_id}): {type(e)} - {e}')

			if not inn:
				try:
					inn, search_status = await OGUClient(person=person, session=session, logger=logger).search_inn()
				except Exception as e:
					search_status = 'Ошибка'

					logger.error(f'Failed to search INN (OGU | person ID - {person.person_id}): {type(e)} - {e}')
					print(f'Failed to search INN (OGU | person ID - {person.person_id}): {type(e)} - {e}')

		person.inn = inn
		person.inn_search_status = search_status

		try:
			await asyncio.to_thread(output_results, output_excel_file=output_file, checked_person=checked_person)
		except Exception as e:
			logger.error(f'Failed to output results (person ID - {person.person_id}): {type(e)} - {e} | Results: {person.to_json()}')
			print(f'Failed to output results (person ID - {person.person_id}): {type(e)} - {e} | Results: {person.to_json()}')


if __name__ == '__main__':
	from log import InnSearcherLogger
	from excel.xlsx_io import get_persons_list

	import time


	async def test():
		logger = InnSearcherLogger()

		persons_list = get_persons_list('../excel/input/persons_table.xlsx') * 5
		tasks = [search_inn_(person=person, logger=logger, output_file='../excel/output/test.xlsx') for person in persons_list]

		print('-----START----')
		start_time = time.time()

		tasks_count = 0
		for task in asyncio.as_completed(tasks):
			await task

			tasks_count += 1
			print(f'Task {tasks_count}')

		print(f'Time: {time.time() - start_time}')


	loop = asyncio.get_event_loop()
	loop.run_until_complete(test())
