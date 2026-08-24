import asyncio

import httpx
from app.main import app


def request(method: str, path: str, **kwargs: object) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_health_check() -> None:
    response = request("GET", "/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_demo_endpoint_returns_auditable_batch() -> None:
    response = request("POST", "/api/reconcile/demo")
    body = response.json()

    assert response.status_code == 200
    assert body["metrics"]["total_orders"] == 72
    assert body["metrics"]["financial_variance"] == 0
    assert any(item["exception_code"] == "FEE_VARIANCE" for item in body["results"])


def test_development_origin_can_call_the_api() -> None:
    response = request(
        "OPTIONS",
        "/api/reconcile/demo",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
