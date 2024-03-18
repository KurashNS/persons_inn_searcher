import ua_generator
from aiohttp import ClientSession

from bs4 import BeautifulSoup

import uuid

import asyncio


ua = ua_generator.generate(device='desktop')

MAX_TASKS_NUM = 5
request_semaphore = asyncio.Semaphore(MAX_TASKS_NUM)


async def get_captcha_token(session: ClientSession):
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Referer': 'https://service.nalog.ru/inn.do',
        'Sec-Fetch-Dest': 'iframe',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': ua.text,
        'sec-ch-ua': ua.ch.brands,
        'sec-ch-ua-mobile': ua.ch.mobile,
        'sec-ch-ua-platform': ua.ch.platform,
    }
    params = {
        'aver': '3.48.6',
        'sver': '4.40.31',
        'pageStyle': 'GM2',
    }
    async with session.get(url='https://service.nalog.ru/static/captcha-dialog.html', params=params, headers=headers) as captcha_token_resp:
        captcha_page = await captcha_token_resp.text()

    captcha_page_soup = BeautifulSoup(captcha_page, features='html.parser')

    captcha_token_el = captcha_page_soup.find(name='input', attrs={'type': 'hidden', 'name': 'captchaToken'})
    captcha_token = captcha_token_el.get('value')
    return captcha_token


async def get_captcha_img(session: ClientSession, captcha_token: str):
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': ua.text,
        'sec-ch-ua': ua.ch.brands,
        'sec-ch-ua-mobile': ua.ch.mobile,
        'sec-ch-ua-platform': ua.ch.platform,
    }
    params = {
        'a': captcha_token,
        'version': '2',
    }
    async with session.get(url='https://service.nalog.ru/static/captcha.bin', params=params, headers=headers) as captcha_resp:
        return await captcha_resp.content.read()


def save_captcha_image(captcha_img: bytes) -> None:
    with open(f'captcha_imgs/{uuid.uuid4()}.png', 'wb') as f:
        f.write(captcha_img)


async def get_captcha():
    async with request_semaphore:
        async with ClientSession(raise_for_status=True) as session:
            captcha_token = await get_captcha_token(session=session)
            captcha_img_cnt = await get_captcha_img(session=session, captcha_token=captcha_token)

        await asyncio.to_thread(save_captcha_image, captcha_img=captcha_img_cnt)


async def main():
    captcha_num = 200
    get_captcha_tasks = [get_captcha() for _ in range(captcha_num)]
    i = 0
    for get_captcha_future in asyncio.as_completed(get_captcha_tasks):
        i += 1
        print(f'{i}/{captcha_num}')
        await get_captcha_future


if __name__ == '__main__':
    print('------------- STARTED -------------')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    print('------------- FINISHED -------------')
