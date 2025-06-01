import asyncio
import json
import time
import math
import random
import execjs
import os
from collections.abc import Mapping
from urllib.parse import urlencode, urlparse, quote
import requests
from curl_cffi.requests import AsyncSession, Response

from typing import Dict
from numbers import Integral
from typing import Iterable, List, Optional, Tuple
import base64
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class XhsApi:
    def __init__(self, cookie):
        self._cookie = cookie
        self._base_url = "https://edith.xiaohongshu.com"
        self._init_js_engines()

    def _init_js_engines(self):
        """初始化JS引擎"""
        current_directory = os.path.dirname(__file__)
        
        # 初始化主要的JS引擎
        try:
            js_file_path = os.path.join(current_directory, "xhs_xs_xsc_56.js")
            self.js = execjs.compile(open(js_file_path, 'r', encoding='utf-8').read())
        except Exception as e:
            logger.error(f"Failed to load xhs_xs_xsc_56.js: {e}")
            raise
        
        # 初始化xray JS引擎
        try:
            xray_file_path = os.path.join(current_directory, "xhs_xray.js")
            self.xray_js = execjs.compile(open(xray_file_path, 'r', encoding='utf-8').read())
        except Exception as e:
            logger.error(f"Failed to load xhs_xray.js: {e}")
            raise

    def trans_cookies(self, cookies_str: str) -> Dict:
        """转换cookie字符串为字典"""
        cookie_dict = {}
        if cookies_str:
            pairs = cookies_str.split(';')
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.strip().split('=', 1)
                    cookie_dict[key] = value
        return cookie_dict

    def generate_x_b3_traceid(self, length=16):
        """生成x-b3-traceid"""
        x_b3_traceid = ""
        for t in range(length):
            x_b3_traceid += "abcdef0123456789"[math.floor(16 * random.random())]
        return x_b3_traceid

    def generate_xray_traceid(self):
        """生成xray traceid"""
        return self.xray_js.call('traceId')

    def generate_xs_xs_common(self, a1, api, data=''):
        """生成xs和xs_common"""
        ret = self.js.call('get_request_headers_params', api, data, a1)
        xs, xt, xs_common = ret['xs'], ret['xt'], ret['xs_common']
        return xs, xt, xs_common

    def get_request_headers_template(self):
        """获取请求头模板"""
        return {
            "authority": "edith.xiaohongshu.com",
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "cache-control": "no-cache",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.xiaohongshu.com",
            "pragma": "no-cache",
            "referer": "https://www.xiaohongshu.com/",
            "sec-ch-ua": "\"Not A(Brand\";v=\"99\", \"Microsoft Edge\";v=\"121\", \"Chromium\";v=\"121\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
            "x-b3-traceid": "",
            "x-s": "",
            "x-s-common": "",
            "x-t": "",
            "x-xray-traceid": self.generate_xray_traceid()
        }

    def generate_headers(self, a1, api, data=''):
        """生成完整的请求头"""
        xs, xt, xs_common = self.generate_xs_xs_common(a1, api, data)
        x_b3_traceid = self.generate_x_b3_traceid()
        headers = self.get_request_headers_template()
        headers['x-s'] = xs
        headers['x-t'] = str(xt)
        headers['x-s-common'] = xs_common
        headers['x-b3-traceid'] = x_b3_traceid
        if data:
            data = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return headers, data

    def generate_request_params(self, api, data=''):
        """生成请求参数"""
        cookies = self.trans_cookies(self._cookie)
        a1 = cookies.get('a1', '')
        if not a1:
            raise ValueError("Cookie中缺少a1参数")
        headers, processed_data = self.generate_headers(a1, api, data)
        return headers, cookies, processed_data

    def splice_str(self, api, params):
        """拼接URL参数"""
        url = api + '?'
        for key, value in params.items():
            if value is None:
                value = ''
            url += key + '=' + str(value) + '&'
        return url[:-1]

    def init_session(self):
        return AsyncSession(
            verify=True,
            impersonate="chrome124",
            timeout=30,
            max_redirects=5
        )

    def base36encode(self, number: Integral, alphabet: Iterable[str] = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') -> str:
        """Base36编码"""
        base36 = ''
        alphabet = ''.join(alphabet)
        sign = '-' if number < 0 else ''
        number = abs(number)

        while number:
            number, i = divmod(number, len(alphabet))
            base36 = alphabet[i] + base36

        return sign + (base36 or alphabet[0])

    def search_id(self):
        """生成搜索ID"""
        e = int(time.time() * 1000) << 64
        t = int(random.uniform(0, 2147483646))
        return self.base36encode((e + t))

    async def request(self, uri: str, session=None, method="GET", headers=None, params=None, data=None) -> Dict:
        """发送请求"""
        if session is None:
            session = self.init_session()
        
        # 如果没有提供headers，生成标准headers
        if headers is None:
            try:
                headers, cookies, processed_data = self.generate_request_params(uri, data)
                # 如果有data，使用处理后的data
                if data is not None:
                    data = processed_data
            except Exception as e:
                logger.error(f"生成请求参数失败: {e}")
                headers = self.get_request_headers_template()
                cookies = self.trans_cookies(self._cookie)
        else:
            cookies = self.trans_cookies(self._cookie)

        try:
            response: Response = await session.request(
                method=method,
                url=f"{self._base_url}{uri}",
                params=params,
                data=data.encode('utf-8') if isinstance(data, str) else data,
                json=data if method == "POST" and not isinstance(data, str) else None,
                cookies=cookies,
                headers=headers,
                timeout=30
            )

            # 修复stream mode错误，使用response.content而不是response.acontent()
            try:
                content = response.content
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}, 响应内容: {content[:500]}...")
                return {"success": False, "msg": f"JSON解析失败: {str(e)}"}
            except Exception as e:
                logger.error(f"获取响应内容失败: {e}")
                # 尝试使用text属性
                try:
                    content = response.text
                    return json.loads(content)
                except Exception as e2:
                    logger.error(f"使用text属性也失败: {e2}")
                    return {"success": False, "msg": f"获取响应内容失败: {str(e)}"}
                    
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return {"success": False, "msg": str(e)}

    async def get_me(self) -> Dict:
        """获取用户自己的信息"""
        uri = '/api/sns/web/v2/user/me'
        return await self.request(uri, method="GET")

    async def search_notes(self, keywords: str, limit: int = 20, sort: str = "general", note_type: int = 0) -> Dict:
        """搜索笔记"""
        data = {
            "keyword": keywords,
            "page": 1,
            "page_size": limit,
            "search_id": self.search_id(),
            "sort": sort,
            "note_type": note_type,
            "ext_flags": [],
            "image_formats": ["jpg", "webp", "avif"]
        }
        return await self.request("/api/sns/web/v1/search/notes", method="POST", data=data)

    async def home_feed(self, category: str = "homefeed_recommend", cursor_score: str = "", 
                       refresh_type: int = 1, note_index: int = 0) -> Dict:
        """获取主页推荐"""
        data = {
            "category": category,
            "cursor_score": cursor_score,
            "image_formats": ["jpg", "webp", "avif"],
            "need_filter_image": False,
            "need_num": 8,
            "num": 18,
            "note_index": note_index,
            "refresh_type": refresh_type,
            "search_key": "",
            "unread_begin_note_id": "",
            "unread_end_note_id": "",
            "unread_note_count": 0
        }
        return await self.request("/api/sns/web/v1/homefeed", method="POST", data=data)

    async def get_note_content(self, note_id: str, xsec_token: str = "", xsec_source: str = "pc_feed") -> Dict:
        """获取笔记内容"""
        data = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": "1"},
            "xsec_source": xsec_source,
            "xsec_token": xsec_token
        }
        return await self.request("/api/sns/web/v1/feed", method="POST", data=data)

    async def get_note_info(self, url: str) -> Dict:
        """通过URL获取笔记详细信息"""
        try:
            urlParse = urlparse(url)
            note_id = urlParse.path.split("/")[-1]
            kvs = urlParse.query.split('&') if urlParse.query else []
            kvDist = {}
            for kv in kvs:
                if '=' in kv:
                    key, value = kv.split('=', 1)
                    kvDist[key] = value
            
            xsec_source = kvDist.get('xsec_source', 'pc_search')
            xsec_token = kvDist.get('xsec_token', '')
            
            return await self.get_note_content(note_id, xsec_token, xsec_source)
        except Exception as e:
            return {"success": False, "msg": str(e)}

    async def get_user_info(self, user_id: str) -> Dict:
        """获取用户信息"""
        params = {"target_user_id": user_id}
        uri = "/api/sns/web/v1/user/otherinfo"
        splice_uri = self.splice_str(uri, params)
        return await self.request(splice_uri, method="GET")

    async def get_user_notes(self, user_id: str, cursor: str = "", xsec_token: str = "", 
                           xsec_source: str = "pc_search") -> Dict:
        """获取用户笔记"""
        params = {
            "num": "30",
            "cursor": cursor,
            "user_id": user_id,
            "image_formats": "jpg,webp,avif",
            "xsec_token": xsec_token,
            "xsec_source": xsec_source,
        }
        uri = "/api/sns/web/v1/user_posted"
        splice_uri = self.splice_str(uri, params)
        return await self.request(splice_uri, method="GET")

    async def get_user_all_notes(self, user_url: str) -> Dict:
        """获取用户所有笔记"""
        try:
            urlParse = urlparse(user_url)
            user_id = urlParse.path.split("/")[-1]
            kvs = urlParse.query.split('&') if urlParse.query else []
            kvDist = {}
            for kv in kvs:
                if '=' in kv:
                    key, value = kv.split('=', 1)
                    kvDist[key] = value
            
            xsec_token = kvDist.get('xsec_token', '')
            xsec_source = kvDist.get('xsec_source', 'pc_search')
            
            cursor = ''
            note_list = []
            
            while True:
                res_json = await self.get_user_notes(user_id, cursor, xsec_token, xsec_source)
                
                if not res_json.get("success", False):
                    break
                
                notes = res_json.get("data", {}).get("notes", [])
                if not notes:
                    break
                    
                note_list.extend(notes)
                
                data = res_json.get("data", {})
                if 'cursor' in data:
                    cursor = str(data["cursor"])
                else:
                    break
                    
                if not data.get("has_more", False):
                    break
            
            return {"success": True, "msg": "success", "data": note_list}
        except Exception as e:
            return {"success": False, "msg": str(e), "data": []}

    async def get_note_out_comment(self, note_id: str, cursor: str, xsec_token: str) -> Dict:
        """获取指定位置的笔记一级评论"""
        params = {
            'note_id': note_id,
            'cursor': cursor,
            'top_comment_id': '',
            'image_formats': 'jpg,webp,avif',
            'xsec_token': xsec_token
        }
        uri = '/api/sns/web/v2/comment/page'
        splice_uri = self.splice_str(uri, params)
        logger.info(f"获取笔记一级评论: note_id:{note_id}, cursor:{cursor}")
        return await self.request(splice_uri, method="GET")

    async def get_note_all_out_comment(self, note_id: str, xsec_token: str) -> Dict:
        """获取笔记的全部一级评论"""
        cursor = ''
        note_out_comment_list = []
        
        try:
            while True:
                res_json = await self.get_note_out_comment(note_id, cursor, xsec_token)
                
                if not res_json.get('success', False):
                    break

                data = res_json.get('data', {})
                comments = data.get('comments', [])
                
                if not comments:
                    break

                note_out_comment_list.extend(comments)
                
                if 'cursor' in data:
                    cursor = str(data["cursor"])
                else:
                    break

                if not data.get("has_more", False):
                    break

            return {"success": True, "msg": "success", "data": note_out_comment_list}
        except Exception as e:
            return {"success": False, "msg": str(e), "data": []}

    async def get_note_inner_comment(self, comment: dict, cursor: str, xsec_token: str) -> Dict:
        """获取指定位置的笔记二级评论"""
        params = {
            'note_id': comment['note_id'],
            'root_comment_id': comment['id'],
            'num': '10',
            'cursor': cursor,
            'image_formats': 'jpg,webp,avif',
            'top_comment_id': '',
            'xsec_token': xsec_token
        }
        uri = '/api/sns/web/v2/comment/sub/page'
        splice_uri = self.splice_str(uri, params)
        logger.info(f"获取笔记二级评论: note_id:{comment['note_id']}, root_comment_id:{comment['id']}, cursor:{cursor}")
        return await self.request(splice_uri, method="GET")

    async def get_note_all_inner_comment(self, comment: dict, xsec_token: str) -> Dict:
        """获取笔记的全部二级评论"""
        try:
            if not comment.get('sub_comment_has_more', False):
                return {"success": True, "msg": 'success', "data": comment}

            cursor = comment.get('sub_comment_cursor', '')
            inner_comment_list = []

            while True:
                res_json = await self.get_note_inner_comment(comment, cursor, xsec_token)

                if not res_json.get('success', False):
                    break

                data = res_json.get('data', {})
                comments = data.get('comments', [])
                
                if not comments:
                    break

                inner_comment_list.extend(comments)
                
                if 'cursor' in data:
                    cursor = str(data["cursor"])
                else:
                    break

                if not data.get("has_more", False):
                    break

            # 将获取到的二级评论添加到原comment对象中
            if 'sub_comments' not in comment:
                comment['sub_comments'] = []
            comment['sub_comments'].extend(inner_comment_list)

            return {"success": True, "msg": "success", "data": comment}
        except Exception as e:
            return {"success": False, "msg": str(e), "data": comment}

    async def get_note_all_comment(self, note_id: str, xsec_token: str) -> Dict:
        """获取一篇文章的所有评论（包括一级评论和二级评论）"""
        try:
            # 获取所有一级评论
            out_comment_result = await self.get_note_all_out_comment(note_id, xsec_token)

            if not out_comment_result.get('success', False):
                return out_comment_result

            out_comment_list = out_comment_result.get('data', [])

            # 并行为每个一级评论获取所有二级评论
            if out_comment_list:
                # 创建所有二级评论请求的任务列表
                inner_comment_tasks = [
                    self.get_note_all_inner_comment(comment, xsec_token) 
                    for comment in out_comment_list
                ]
                
                # 并行执行所有二级评论请求
                inner_comment_results = await asyncio.gather(*inner_comment_tasks, return_exceptions=True)
                
                # 处理结果，记录失败的请求
                for i, result in enumerate(inner_comment_results):
                    if isinstance(result, Exception):
                        logger.warning(f"获取第{i}个一级评论的二级评论时发生异常: {str(result)}")
                    elif not result.get('success', False):
                        logger.warning(f"获取第{i}个一级评论的二级评论失败: {result.get('msg', '')}")

            return {"success": True, "msg": 'success', "data": out_comment_list}

        except Exception as e:
            return {"success": False, "msg": str(e), "data": []}

    async def post_comment(self, note_id: str, comment: str) -> Dict:
        """发表评论"""
        data = {
            "note_id": note_id,
            "content": comment,
            "at_users": []
        }
        return await self.request('/api/sns/web/v1/comment/post', method="POST", data=data)

    async def search_users(self, query: str, page: int = 1) -> Dict:
        """搜索用户"""
        data = {
            "search_user_request": {
                "keyword": query,
                "search_id": self.generate_x_b3_traceid(21),
                "page": page,
                "page_size": 15,
                "biz_type": "web_search_user",
                "request_id": str(int(time.time() * 1000))
            }
        }
        return await self.request("/api/sns/web/v1/search/usersearch", method="POST", data=data)

    async def get_search_keyword(self, word: str) -> Dict:
        """获取搜索关键词推荐"""
        params = {"keyword": quote(word)}
        uri = "/api/sns/web/v1/search/recommend"
        splice_uri = self.splice_str(uri, params)
        return await self.request(splice_uri, method="GET")
