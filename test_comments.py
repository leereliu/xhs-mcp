import asyncio
import os
import sys

# 添加 spider 目录到 sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import get_browser_cookie, init
from spider.main import Data_Spider

async def test():
    browser_cookie = get_browser_cookie()
    env_cookie, base_path = init()
    cookies_str = browser_cookie if browser_cookie else env_cookie
    
    spider = Data_Spider()
    url = "https://www.xiaohongshu.com/explore/6917d9b4000000000703700f?xsec_token=AByQVvcCvIR6Y1cKu-TtGiaoYETO193NWU3pspk75v1Aw="
    success, msg, data = spider.xhs_apis.get_note_all_comment(url, cookies_str)
    
    print(f"Success: {success}")
    print(f"Msg: {msg}")
    print(f"Data length: {len(data) if data else 0}")
    if data:
        print(data[0])

if __name__ == "__main__":
    asyncio.run(test())
