"""Regression test the actual API boundary for training-database sync confirmation."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers.telegram_ocr import router


def test_training_sync_endpoint_rejects_missing_explicit_confirmation():
    app = FastAPI()
    app.include_router(router, prefix="/api/telegram-ocr")
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test-user"}

    response = TestClient(app).post("/api/telegram-ocr/trainingdb/sync", json={})

    assert response.status_code == 400
    assert "explicit confirmation required" in response.json()["detail"]
