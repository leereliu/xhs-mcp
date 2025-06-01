from typing import Any, List, Dict, Optional
import asyncio
import json
import os
from datetime import datetime
from mcp.server.fastmcp import FastMCP, Context

import requests
from api.xhs_api import XhsApi
import logging
from urllib.parse import urlparse, parse_qs
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()

parser.add_argument("--type", type=str, default='stdio')
parser.add_argument("--port", type=int, default=11451)

args = parser.parse_args()

mcp = FastMCP("小红书", port=args.port)

xhs_cookie = os.getenv('XHS_COOKIE')

xhs_api = XhsApi(cookie=xhs_cookie)


def get_nodeid_token(url=None, note_ids=None):
    if note_ids is not None:
        note_id = note_ids[0,24]
        xsec_token = note_ids[24:]
        return {"note_id": note_id, "xsec_token": xsec_token}
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    note_id = parsed_url.path.split('/')[-1]
    xsec_token = None
    xsec_token_list = query_params.get('xsec_token', [None])
    if len(xsec_token_list) > 0:
        xsec_token = xsec_token_list[0]
    return {"note_id": note_id, "xsec_token": xsec_token}


@mcp.tool()
async def check_cookie() -> str:
    """检测cookie是否失效

    """
    try:
        data = await xhs_api.get_me()

        if 'success' in data and data['success'] == True:
            return "cookie有效"
        else:
            return "cookie已失效"
    except Exception as e:
        logger.error(e)
        return "cookie已失效"



@mcp.tool()
async def home_feed() -> str:
    """获取首页推荐笔记

    """
    data = await xhs_api.home_feed()
    result = "搜索结果：\n\n"
    if 'data' in data and 'items' in data['data'] and len(data['data']['items']) > 0:
        for i in range(0, len(data['data']['items'])):
            item = data['data']['items'][i]
            if 'note_card' in item and 'display_title' in item['note_card']:
                title = item['note_card']['display_title']
                liked_count = item['note_card']['interact_info']['liked_count']
                # cover=item['note_card']['cover']['url_default']
                url = f'https://www.xiaohongshu.com/explore/{item["id"]}?xsec_token={item["xsec_token"]}'
                result += f"{i}. {title}  \n 点赞数:{liked_count} \n   链接: {url}  \n\n"
    else:
        result = await check_cookie()
        if "有效" in result:
            result = f"未找到相关的笔记"
    return result

@mcp.tool()
async def search_notes(keywords: str) -> str:
    """根据关键词搜索笔记

        Args:
            keywords: 搜索关键词
    """

    data = await xhs_api.search_notes(keywords)
    logger.info(f'keywords:{keywords},data:{data}')
    result = "搜索结果：\n\n"
    if 'data' in data and 'items' in data['data'] and len(data['data']['items']) > 0:
        for i in range(0, len(data['data']['items'])):
            item = data['data']['items'][i]
            if 'note_card' in item and 'display_title' in item['note_card']:
                title = item['note_card']['display_title']
                liked_count = item['note_card']['interact_info']['liked_count']
                # cover=item['note_card']['cover']['url_default']
                url = f'https://www.xiaohongshu.com/explore/{item["id"]}?xsec_token={item["xsec_token"]}'
                result += f"{i}. {title}  \n 点赞数:{liked_count} \n   链接: {url}  \n\n"
    else:
        result = await check_cookie()
        if "有效" in result:
            result = f"未找到与\"{keywords}\"相关的笔记"
    return result


@mcp.tool()
async def get_note_content(url: str) -> str:
    """获取笔记内容,参数url要带上xsec_token

    Args:
        url: 笔记 url
    """
    params = get_nodeid_token(url=url)
    data = await xhs_api.get_note_content(**params)
    logger.info(f'url:{url},data:{data}')
    result = ""
    if 'data' in data and 'items' in data['data'] and len(data['data']['items']) > 0:
        for i in range(0, len(data['data']['items'])):
            item = data['data']['items'][i]

            if 'note_card' in item and 'user' in item['note_card']:
                note_card = item['note_card']
                cover = ''
                if 'image_list' in note_card and len(note_card['image_list']) > 0 and note_card['image_list'][0][
                    'url_pre']:
                    cover = note_card['image_list'][0]['url_pre']

                data_format = datetime.fromtimestamp(note_card.get('time', 0) / 1000)
                liked_count = item['note_card']['interact_info']['liked_count']
                comment_count = item['note_card']['interact_info']['comment_count']
                collected_count = item['note_card']['interact_info']['collected_count']

                url = f'https://www.xiaohongshu.com/explore/{params["note_id"]}?xsec_token={params["xsec_token"]}'
                result = f"标题: {note_card.get('title', '')}\n"
                result += f"作者: {note_card['user'].get('nickname', '')}\n"
                result += f"发布时间: {data_format}\n"
                result += f"点赞数: {liked_count}\n"
                result += f"评论数: {comment_count}\n"
                result += f"收藏数: {collected_count}\n"
                result += f"链接: {url}\n\n"
                result += f"内容:\n{note_card.get('desc', '')}\n"
                result += f"封面:\n{cover}"

            break
    else:
        result = await check_cookie()
        if "有效" in result:
            result = "获取失败"
    return result


@mcp.tool()
async def get_note_comments(url: str) -> str:
    """获取笔记的所有评论(包括一级和二级评论),参数url要带上xsec_token

    Args:
        url: 笔记 url
    """
    params = get_nodeid_token(url=url)
    
    # 使用新的全量评论接口
    data = await xhs_api.get_note_all_comment(params['note_id'], params['xsec_token'])
    logger.info(f'url:{url},data:{data}')

    result = ""
    if data.get('success', False) and len(data.get('data', [])) > 0:
        for i, comment in enumerate(data['data']):
            comment_time = datetime.fromtimestamp(comment['create_time'] / 1000)
            result += f"{i+1}. {comment['user_info']['nickname']}（{comment_time}）: {comment['content']}\n"
            
            # 如果有二级评论，也显示出来
            if 'sub_comments' in comment and len(comment['sub_comments']) > 0:
                for j, sub_comment in enumerate(comment['sub_comments']):
                    sub_comment_time = datetime.fromtimestamp(sub_comment['create_time'] / 1000)
                    result += f"    └─ {sub_comment['user_info']['nickname']}（{sub_comment_time}）: {sub_comment['content']}\n"
            result += "\n"
    else:
        result = await check_cookie()
        if "有效" in result:
            result = "暂无评论"

    return result


@mcp.tool()
async def post_comment(comment: str, note_id: str) -> str:
    """发布评论到指定笔记

    Args:
        note_id: 笔记 note_id
        comment: 要发布的评论内容
    """
    # params = get_nodeid_token(url)
    response = await xhs_api.post_comment(note_id, comment)
    if 'success' in response and response['success'] == True:
        return "回复成功"
    else:
        result = await check_cookie()
        if "有效" in result:
            return "回复失败"
        else:
            return result


@mcp.tool()
async def search_notes_with_contents(keywords: str, max_notes: int = 20) -> str:
    """根据关键词搜索笔记并批量获取内容和评论，返回压缩的JSON数据

    Args:
        keywords: 搜索关键词
        max_notes: 最大获取笔记数量，默认20
        
    Returns:
        包含搜索结果、笔记内容、评论数据等完整信息
    """
    try:
        # 1. 搜索笔记
        search_data = await xhs_api.search_notes(keywords)
        logger.info(f'搜索关键词: {keywords}, 最大获取数量: {max_notes}')
        
        if 'data' not in search_data or 'items' not in search_data['data'] or len(search_data['data']['items']) == 0:
            cookie_status = await check_cookie()
            if "有效" in cookie_status:
                return f"未找到与\"{keywords}\"相关的笔记"
            else:
                return cookie_status
        
        # 过滤有效的笔记，与search_notes保持一致的过滤逻辑
        valid_items = []
        for item in search_data['data']['items']:
            if 'note_card' in item and 'display_title' in item['note_card']:
                valid_items.append(item)
        
        if len(valid_items) == 0:
            return f"未找到与\"{keywords}\"相关的有效笔记"
        
        items = valid_items[:max_notes]  # 限制获取数量
        total_notes = len(items)
        
        # 2. 批量获取笔记内容和评论
        results = []
        failed_operations = []
        
        for i, item in enumerate(items):
            note_id = item['id']
            xsec_token = item['xsec_token']
            
            logger.info(f'正在处理第 {i+1}/{total_notes} 篇笔记: {note_id}')
            
            note_result = {
                "note_id": note_id,
                "xsec_token": xsec_token,
                "search_info": {
                    "title": item['note_card'].get('display_title', ''),
                    "liked_count": item['note_card']['interact_info'].get('liked_count', 0),
                    "url": f'https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}'
                },
                "content": None,
                "comments": None,
                "errors": []
            }
            
            # 获取笔记内容
            try:
                content_data = await xhs_api.get_note_content(note_id=note_id, xsec_token=xsec_token)

                logger.info(f'content_data:{content_data}')

                if 'data' in content_data and 'items' in content_data['data'] and len(content_data['data']['items']) > 0:
                    content_item = content_data['data']['items'][0]
                    if 'note_card' in content_item:
                        note_card = content_item['note_card']
                        cover = ''
                        if 'image_list' in note_card and len(note_card['image_list']) > 0:
                            cover = note_card['image_list'][0].get('url_pre', '')
                        
                        data_format = datetime.fromtimestamp(note_card.get('time', 0) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                        
                        note_result["content"] = {
                            "title": note_card.get('title', ''),
                            "author": note_card.get('user', {}).get('nickname', ''),
                            "publish_time": data_format,
                            "liked_count": content_item['note_card']['interact_info'].get('liked_count', 0),
                            "comment_count": content_item['note_card']['interact_info'].get('comment_count', 0),
                            "collected_count": content_item['note_card']['interact_info'].get('collected_count', 0),
                            "desc": note_card.get('desc', ''),
                            "cover": cover
                        }
                else:
                    note_result["errors"].append("获取笔记内容失败")
                    failed_operations.append(f"笔记内容获取失败: {note_id}")
            except Exception as e:
                logger.error(f"获取笔记内容失败 {note_id}: {e}")
                note_result["errors"].append(f"获取笔记内容异常: {str(e)}")
                failed_operations.append(f"笔记内容获取异常: {note_id} - {str(e)}")
            
            # 获取笔记评论（包括一级和二级评论）
            try:
                comments_data = await xhs_api.get_note_all_comment(note_id, xsec_token)

                logger.info(f'comments_data:{comments_data}')

                if comments_data.get('success', False) and len(comments_data.get('data', [])) > 0:
                    comments_list = []
                    for comment in comments_data['data']:
                        comment_time = datetime.fromtimestamp(comment['create_time'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                        
                        # 一级评论数据
                        comment_item = {
                            "comment_id": comment.get('id', ''),
                            "user": comment['user_info'].get('nickname', ''),
                            "user_id": comment['user_info'].get('user_id', ''),
                            "content": comment.get('content', ''),
                            "create_time": comment_time,
                            "like_count": comment.get('like_count', 0),
                            "sub_comments": []
                        }
                        
                        # 处理二级评论
                        if 'sub_comments' in comment and len(comment['sub_comments']) > 0:
                            for sub_comment in comment['sub_comments']:
                                sub_comment_time = datetime.fromtimestamp(sub_comment['create_time'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                                sub_comment_item = {
                                    "comment_id": sub_comment.get('id', ''),
                                    "user": sub_comment['user_info'].get('nickname', ''),
                                    "user_id": sub_comment['user_info'].get('user_id', ''),
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
            return f"数据获取完成但保存文件失败: {str(e)}"
        
        # 4. 提取指定字段并拼接成字符串返回给大模型
        all_relevant_text_parts = []
        # output_data["notes"] 即为之前构建的 results 列表
        for note_data in output_data.get("notes", []):
            # 提取笔记标题
            if note_data.get("content") and note_data["content"].get("title"):
                title = str(note_data["content"]["title"])
                all_relevant_text_parts.append(f"笔记标题：{title}")
            
            # 提取笔记正文
            if note_data.get("content") and note_data["content"].get("desc"):
                desc = str(note_data["content"]["desc"])
                all_relevant_text_parts.append(f"笔记正文：\\n{desc}") # Adding a newline for better readability of description
                
            # 提取评论和子评论内容
            if note_data.get("comments") and note_data["comments"].get("comments"):
                comments_section = ["\\n--- 评论区 ---"] # Add a separator for comments section
                has_comments = False
                for comment in note_data["comments"]["comments"]:
                    # 过滤掉点赞数为0的一级评论
                    comment_like_count = comment.get("like_count", 0)
                    # 处理like_count可能是字符串的情况
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
                            # 处理like_count可能是字符串的情况
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
            all_relevant_text_parts.append("\\n====================\\n") # Separator between notes
        
        final_text_blob = "\\n".join(all_relevant_text_parts)

        logger.info(f"final_text_blob:{final_text_blob}")

        return final_text_blob
        
    except Exception as e:
        logger.error(f"批量获取过程中发生错误: {e}")
        return f"批量获取失败: {str(e)}"


if __name__ == "__main__":
    logger.info("mcp run")
    mcp.run(transport=args.type)
