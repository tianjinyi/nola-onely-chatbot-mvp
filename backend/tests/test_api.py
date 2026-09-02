import os
from pathlib import Path

os.environ["DATABASE_PATH"] = str(Path(__file__).parent / "test_nola.db")
os.environ.pop("DEEPSEEK_API_KEY", None)

from fastapi.testclient import TestClient

from app import main


def setup_function():
    if main.DATABASE_PATH.exists():
        main.DATABASE_PATH.unlink()
    main.init_db()


def teardown_function():
    if main.DATABASE_PATH.exists():
        main.DATABASE_PATH.unlink()


def test_health_does_not_expose_secret():
    with TestClient(main.app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["deepseek_configured"] is False
    assert "api_key" not in body


def test_products_are_seeded():
    with TestClient(main.app) as client:
        response = client.get("/api/products")
    assert response.status_code == 200
    assert [item["code"] for item in response.json()] == ["starter", "standard", "pro", "agency"]


def test_missing_key_returns_clear_503():
    with TestClient(main.app) as client:
        response = client.post("/api/chat", json={"message": "你好"})
    assert response.status_code == 503
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_deepseek_result_is_saved_and_product_is_authoritative(monkeypatch):
    async def fake_ask(message, history):
        assert message == "我们是三个人的小团队，每天更新"
        return {
            "reply": "Pro 更适合你们。",
            "emotion": "平静",
            "stage": "小团队运营",
            "need": "高频内容生产",
            "product_code": "pro",
            "recommendation_reason": "小团队加高频更新",
        }

    monkeypatch.setattr(main, "ask_deepseek", fake_ask)
    with TestClient(main.app) as client:
        response = client.post("/api/chat", json={"message": "我们是三个人的小团队，每天更新"})
        session_id = response.json()["session_id"]
        history = client.get(f"/api/sessions/{session_id}/messages")
    assert response.status_code == 200
    assert response.json()["product"]["code"] == "pro"
    assert response.json()["product"]["price"] == "$199"
    assert [item["role"] for item in history.json()] == ["user", "assistant"]


def test_invalid_json_or_timeout_uses_keyword_fallback(monkeypatch):
    async def broken_ask(message, history):
        raise ValueError("invalid json")

    monkeypatch.setattr(main, "ask_deepseek", broken_ask)
    with TestClient(main.app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "我们是小团队，需要每天高频更新"},
        )
    assert response.status_code == 200
    assert response.json()["product"]["code"] == "pro"


def test_all_fallback_product_mappings():
    cases = {
        "我刚开始做内容，预算不高": "starter",
        "我已经稳定更新，也在经营粉丝": "standard",
        "我们是小团队，需要高频更新": "pro",
        "我们是机构，需要管理多个 creator 和权限": "agency",
    }
    for message, expected in cases.items():
        assert main.fallback_analysis(message)["product_code"] == expected


def test_reset_deletes_history(monkeypatch):
    async def fake_ask(message, history):
        return main.fallback_analysis(message)

    monkeypatch.setattr(main, "ask_deepseek", fake_ask)
    with TestClient(main.app) as client:
        chat = client.post("/api/chat", json={"message": "我刚开始做内容"})
        session_id = chat.json()["session_id"]
        assert client.delete(f"/api/sessions/{session_id}").status_code == 204
        assert client.get(f"/api/sessions/{session_id}/messages").json() == []
