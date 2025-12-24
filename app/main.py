from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.settings import settings
from app.features.auth.dependencies import get_optional_user
from app.models.user import User


def create_app() -> FastAPI:
    app = FastAPI(title="Online Building Materials Store")

    static_dir = Path(settings.STATIC_ROOT)
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    media_dir = Path(settings.MEDIA_ROOT)
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    templates_dir = Path(__file__).parent.parent / "web" / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # routers
    from app.features.auth.router import router as auth_router
    from app.features.auth.form_router import router as auth_form_router
    from app.features.cart.router import router as cart_router
    from app.features.orders.form_router import router as orders_router
    from app.features.products.router import router as products_router
    from app.features.products.form_router import router as products_form_router
    from app.features.users.router import router as users_router
    from app.features.staff.router import router as staff_router

    app.include_router(auth_router)
    app.include_router(auth_form_router)
    app.include_router(users_router)
    app.include_router(products_router)
    app.include_router(products_form_router)
    app.include_router(cart_router)
    app.include_router(orders_router)
    app.include_router(staff_router)

    return app


app = create_app()
