from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(title="Online Building Materials Store")

    static_dir = Path(settings.STATIC_ROOT)
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    media_dir = Path(settings.MEDIA_ROOT)
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    @app.get("/", include_in_schema=False)
    async def index():
        return RedirectResponse(url="/products/catalog")

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

    app.include_router(auth_router)
    app.include_router(auth_form_router)
    app.include_router(users_router)
    app.include_router(products_router)
    app.include_router(products_form_router)
    app.include_router(cart_router)
    app.include_router(orders_router)

    return app


app = create_app()
