# Nola × Onely DeepSeek 问答机器人 MVP

一个可本地运行的 AI 问答机器人 Demo。Nola 使用 DeepSeek 完成多轮中文对话、情绪理解和需求提取，并结合 Onely 官网公开资料回答产品问题、推荐 Starter / Standard / Pro / Agency 套餐。

> 本项目仅用于 MVP 演示。套餐、价格和 Credits 为 2026-09-02 从 Onely 公开页面整理的静态快照，不代表 Onely 官方销售承诺。

## 功能

- DeepSeek 驱动的自然多轮问答
- 压力、迷茫、平静、兴奋等简单情绪理解
- 四档套餐推荐与商品卡片
- SQLite 匿名会话和聊天记录持久化
- 刷新恢复会话、重新开始
- DeepSeek 异常时关键词规则兜底
- API Key 仅从本地 `.env` 读取，不进入浏览器或 Git

## 技术架构

```text
React 19 / Vinext 前端
        │ HTTP JSON
        ▼
FastAPI ── DeepSeek Chat Completions API
        │
        └── SQLite（套餐、匿名会话、消息）
```

## 环境要求

- Node.js >= 22.13
- pnpm >= 10
- Python >= 3.11
- 一个可用且有余额的 DeepSeek API Key

## 1. 获取代码

```bash
git clone https://github.com/tianjinyi/nola-onely-chatbot-mvp.git
cd nola-onely-chatbot-mvp
```

## 2. 配置大模型厂商与 API

本项目接入了支持 Chat Completions 的 LLM API，**唯一需要你自己填写的是根目录 `.env` 文件中的三个变量**：

```dotenv
DEEPSEEK_API_KEY=你的模型服务商 API Key
DEEPSEEK_BASE_URL=模型服务商的接口地址
DEEPSEEK_MODEL=要使用的模型名称
```

首次运行先把模板复制为 `.env`：

Linux / macOS：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

然后编辑根目录的 `.env`，把 `DEEPSEEK_API_KEY` 替换成你自己的 Key。

### 2.1 使用 DeepSeek（默认示例）

如果你用 DeepSeek 官方服务，在 DeepSeek 开放平台创建 API Key 后，这样填写：

```dotenv
# 在这里填你自己申请的 Key；不要把真实 Key 提交到 Git
DEEPSEEK_API_KEY=sk-你的DeepSeek_API_Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

DeepSeek 官方文档：<https://api-docs.deepseek.com/>

> 注意：后端代码默认按上面这套变量读取模型厂商和 Key。`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` 都来自根目录 `.env`，请勿把它们写进源码或提交到 Git。

### 2.2 换成其他大模型厂商

本项目使用 OpenAI 兼容的 Chat Completions 接口。想换厂商时，只需把 `.env` 中的三个变量改成对应值即可：

```dotenv
DEEPSEEK_API_KEY=你的API_Key
DEEPSEEK_BASE_URL=服务商提供的接口地址（OpenAI兼容）
DEEPSEEK_MODEL=服务商提供的模型名称
```

常见示例：

```dotenv
# OpenAI
DEEPSEEK_API_KEY=sk-你的OpenAI_Key
DEEPSEEK_BASE_URL=https://api.openai.com/v1
DEEPSEEK_MODEL=gpt-4o-mini
```

```dotenv
# 其他任何 OpenAI 兼容厂商，例如智谱/月之暗面/通义等
DEEPSEEK_API_KEY=你的API_Key
DEEPSEEK_BASE_URL=https://服务商提供的兼容地址/v1
DEEPSEEK_MODEL=服务商提供的模型名
```

### 2.3 修改后的验证

1. 保存 `.env` 后**重启后端**（FastAPI 只在启动时读取一次 `.env`）。
2. 打开 <http://localhost:8000/api/health>，`deepseek_configured` 应为 `true`，页面里不会显示 Key 本身。
3. 再回到页面发送一条消息，确认能收到模型回复。

## 3. 启动后端

Linux / macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

后端健康检查：<http://localhost:8000/api/health>

## 4. 启动前端

打开第二个终端：

```bash
pnpm install
pnpm dev -- --host 0.0.0.0
```

按照终端显示的 Local URL 打开页面。通常为 <http://localhost:3000> 或 <http://localhost:5173>。

如果后端不是 `http://localhost:8000`，创建 `.env.local`：

```dotenv
VITE_API_BASE_URL=http://你的后端地址:8000
```

## API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/health` | 检查数据库、模型名和 Key 配置状态 |
| `POST` | `/api/chat` | 发送消息并返回回复、识别结果和可选套餐 |
| `GET` | `/api/products` | 查询四档 Onely 套餐 |
| `GET` | `/api/sessions/{id}/messages` | 恢复匿名会话 |
| `DELETE` | `/api/sessions/{id}` | 清空会话 |

`POST /api/chat` 示例：

```json
{
  "session_id": "可选 UUID",
  "message": "我们是小团队，需要每天高频更新"
}
```

## 测试

```bash
source .venv/bin/activate
PYTHONPATH=backend pytest -q backend/tests
pnpm build
```

Windows PowerShell：

```powershell
$env:PYTHONPATH="backend"
pytest -q backend\tests
pnpm build
```

建议的手工测试：

1. “我最近做内容有点焦虑，感觉忙不过来”——先理解情绪，不强行推荐。
2. “我们是小团队，需要每天高频更新”——返回 Pro 卡片。
3. “我刚开始做内容，预算不高”——返回 Starter 卡片。
4. 刷新页面——恢复历史消息。
5. 点击“重新开始”——清空当前会话。

## 项目结构

```text
app/                    # React/Vinext 前端
backend/app/main.py     # FastAPI、DeepSeek、SQLite 和推荐逻辑
backend/tests/          # API 与兜底规则测试
public/                 # Nola 头像与社交预览
.env.example            # 无敏感信息的配置模板
```

## 常见问题

### 页面提示没有配置 DEEPSEEK_API_KEY

确认根目录存在 `.env`，Key 没有引号和多余空格，然后重启后端。

### DeepSeek 请求失败

确认 Key 有余额且服务器能访问 `https://api.deepseek.com`。短暂超时或模型非结构化输出会自动使用关键词规则兜底。

### 前端无法连接后端

确认 FastAPI 正在 8000 端口运行，并检查 `VITE_API_BASE_URL` 与 `CORS_ORIGINS`。

### 为什么不实时抓取 Onely 网站？

这是一个一小时 MVP。产品资料作为种子数据随项目交付，可以稳定演示、快速审核，也不会依赖未开放的网站源码或接口。

## 数据与隐私

- 不包含账号体系，使用浏览器生成的匿名 UUID。
- 聊天消息保存在本地 `backend/data/nola_demo.db`。
- 输入会发送给 DeepSeek API；请勿输入敏感个人信息。
- 情绪标签只用于调整交流语气，不构成心理或医疗诊断。

## 信息来源

- Onely 官网：<https://www.onely.cc/>
- DeepSeek API 文档：<https://api-docs.deepseek.com/>

## License

MIT
