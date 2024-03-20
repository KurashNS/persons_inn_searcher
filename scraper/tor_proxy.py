from aiohttp_socks import ProxyConnector

from stem import Signal
from stem.control import Controller

import re

import psutil
import subprocess
from threading import Thread

import time


_TOR_PROCESS_NAMES = ['tor', 'tor.exe']


class TorProxyConnector(ProxyConnector):
    def __init__(self) -> None:
        self._circuits_switch_thread = Thread(target=self._switch_tor_circuits)
        self._start_tor_process()

        super().__init__(host='127.0.0.1', port='9050')

    @property
    def _is_tor_process_running(self) -> bool:
        return any(process.name() in _TOR_PROCESS_NAMES for process in psutil.process_iter(['name']))

    async def __aenter__(self) -> "TorProxyConnector":
        await super().__aenter__()
        return self

    def _start_tor_process(self) -> None:
        if not self._is_tor_process_running:
            subprocess.Popen(args='tor.exe', shell=True)

            start_time = time.time()
            while time.time() - start_time < 10:
                if self._is_tor_process_running:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Failed to start Tor process')

        self._wait_for_tor_bootstrap()
        self._circuits_switch_thread.start()

    @staticmethod
    def _wait_for_tor_bootstrap() -> None:
        with Controller.from_port(port=9051) as controller:
            controller.authenticate(password='tor-passwd')
            while True:
                bootstrap_info = controller.get_info('status/bootstrap-phase')
                bootstrap_progress = re.search(pattern=r'PROGRESS=(\d+)', string=bootstrap_info).group(1)
                if bootstrap_progress == '100':
                    break

                time.sleep(1)

    def _switch_tor_circuits(self) -> None:
        with Controller.from_port(port=9051) as controller:
            controller.authenticate(password='tor-passwd')
            while self._is_tor_process_running:
                if controller.is_newnym_available():
                    controller.signal(Signal.NEWNYM)

    def _terminate_tor_process(self) -> None:
        for process in psutil.process_iter(['name']):
            if process.name() in _TOR_PROCESS_NAMES:
                process.kill()

        if self._circuits_switch_thread:
            self._circuits_switch_thread.join(timeout=1)

    async def __aexit__(self, *args, **kwargs) -> None:
        await super().__aexit__(*args, **kwargs)
        self._terminate_tor_process()


if __name__ == '__main__':
    import asyncio
    import aiohttp

    from stem import ControllerError

    from logging import Logger

    logger = Logger(__name__)


    async def check_ip(session):
        async with session.get(url='https://api.ipify.org') as resp:
            return await resp.text()


    async def test():
        try:
            async with TorProxyConnector() as tor_connector:
                async with aiohttp.ClientSession(connector=tor_connector) as session:
                    tasks = [check_ip(session) for _ in range(500)]
                    for task in asyncio.as_completed(tasks):
                        print(await task)
        except (subprocess.SubprocessError, RuntimeError, ControllerError) as e:
            print(f'{type(e)} - {e}')

    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())
