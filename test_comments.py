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
    
    # 搜索 AI
    success, msg, notes = spider.xhs_apis.search_some_note("AI", 1, cookies_str)
    print(f"Search Success: {success}, msg: {msg}")
    
    if success and notes:
        # 获取第一篇笔记
        note_info = notes[0]
        note_id = note_info.get('id', '')
        xsec_token = note_info.get('xsec_token', '')
        print(f"Note ID: {note_id}")
        url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}"
        print(f"Note URL: {url}")
        
        # 为了测试顺利，这里强制换一个固定的能用的note，因为上面的搜索可能会因为风控拿到空
        if not note_id:
            url = "https://www.xiaohongshu.com/explore/6917d9b4000000000703700f?xsec_token=AByQVvcCvIR6Y1cKu-TtGiaoYETO193NWU3pspk75v1Aw="
            print(f"Fallback Note URL: {url}")
        
        # 获取评论
        success_comment, msg_comment, comments_data = spider.xhs_apis.get_note_all_comment(url, cookies_str)
        print(f"Comment Success: {success_comment}")
        print(f"Comment Msg: {msg_comment}")
        
        if comments_data:
            print(f"Total top-level comments: {len(comments_data)}")
            total_sub_comments = sum(len(c.get('sub_comments', [])) for c in comments_data)
            print(f"Total sub-comments: {total_sub_comments}")
            print(f"Total comments: {len(comments_data) + total_sub_comments}")
            
            # 打印部分评论内容检查
            for i, comment in enumerate(comments_data[:3]):
                print(f"\nTop comment {i+1}: {comment.get('content', '')}")
                sub_comments = comment.get('sub_comments', [])
                print(f"  Sub-comments count: {len(sub_comments)}")
                for j, sub in enumerate(sub_comments[:2]):
                    print(f"    Sub {j+1}: {sub.get('content', '')}")
        else:
            print("No comments found.")

if __name__ == "__main__":
    asyncio.run(test())
