"""Bound HTTP request bodies before parsing JSON or uploading artifacts.

Rejects oversized Content-Length immediately and counts actual ASGI chunks,
so Transfer-Encoding: chunked cannot bypass the bound. Not a rate limiter.
"""
from starlette.responses import JSONResponse

MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_BODY_CHUNKS = 16384


class BodyBudgetMiddleware:
    def __init__(self, app, max_bytes=MAX_REQUEST_BYTES, max_chunks=MAX_BODY_CHUNKS):
        self.app = app
        self.max_bytes = max_bytes
        self.max_chunks = max_chunks

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def reject(status, code, message):
            response = JSONResponse(
                {"type": "about:blank", "title": "Request rejected",
                 "status": status, "code": code, "detail": message,
                 "request_id": "runtime"},
                status_code=status, media_type="application/problem+json",
            )
            await response(scope, receive, send)

        lengths = [value for name, value in scope.get("headers", [])
                   if name.lower() == b"content-length"]
        if lengths:
            if len(lengths) != 1 or len(lengths[0]) > 20 or not lengths[0].isdigit():
                return await reject(400, "INVALID_CONTENT_LENGTH", "Content-Length must be one decimal integer")
            if int(lengths[0]) > self.max_bytes:
                return await reject(413, "REQUEST_BODY_TOO_LARGE", "Request exceeds the 8 MiB body budget")

        declared_size = int(lengths[0]) if lengths else None
        chunks, size, count = [], 0, 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return  # The caller disconnected; no response can be delivered.
            if event["type"] != "http.request":
                return await reject(400, "INVALID_REQUEST_BODY", "Unexpected ASGI body event")
            body = event.get("body", b"")
            size += len(body)
            count += 1
            if size > self.max_bytes or count > self.max_chunks:
                return await reject(413, "REQUEST_BODY_TOO_LARGE", "Request exceeds the bounded body budget")
            if declared_size is not None and size > declared_size:
                return await reject(400, "INVALID_CONTENT_LENGTH", "Content-Length differs from received bytes")
            if body:
                chunks.append(body)
            if not event.get("more_body", False):
                break

        if declared_size is not None and size != declared_size:
            return await reject(400, "INVALID_CONTENT_LENGTH", "Content-Length differs from received bytes")
        content = b"".join(chunks)
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": content, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
