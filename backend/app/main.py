from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "backend/data/nola_demo.db"))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = ROOT_DIR / DATABASE_PATH

PURCHASE_URL = "https://www.onely.cc/studio/signup"
VALID_PRODUCT_CODES = {"starter", "standard", "pro", "agency"}

PRODUCTS = [
    {
        "code": "starter",
        "name": "Starter",
        "price": "$29",
        "credits": "300 Credits",
        "description": "适合第一次搭建 creator identity，并验证基础内容和收入闭环。",
        "target_user": "个人、新手、首次验证、预算较低",
        "features": ["首次验证更轻量", "个人创作者友好", "成本门槛低"],
        "purchase_url": PURCHASE_URL,
    },
    {
        "code": "standard",
        "name": "Standard",
        "price": "$99",
        "credits": "1,000 Credits",
        "description": "适合稳定内容生产、粉丝页运营和多种收入方式测试。",
        "target_user": "已开始稳定运营，希望持续产出并经营粉丝关系",
        "features": ["持续内容生产", "粉丝关系运营", "多种收入测试"],
        "purchase_url": PURCHASE_URL,
    },
    {
        "code": "pro",
        "name": "Pro",
        "price": "$199",
        "credits": "2,000 Credits",
        "description": "适合高频内容、多品牌运营，以及需要协作的小团队。",
        "target_user": "小团队、高频更新、多品牌运营",
        "features": ["高频生产", "多品牌运营", "小团队协作"],
        "purchase_url": PURCHASE_URL,
    },
    {
        "code": "agency",
        "name": "Agency",
        "price": "Custom",
        "credits": "按方案配置",
        "description": "适合规模化管理多个 creator、角色权限、内容与收入数据。",
        "target_user": "机构、多个 creator、复杂权限和规模化运营",
        "features": ["多 creator 管理", "角色与权限", "规模化运营"],
        "purchase_url": PURCHASE_URL,
    },
]

ONELY_KNOWLEDGE = """
Onely 是 AI-powered creator business platform，帮助 creators、agencies 和 character-led brands
完成 creator identity、内容生产、社交发布、受众增长、粉丝关系、订阅和电商变现。
核心模块包括 Identity Builder、Content Studio、Publishing Workspace、Fan Relationship Layer、
Subscriptions & E-commerce、Agency Console。变现方式包括订阅、付费内容、1:1 粉丝互动、
定制请求、电商/数字商品/课程/联盟营销和品牌合作。
套餐：Starter $29/300 Credits；Standard $99/1,000 Credits；Pro $199/2,000 Credits；
Agency 为 Custom。Credits 参考消耗：Identity Setup 30、Per Image 2、Per Social Post 1、
Relationship Support 0.2。当前公开页面标注 Private Beta Access。
""".strip()


class Signals(BaseModel):
    emotion: str
    stage: str
    need: str


class Product(BaseModel):
    code: str
    name: str
    price: str
    credits: str
    description: str
    target_user: str
    features: list[str]
    purchase_url: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    reply: str
    signals: Signals
    product: Product | None


class HistoryMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    product: Product | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_db() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with connect_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price TEXT NOT NULL,
                credits TEXT NOT NULL,
                description TEXT NOT NULL,
                target_user TEXT NOT NULL,
                features_json TEXT NOT NULL,
                purchase_url TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                emotion TEXT,
                stage TEXT,
                need TEXT,
                recommended_product_code TEXT,
                recommendation_reason TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY(recommended_product_code) REFERENCES products(code)
            )
            """
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session_created ON messages(session_id, created_at)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_product ON messages(recommended_product_code) WHERE recommended_product_code IS NOT NULL"
        )
        for product in PRODUCTS:
            db.execute(
                """
                INSERT INTO products (
                    code, name, price, credits, description, target_user,
                    features_json, purchase_url, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name,
                    price=excluded.price,
                    credits=excluded.credits,
                    description=excluded.description,
                    target_user=excluded.target_user,
                    features_json=excluded.features_json,
                    purchase_url=excluded.purchase_url,
                    updated_at=excluded.updated_at
                """,
                (
                    product["code"],
                    product["name"],
                    product["price"],
                    product["credits"],
                    product["description"],
                    product["target_user"],
                    json.dumps(product["features"], ensure_ascii=False),
                    product["purchase_url"],
                    now_iso(),
                ),
            )
        db.execute("PRAGMA optimize")


def row_to_product(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "code": row["code"],
        "name": row["name"],
        "price": row["price"],
        "credits": row["credits"],
        "description": row["description"],
        "target_user": row["target_user"],
        "features": json.loads(row["features_json"]),
        "purchase_url": row["purchase_url"],
    }


def get_product(code: str | None) -> dict[str, Any] | None:
    if not code:
        return None
    with connect_db() as db:
        return row_to_product(db.execute("SELECT * FROM products WHERE code = ?", (code,)).fetchone())


def valid_session_id(value: str | None) -> str:
    if not value:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="session_id 必须是合法 UUID") from exc


def fallback_analysis(message: str) -> dict[str, Any]:
    lowered = message.lower()
    pressure = bool(re.search(r"压力|焦虑|累|疲惫|难受|没动力|沮丧", message))
    confused = bool(re.search(r"迷茫|犹豫|纠结|不知道|怎么选", message))
    excited = bool(re.search(r"开心|兴奋|顺利|期待", message))
    agency = bool(re.search(r"多个\s*creator|多个创作者|机构|agency|权限管理|规模化", lowered))
    pro = bool(re.search(r"高频|每天更新|小团队|多品牌|协作", lowered))
    standard = bool(re.search(r"稳定|每周|粉丝|收入测试|持续内容", lowered))
    starter = bool(re.search(r"刚开始|新手|第一次|起步|预算.{0,3}(低|不高|有限)|starter", lowered))

    if pressure:
        emotion = "有些压力 / 焦虑"
    elif confused:
        emotion = "迷茫 / 犹豫"
    elif excited:
        emotion = "状态不错 / 兴奋"
    else:
        emotion = "平静"

    if agency:
        product_code, stage, need = "agency", "机构规模化运营", "多账号与权限管理"
    elif pro:
        product_code, stage, need = "pro", "小团队运营", "高频内容生产"
    elif standard:
        product_code, stage, need = "standard", "稳定运营", "持续内容与粉丝经营"
    elif starter:
        product_code, stage, need = "starter", "刚刚起步", "低成本验证"
    else:
        product_code = None
        stage = "待进一步了解"
        need = "需要继续交流" if pressure or confused else "自由交流"

    if product_code:
        product = next(item for item in PRODUCTS if item["code"] == product_code)
        reply = (
            ("听起来你已经扛了不少事情，我们先把选择变简单一点。" if pressure else "我明白你的方向了。")
            + f" 按你现在的情况，{product['name']} 会更匹配：{product['description']}"
        )
    elif pressure:
        reply = "听起来你最近承受了不少压力。我们不用急着一次解决全部问题；你现在更卡在持续产出内容，还是不知道怎样把内容变成稳定收入？"
    elif confused:
        reply = "纠结很正常，我们可以把问题拆小一点。你现在是个人尝试还是团队运营？大概多久更新一次内容？"
    else:
        reply = "我在听。你可以告诉我你目前是个人还是团队、内容更新频率，以及最想解决的问题，我会结合 Onely 的公开信息帮你梳理。"

    return {
        "reply": reply,
        "emotion": emotion,
        "stage": stage,
        "need": need,
        "product_code": product_code,
        "recommendation_reason": reply if product_code else None,
    }


def get_recent_history(session_id: str) -> list[dict[str, str]]:
    with connect_db() as db:
        rows = db.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 10",
            (session_id,),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


async def ask_deepseek(message: str, history: list[dict[str, str]]) -> dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="未配置 DEEPSEEK_API_KEY。请复制 .env.example 为 .env 并填写自己的 Key。",
        )

    system_prompt = f"""
你是 Nola，一位亲切、简洁、不过度推销的创作者业务问答助手。
你的任务：回答用户关于 Onely 和创作者运营的问题；理解情绪；必要时从四个套餐中推荐一个。
不要做心理或医疗诊断；用户明显焦虑时先表示理解，再提出一个简单问题。
产品事实只能使用以下素材，不要编造价格、Credits 或能力：
{ONELY_KNOWLEDGE}

必须只返回一个 JSON 对象，不要 Markdown，不要代码围栏：
{{
  "reply": "亲切自然的中文回复，通常 2-4 句",
  "emotion": "平静|有些压力 / 焦虑|迷茫 / 犹豫|状态不错 / 兴奋",
  "stage": "简短的用户阶段",
  "need": "简短的当前需求",
  "product_code": "starter|standard|pro|agency|null",
  "recommendation_reason": "推荐理由；不推荐时为 null"
}}
推荐规则：机构/多 creator/复杂权限优先 Agency；小团队且高频或多品牌用 Pro；稳定内容和粉丝经营用 Standard；新手或预算较低用 Starter；信息不足就不推荐并追问。
""".strip()

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        timeout=25.0,
        max_retries=1,
    )
    messages = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": message}]
    response = await client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.5,
        max_tokens=700,
    )
    content = response.choices[0].message.content or ""
    parsed = json.loads(content)
    if not isinstance(parsed, dict) or not str(parsed.get("reply", "")).strip():
        raise ValueError("DeepSeek 返回内容缺少 reply")

    code = parsed.get("product_code")
    if code not in VALID_PRODUCT_CODES:
        code = None
    return {
        "reply": str(parsed["reply"]).strip()[:1800],
        "emotion": str(parsed.get("emotion") or "平静")[:40],
        "stage": str(parsed.get("stage") or "待进一步了解")[:60],
        "need": str(parsed.get("need") or "自由交流")[:60],
        "product_code": code,
        "recommendation_reason": (
            str(parsed.get("recommendation_reason") or "")[:500] if code else None
        ),
    }


def save_exchange(session_id: str, message: str, result: dict[str, Any]) -> str:
    timestamp = now_iso()
    assistant_id = str(uuid.uuid4())
    with connect_db() as db:
        db.execute(
            "INSERT INTO sessions(id, created_at, updated_at) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at",
            (session_id, timestamp, timestamp),
        )
        db.execute(
            "INSERT INTO messages(id, session_id, role, content, created_at) VALUES (?, ?, 'user', ?, ?)",
            (str(uuid.uuid4()), session_id, message, timestamp),
        )
        db.execute(
            """
            INSERT INTO messages(
                id, session_id, role, content, emotion, stage, need,
                recommended_product_code, recommendation_reason, created_at
            ) VALUES (?, ?, 'assistant', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assistant_id,
                session_id,
                result["reply"],
                result["emotion"],
                result["stage"],
                result["need"],
                result["product_code"],
                result["recommendation_reason"],
                now_iso(),
            ),
        )
    return assistant_id


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Nola × Onely MVP API", version="1.0.0", lifespan=lifespan)
origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8788,http://127.0.0.1:8788").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "database": DATABASE_PATH.exists(),
        "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    }


@app.get("/api/products", response_model=list[Product])
def products() -> list[dict[str, Any]]:
    with connect_db() as db:
        rows = db.execute("SELECT * FROM products ORDER BY CASE code WHEN 'starter' THEN 1 WHEN 'standard' THEN 2 WHEN 'pro' THEN 3 ELSE 4 END").fetchall()
    return [row_to_product(row) for row in rows]


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> dict[str, Any]:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="消息不能为空")
    session_id = valid_session_id(payload.session_id)
    history = get_recent_history(session_id)
    try:
        result = await ask_deepseek(message, history)
    except HTTPException:
        raise
    except Exception:
        result = fallback_analysis(message)
    message_id = save_exchange(session_id, message, result)
    return {
        "session_id": session_id,
        "message_id": message_id,
        "reply": result["reply"],
        "signals": {
            "emotion": result["emotion"],
            "stage": result["stage"],
            "need": result["need"],
        },
        "product": get_product(result["product_code"]),
    }


@app.get("/api/sessions/{session_id}/messages", response_model=list[HistoryMessage])
def history(session_id: str) -> list[dict[str, Any]]:
    session_id = valid_session_id(session_id)
    with connect_db() as db:
        rows = db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    output = []
    for row in rows:
        output.append(
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
                "product": get_product(row["recommended_product_code"]),
            }
        )
    return output


@app.delete("/api/sessions/{session_id}", status_code=204)
def reset_session(session_id: str) -> None:
    session_id = valid_session_id(session_id)
    with connect_db() as db:
        db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
