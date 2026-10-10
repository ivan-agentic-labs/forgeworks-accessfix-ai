"""Pure-ASGI body budget tests; no database or external credentials needed."""
import asyncio

from accessfix_ai.presentation.body_budget import BodyBudgetMiddleware


def exercise(parts, *, max_bytes=6, max_chunks=4, headers=()):
    seen, messages = [], []
    events = [{"type": "http.request", "body": part,
               "more_body": index < len(parts) - 1}
              for index, part in enumerate(parts)]
    async def receive():
        if events:
            return events.pop(0)
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    async def endpoint(scope, inner_receive, inner_send):
        seen.append((await inner_receive()).get("body", b""))
        await inner_send({"type": "http.response.start", "status": 200, "headers": []})
        await inner_send({"type": "http.response.body", "body": b"ok"})

    scope = {"type": "http", "method": "POST", "path": "/",
             "headers": list(headers)}
    asyncio.run(BodyBudgetMiddleware(endpoint, max_bytes=max_bytes,
                                     max_chunks=max_chunks)(scope, receive, send))
    return next((m["status"] for m in messages
                 if m["type"] == "http.response.start"), None), seen


def test_chunked_body_at_limit_replayed_once():
    assert exercise([b"abc", b"def"]) == (200, [b"abcdef"])


def test_chunked_actual_bytes_over_limit_rejected():
    assert exercise([b"abc", b"defg"]) == (413, [])


def test_declared_oversize_rejected_before_body_read():
    assert exercise([b"ok"], headers=[(b"content-length", b"7")]) == (413, [])


def test_duplicate_and_malformed_content_length_rejected():
    assert exercise([b"x"], headers=[(b"content-length", b"1"), (b"content-length", b"1")]) == (400, [])
    assert exercise([b"x"], headers=[(b"content-length", b"NaN")]) == (400, [])


def test_empty_chunk_flood_is_bounded():
    assert exercise([b"", b"", b"", b"", b""]) == (413, [])


def test_empty_body_allowed():
    assert exercise([b""]) == (200, [b""])
