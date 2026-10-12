"""Pure ASGI stream length consistency proof; no external network or database."""
import asyncio
import pytest
from accessfix_ai.presentation.body_budget import BodyBudgetMiddleware


def execute(chunks, declared=None):
    queued = [{"type": "http.request", "body": value, "more_body": index < len(chunks) - 1}
              for index, value in enumerate(chunks)]
    events, reached = [], []
    async def receive():
        if queued:
            return queued.pop(0)
        return {"type": "http.disconnect"}
    async def send(message):
        events.append(message)
    async def endpoint(scope, replay, inner_send):
        reached.append((await replay())["body"])
        await inner_send({"type": "http.response.start", "status": 200, "headers": []})
        await inner_send({"type": "http.response.body", "body": b"ok"})
    headers = [(b"content-length", str(declared).encode())] if declared is not None else []
    asyncio.run(BodyBudgetMiddleware(endpoint, max_bytes=16, max_chunks=5)(
        {"type": "http", "method": "POST", "path": "/synthetic", "headers": headers},
        receive, send,
    ))
    status = next(event["status"] for event in events if event["type"] == "http.response.start")
    return status, reached


@pytest.mark.parametrize("declared,chunks", [
    (3, [b"ab", b"cd"]),
    (5, [b"ab", b"cd"]),
    (0, [b"x"]),
    (1, [b""]),
])
def test_inconsistent_declared_body_length_rejected_without_handler(declared, chunks):
    assert execute(chunks, declared) == (400, [])


@pytest.mark.parametrize("declared,chunks,expected", [
    (4, [b"ab", b"cd"], b"abcd"),
    (0, [b""], b""),
    (None, [b"ab", b"cd"], b"abcd"),
])
def test_exact_and_undeclared_length_requests_keep_functioning(declared, chunks, expected):
    assert execute(chunks, declared) == (200, [expected])


def test_oversized_body_remains_413_not_length_mismatch():
    assert execute([b"x" * 17], 17) == (413, [])
