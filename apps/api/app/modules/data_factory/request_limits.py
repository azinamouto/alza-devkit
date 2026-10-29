"""Bound custom request bodies before JSON parsing (including chunked requests)."""
from starlette.responses import JSONResponse


def get_limit_for_path(path: str) -> int:
    """Return the appropriate size limit based on the request path."""
    if path.startswith("/api/v1/schema-import"):
        return 2_000_000
    return 262144


def format_size_limit(limit: int) -> str:
    """Format byte limit as human-readable string."""
    if limit >= 1_000_000:
        return f"{limit / 1_000_000:.1f} MB"
    if limit >= 1_000:
        return f"{limit / 1_000:.0f} KB"
    return f"{limit} bytes"


class CustomBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or not (path.startswith("/api/v1/data-factory/custom") or path.startswith("/api/v1/data-factory/templates") or path.startswith("/api/v1/schema-import")):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        limit = get_limit_for_path(path)
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > limit:
                formatted_limit = format_size_limit(limit)
                return await JSONResponse({"detail": f"Request exceeds the {formatted_limit} limit"}, status_code=413)(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
