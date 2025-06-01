# 小红书 MCP 服务

[![smithery badge](https://smithery.ai/badge/@leereliu/xhs-mcp)](https://smithery.ai/server/@leereliu/xhs-mcp)

## 特点

- [x] 采用 js 逆向出 x-s,x-t,直接请求 http 接口,无须笨重的 playwright
- [x] 搜索笔记
- [x] 获取笔记内容
- [x] 获取笔记的评论
- [x] 发表评论

![特性](https://raw.githubusercontent.com/jobsonlook/xhs-mcp/master/docs/feature.png)

## 快速开始

### 1. 环境

- node
- python 3.12
- uv (pip install uv)

### 2. 安装依赖

```sh

git clone git@github.com:jobsonlook/xhs-mcp.git

cd xhs-mcp
uv sync

```

### 3. 获取小红书的 cookie

[打开 web 小红书](https://www.xiaohongshu.com/explore)
登录后，获取 cookie，将 cookie 配置到第 4 步的 XHS_COOKIE 环境变量中
![cookie](https://raw.githubusercontent.com/jobsonlook/xhs-mcp/master/docs/cookie.png)

### 4. 配置 mcp server

```json
{
  "mcpServers": {
    "xhs-mcp": {
      "command": "uv",
      "args": ["--directory", "/Users/xxx/xhs-mcp", "run", "main.py"],
      "env": {
        "XHS_COOKIE": "xxxx"
      }
    }
  }
}
```

## 免责声明

本项目仅用于学习交流，禁止用于其他用途，任何涉及商业盈利目的均不得使用，否则风险自负。
