from pathlib import Path
from uuid import uuid4
from typing import Optional, List

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Request,
    UploadFile,
    File
)
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.features.auth.dependencies import get_current_staff
from app.features.products import crud as product_crud
from app.features.products.schemas import PrCreate
from app.infra.db import get_db
from app.infra.templates import templates
from app.models.product import Product

router = APIRouter(prefix="/staff", tags=["staff"])


async def _save_product_image(upload: Optional[UploadFile]) -> Optional[str]:
    """Сохраняет загруженное фото и возвращает относительный путь для БД."""
    if not upload or not upload.filename:
        return None

    media_root = Path(settings.MEDIA_ROOT)
    media_root.mkdir(parents=True, exist_ok=True)
    products_dir = media_root / "products"
    products_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(upload.filename).suffix or ".jpg"
    filename = f"{uuid4().hex}{extension}"
    dest_path = products_dir / filename

    content = await upload.read()
    dest_path.write_bytes(content)
    return f"products/{filename}"


async def _get_products(db: AsyncSession) -> List[Product]:
    products = await product_crud.get_products(db)
    return products


@router.get("/", response_class=HTMLResponse)
async def staff_dashboard(
        request: Request,
        user=Depends(get_current_staff)
):
    return templates.TemplateResponse(
        "staff/dashboard.html",
        {"request": request, "user": user}
    )


@router.get("/products", response_class=HTMLResponse)
async def staff_products_table(
        request: Request,
        user=Depends(get_current_staff),
        db: AsyncSession = Depends(get_db)
):
    products = await _get_products(db)
    return templates.TemplateResponse(
        "staff/products.html",
        {"request": request, "user": user, "products": products}
    )


@router.get("/products/stock", response_class=HTMLResponse)
async def stock_page(
        request: Request,
        user=Depends(get_current_staff),
        db: AsyncSession = Depends(get_db),
        message: Optional[str] = None,
        error: Optional[str] = None
):
    products = await _get_products(db)
    return templates.TemplateResponse(
        "staff/stock.html",
        {
            "request": request,
            "user": user,
            "products": products,
            "message": message,
            "error": error
        }
    )


@router.post("/products/stock", response_class=HTMLResponse)
async def change_stock(
        request: Request,
        product_id: int = Form(...),
        operation: str = Form(...),  # in|out
        delta: int = Form(...),
        user=Depends(get_current_staff),
        db: AsyncSession = Depends(get_db)
):
    message = None
    error = None

    if delta <= 0:
        error = "Дельта должна быть положительной"
    elif operation not in {"in", "out"}:
        error = "Некорректная операция"
    else:
        try:
            product = await product_crud.get_product(db, product_id)
            if not product:
                error = "Товар не найден"
            else:
                new_quantity = product.quantity_available + delta if operation == "in" else product.quantity_available - delta
                if new_quantity < 0:
                    error = "Недостаточно товара на складе для списания"
                else:
                    product.quantity_available = new_quantity
                    await db.commit()
                    await db.refresh(product)
                    message = f"Количество доступного продукта {product.name} изменено: {product.quantity_available}"
        except Exception as exc:
            await db.rollback()
            error = f"Ошибка при обновлении стока: {exc}"

    products = await _get_products(db)

    return templates.TemplateResponse(
        "staff/stock.html",
        {
            "request": request,
            "user": user,
            "products": products,
            "message": message,
            "error": error,
            "current_product_id": product_id,
            "current_operation": operation,
            "current_delta": delta
        }
    )


@router.get("/products/new", response_class=HTMLResponse)
async def new_product_page(
        request: Request,
        user=Depends(get_current_staff)
):
    return templates.TemplateResponse(
        "staff/add_product.html",
        {"request": request, "user": user, "message": None, "error": None}
    )


@router.post("/products/new", response_class=HTMLResponse)
async def create_new_product(
        request: Request,
        manufacturer: str = Form(...),
        name: str = Form(...),
        dimensions: Optional[str] = Form(None),
        unit: str = Form(...),
        price: float = Form(...),
        quantity_available: int = Form(0),
        image: UploadFile | None = File(None),
        user=Depends(get_current_staff),
        db: AsyncSession = Depends(get_db)
):
    message = None
    error = None
    image_path = None

    try:
        if quantity_available < 0:
            raise ValueError("Количество не может быть отрицательным")

        image_path = await _save_product_image(image)

        price_value = int(round(float(price)))

        product = PrCreate(
            manufacturer=manufacturer,
            name=name,
            dimensions=dimensions or None,
            unit=unit,
            price=price_value,
            quantity_available=quantity_available,
            image_path=image_path
        )

        created = await product_crud.create_product(db, product)
        message = f"Товар добавлен: {created.name}"
    except Exception as exc:
        error = f"Ошибка при добавлении товара: {exc}"

    return templates.TemplateResponse(
        "staff/add_product.html",
        {
            "request": request,
            "user": user,
            "message": message,
            "error": error
        }
    )
