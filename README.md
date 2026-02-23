# XHS MCP Server

基于 [Spider_XHS](https://github.com/cv-cat/Spider_XHS) 封装的小红书 MCP Server。
可以直接供 Cursor/Cline 等 AI Agent 使用，搜索小红书笔记和评论并返回整理好的数据供大语言模型消费。

## 快速开始

1. 初始化 Python 环境并安装依赖：
```bash
uv sync # 或者 pip install -r requirements.txt
```

2. 登录小红书并获取 cookie：
需要在 `spider/.env` 文件中填入正确的小红书登录 cookie。格式如下：
```env
cookie="你的cookie"
```

3. 运行 MCP Server：
```bash
# stdio 模式（供 Cursor 等调用）
python main.py --type stdio

# SSE 模式（供调试）
python main.py --type sse --port 11451
```

## 功能支持

- `search_notes_with_contents`: 搜索指定关键词的笔记并批量获取内容和一二级评论（为精简返回给大模型的内容体积，点赞数为 0 的评论会被自动过滤掉）。

## 如何添加到 Cursor

1. 打开 Cursor 的设置（Settings）。
2. 在左侧菜单中找到 **Features** -> **MCP** (Model Context Protocol)。
3. 点击 **+ Add New MCP Server**。
4. 填写配置信息：
   - **Name**: `xhs-mcp` (或任意你喜欢的名称)
   - **Type**: `command`
   - **Command**: `uv run main.py --type stdio` (如果你使用的是 python 的 venv，可以填写绝对路径指向你的 `.venv/bin/python main.py --type stdio`)
5. 设置工作目录 (Working Directory) 为本项目所在的绝对路径。
6. 点击 Save 即可。
7. 测试调用：在对话中对 Cursor 提到“请用小红书MCP搜索关于某某的内容”即可。