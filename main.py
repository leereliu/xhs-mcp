import json
import os
import argparse
from datetime import datetime
from loguru import logger
from mcp.server.fastmcp import FastMCP

import sys

# 切换工作目录到 spider 目录下，因为 spider 项目里面的文件读取都是用的相对路径（比如 '../static/' 等）
current_dir = os.path.dirname(os.path.abspath(__file__))
spider_dir = os.path.join(current_dir, 'spider')

# 为了能让 spider 内部的代码找到相对模块，我们切换进去
os.chdir(spider_dir)
sys.path.append(spider_dir)

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# 强制让 requests 忽略 SSL
old_request = requests.Session.request
def new_request(*args, **kwargs):
    kwargs['verify'] = False
    return old_request(*args, **kwargs)
requests.Session.request = new_request

from spider.main import Data_Spider
from spider.xhs_utils.common_util import init
import spider.apis.xhs_pc_apis as spider_api

# 强制替换 spider 内部所有的 get / post 方法来规避 SSL
old_get = spider_api.requests.get
def new_get(*args, **kwargs):
    kwargs["verify"] = False
    return old_get(*args, **kwargs)
spider_api.requests.get = new_get

old_post = spider_api.requests.post
def new_post(*args, **kwargs):
    kwargs["verify"] = False
    return old_post(*args, **kwargs)
spider_api.requests.post = new_post

# 配置参数
parser = argparse.ArgumentParser()
parser.add_argument("--type", type=str, default='stdio')
parser.add_argument("--port", type=int, default=11451)
args = parser.parse_args()

# 初始化 MCP
mcp = FastMCP("小红书", port=args.port)

def get_browser_cookie():
    try:
        import browser_cookie3
        cookie_str = None
        # 1. 尝试 Edge
        try:
            cj = browser_cookie3.edge(domain_name='.xiaohongshu.com')
            cookie_dict = {cookie.name: cookie.value for cookie in cj}
            if cookie_dict:
                cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
                logger.info("成功从 Edge 浏览器提取小红书 Cookie")
                return cookie_str
        except Exception as e:
            logger.debug(f"尝试从 Edge 获取 Cookie 失败: {e}")
            
        # 2. 尝试 Chrome
        try:
            cj = browser_cookie3.chrome(domain_name='.xiaohongshu.com')
            cookie_dict = {cookie.name: cookie.value for cookie in cj}
            if cookie_dict:
                cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
                logger.info("成功从 Chrome 浏览器提取小红书 Cookie")
                return cookie_str
        except Exception as e:
            logger.debug(f"尝试从 Chrome 获取 Cookie 失败: {e}")
            
    except ImportError:
        logger.warning("未安装 browser-cookie3，将降级使用 .env 中的 cookie")
    except Exception as e:
        logger.warning(f"获取浏览器 Cookie 失败: {e}")
    return None

# 初始化爬虫对象
# 优先从 Edge 获取，如果失败则回退到 Chrome，如果再次失败则从 spider/.env 获取
browser_cookie = get_browser_cookie()
env_cookie, base_path = init()
cookies_str = browser_cookie if browser_cookie else env_cookie

if not cookies_str:
    logger.error("未找到有效的 Cookie (Edge/Chrome/env 均未找到)，程序无法继续！")
    raise ValueError("Missing Xiaohongshu Cookie. Please login in Edge/Chrome or provide it in spider/.env")

data_spider = Data_Spider()

# 还原工作路径（如果有必要的话）
# os.chdir(current_dir) 
# 由于数据可能保存在 temp 文件夹，我们最好就在 spider 目录下执行，这样 spider 的文件导出也不会报错。

@mcp.tool()
async def search_notes_with_contents(keywords: str, max_notes: int = 20) -> str:
    """根据关键词搜索笔记并批量获取内容和评论，返回压缩的JSON数据。
    注意：为了精简数据给大模型使用，目前策略会自动过滤掉点赞数为 0 的一级和二级评论。

    Args:
        keywords: 搜索关键词
        max_notes: 最大获取笔记数量，默认20
        
    Returns:
        包含搜索结果、笔记内容、评论数据等完整信息
    """
    try:
        logger.info(f'搜索关键词: {keywords}, 最大获取数量: {max_notes}')
        
        # 1. 搜索笔记
        # sort_type_choice: 0 综合排序
        # note_type: 0 不限
        # note_time: 0 不限
        # note_range: 0 不限
        # pos_distance: 0 不限
        success, msg, search_data = data_spider.xhs_apis.search_some_note(
            keywords, max_notes, cookies_str, 0, 0, 0, 0, 0, None, None
        )
        
        if not success:
            return f"搜索失败: {msg}"
            
        if not search_data:
            return f"未找到与\"{keywords}\"相关的笔记"
            
        # 过滤出笔记类型的
        notes = list(filter(lambda x: x.get('model_type') == "note", search_data))
        if not notes:
            return f"未找到与\"{keywords}\"相关的有效笔记"
            
        items = notes[:max_notes]  # 限制获取数量
        total_notes = len(items)
        
        # 2. 批量获取笔记内容和评论
        results = []
        failed_operations = []
        
        for i, item in enumerate(items):
            note_id = item['id']
            xsec_token = item.get('xsec_token', '')
            note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}"
            
            logger.info(f'正在处理第 {i+1}/{total_notes} 篇笔记: {note_id}')
            
            note_result = {
                "note_id": note_id,
                "xsec_token": xsec_token,
                "search_info": {
                    "title": item.get('display_title', ''),
                    "liked_count": 0, # search API return structure might differ slightly
                    "url": note_url
                },
                "content": None,
                "comments": None,
                "errors": []
            }
            
            # 获取笔记内容
            try:
                # 获取原汁原味的详情 API，或者把 success_detail, msg_detail, content_data 打印出来
                success_detail, msg_detail, content_data = data_spider.xhs_apis.get_note_info(note_url, cookies_str)
                logger.info(f"content_data: {type(content_data)}")
                if success_detail and content_data:
                    # spider_note 返回的数据结构
                    if isinstance(content_data, dict) and 'data' in content_data and 'items' in content_data['data'] and len(content_data['data']['items']) > 0:
                        content_item = content_data['data']['items'][0]
                        note_card = content_item.get('note_card', {})
                        
                        cover = ''
                        if 'image_list' in note_card and len(note_card['image_list']) > 0:
                            cover = note_card['image_list'][0].get('url_pre', '')
                        
                        data_format = datetime.fromtimestamp(note_card.get('time', 0) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                        
                        note_result["content"] = {
                            "title": note_card.get('title', ''),
                            "author": note_card.get('user', {}).get('nickname', ''),
                            "publish_time": data_format,
                            "liked_count": note_card.get('interact_info', {}).get('liked_count', 0),
                            "comment_count": note_card.get('interact_info', {}).get('comment_count', 0),
                            "collected_count": note_card.get('interact_info', {}).get('collected_count', 0),
                            "desc": note_card.get('desc', ''),
                            "cover": cover
                        }
                    else:
                        note_result["errors"].append("获取笔记内容失败(数据格式非dict)")
                        failed_operations.append(f"笔记内容获取失败(格式错误): {note_id}")
                else:
                    note_result["errors"].append(f"获取笔记内容失败: {msg_detail}")
                    failed_operations.append(f"笔记内容获取失败: {note_id}")
            except Exception as e:
                logger.error(f"获取笔记内容失败 {note_id}: {e}")
                note_result["errors"].append(f"获取笔记内容异常: {str(e)}")
                failed_operations.append(f"笔记内容获取异常: {note_id} - {str(e)}")
            
            # 获取笔记评论（包括一级和二级评论）
            try:
                success_comment, msg_comment, comments_data = data_spider.xhs_apis.get_note_all_comment(note_url, cookies_str)
                
                if success_comment and comments_data:
                    comments_list = []
                    for comment in comments_data:
                        # 兼容处理时间格式，可能是毫秒级时间戳，也可能已经是格式化字符串
                        create_time = comment.get('create_time', 0)
                        if isinstance(create_time, (int, float)):
                            comment_time = datetime.fromtimestamp(create_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            comment_time = str(create_time)
                            
                        # 一级评论数据
                        comment_item = {
                            "comment_id": comment.get('id', ''),
                            "user": comment.get('user_info', {}).get('nickname', ''),
                            "user_id": comment.get('user_info', {}).get('user_id', ''),
                            "content": comment.get('content', ''),
                            "create_time": comment_time,
                            "like_count": comment.get('like_count', 0),
                            "sub_comments": []
                        }
                        
                        # 处理二级评论
                        if 'sub_comments' in comment and len(comment['sub_comments']) > 0:
                            for sub_comment in comment['sub_comments']:
                                sub_create_time = sub_comment.get('create_time', 0)
                                if isinstance(sub_create_time, (int, float)):
                                    sub_comment_time = datetime.fromtimestamp(sub_create_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                                else:
                                    sub_comment_time = str(sub_create_time)
                                    
                                sub_comment_item = {
                                    "comment_id": sub_comment.get('id', ''),
                                    "user": sub_comment.get('user_info', {}).get('nickname', ''),
                                    "user_id": sub_comment.get('user_info', {}).get('user_id', ''),
                                    "content": sub_comment.get('content', ''),
                                    "create_time": sub_comment_time,
                                    "like_count": sub_comment.get('like_count', 0),
                                    "target_user": sub_comment.get('target_comment', {}).get('user_info', {}).get('nickname', '') if sub_comment.get('target_comment') else ''
                                }
                                comment_item["sub_comments"].append(sub_comment_item)
                        
                        comments_list.append(comment_item)
                    
                    note_result["comments"] = {
                        "total_count": len(comments_list),
                        "total_sub_comments": sum(len(c["sub_comments"]) for c in comments_list),
                        "comments": comments_list
                    }
                else:
                    note_result["comments"] = {
                        "total_count": 0,
                        "total_sub_comments": 0,
                        "comments": []
                    }
            except Exception as e:
                logger.error(f"获取笔记评论失败 {note_id}: {e}")
                note_result["errors"].append(f"获取笔记评论异常: {str(e)}")
                failed_operations.append(f"笔记评论获取异常: {note_id} - {str(e)}")
                note_result["comments"] = {
                    "total_count": 0,
                    "total_sub_comments": 0,
                    "comments": []
                }
            
            results.append(note_result)
        
        # 3. 保存数据到JSON文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"temp/xhs_data_{keywords}_{timestamp}.json"
        
        # 确保temp目录存在
        os.makedirs("temp", exist_ok=True)
        
        successful_notes = [r for r in results if not r["errors"]]
        total_comments = sum(r.get("comments", {}).get("total_count", 0) for r in successful_notes)
        total_sub_comments = sum(r.get("comments", {}).get("total_sub_comments", 0) for r in successful_notes)
        
        output_data = {
            "search_keywords": keywords,
            "search_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_notes": total_notes,
            "successful_notes": len(successful_notes),
            "total_comments": total_comments,
            "total_sub_comments": total_sub_comments,
            "failed_operations": failed_operations,
            "notes": results
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            logger.info(f"数据已保存到文件: {filename}")
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            # 即使保存失败也继续返回文本给大模型
            
        # 4. 提取指定字段并拼接成字符串返回给大模型
        all_relevant_text_parts = []
        for note_data in output_data.get("notes", []):
            # 提取笔记标题
            if note_data.get("content") and note_data["content"].get("title"):
                title = str(note_data["content"]["title"])
                all_relevant_text_parts.append(f"笔记标题：{title}")
            
            # 提取笔记正文
            if note_data.get("content") and note_data["content"].get("desc"):
                desc = str(note_data["content"]["desc"])
                all_relevant_text_parts.append(f"笔记正文：\n{desc}")
                
            # 提取评论和子评论内容
            if note_data.get("comments") and note_data["comments"].get("comments"):
                comments_section = ["\n--- 评论区 ---"]
                has_comments = False
                for comment in note_data["comments"]["comments"]:
                    # 过滤掉点赞数为0的一级评论
                    comment_like_count = comment.get("like_count", 0)
                    if isinstance(comment_like_count, str):
                        try:
                            comment_like_count = int(comment_like_count)
                        except ValueError:
                            comment_like_count = 0
                    
                    if comment.get("content") and comment_like_count > 0:
                        comment_content = str(comment["content"])
                        comments_section.append(f"评论：{comment_content}")
                        has_comments = True
                    
                    # 处理子评论，同样过滤掉点赞数为0的
                    if comment.get("sub_comments"):
                        for sub_comment in comment["sub_comments"]:
                            sub_comment_like_count = sub_comment.get("like_count", 0)
                            if isinstance(sub_comment_like_count, str):
                                try:
                                    sub_comment_like_count = int(sub_comment_like_count)
                                except ValueError:
                                    sub_comment_like_count = 0
                            
                            if sub_comment.get("content") and sub_comment_like_count > 0:
                                sub_comment_content = str(sub_comment["content"])
                                comments_section.append(f"  回复：{sub_comment_content}")
                                has_comments = True
                if has_comments:
                    all_relevant_text_parts.extend(comments_section)
            all_relevant_text_parts.append("\n====================\n")
        
        final_text_blob = "\n".join(all_relevant_text_parts)

        logger.info(f"成功获取并解析数据")

        return final_text_blob
        
    except Exception as e:
        logger.error(f"批量获取过程中发生错误: {e}")
        return f"批量获取失败: {str(e)}"

if __name__ == "__main__":
    logger.info("mcp run")
    mcp.run(transport=args.type)