from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, RedirectResponse

_BADGE_SCRIPT_PATH = Path(__file__).parent / "assets" / "progress_badge.js"


def configure_dev_helpers(app: FastAPI) -> None:
    """Redirect / to /docs and inject the live WebSocket job progress badge into Swagger UI."""
    badge_js = _BADGE_SCRIPT_PATH.read_text(encoding="utf-8")

    @app.get("/", include_in_schema=False)
    async def redirect_to_docs() -> RedirectResponse:
        """If env is development, redirect / to Swagger UI."""
        return RedirectResponse(url="/docs")

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui() -> HTMLResponse:
        """If env is development, then we inject progress_badge.js into Swagger UI."""
        swagger_html = get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{app.title} - Swagger UI",
        )
        body = swagger_html.body.decode("utf-8").replace(
            "</body>", f"<script>{badge_js}</script></body>"
        )
        return HTMLResponse(content=body, status_code=swagger_html.status_code)
