from fastapi import FastAPI
from fastapi.responses import RedirectResponse


def configure_dev_helpers(app: FastAPI):
    """Redirect / to /docs"""
    @app.get("/", include_in_schema=False)
    async def redirect_to_docs():
        return RedirectResponse(url="/docs")