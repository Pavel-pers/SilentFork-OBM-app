from decimal import Decimal

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import get_current_user, get_optional_user
from app.features.cart import crud as cart_crud
from app.features.cart.schemas import CartItemCreate, CartItemUpdate
from app.features.products import crud as product_crud
from app.infra.db import get_db
from app.infra.templates import templates
from app.models.user import User

router = APIRouter(prefix="/cart", tags=["cart"])


def format_price(value: Decimal | int | float) -> float:
    """Convert Decimal values to a rounded float for JSON responses."""
    return round(float(value or 0), 2)


async def check_product_availability(db: AsyncSession, product_id: int, required_quantity: int):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if required_quantity <= 0:
        raise HTTPException(status_code=400, detail="Количество должно быть больше нуля")
    if product.quantity_available is None or product.quantity_available < required_quantity:
        raise HTTPException(status_code=400, detail="Недостаточно товара на складе")
    return product


@router.get("/", response_class=HTMLResponse)
async def cart_page(req: Request, user: User | None = Depends(get_optional_user)):
    return templates.TemplateResponse("cart/view.html", {"request": req, "user": user})


@router.get("/api")
async def get_cart(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = await cart_crud.CartCRUD.get_cart_items(db, current_user.user_id)
    if not items:
        return {"items": [], "total_price": 0}

    data = []
    total_price = 0.0
    for item in items:
        if item.product:
            price = format_price(item.product.price)
            item_total = format_price(item.product.price * item.quantity)
            data.append({
                "cart_item_id": item.cart_item_id,
                "product_id": item.product.product_id,
                "name": item.product.name,
                "price": price,
                "quantity": item.quantity,
                "total": item_total
            })
            total_price += item_total

    return {"items": data, "total_price": round(total_price, 2)}


@router.post("/items/")
async def add_item(
    item_data: CartItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing_item = await cart_crud.CartCRUD.get_cart_item_by_product(
        db, current_user.user_id, item_data.product_id
    )
    current_qty = existing_item.quantity if existing_item else 0

    await check_product_availability(db, item_data.product_id, current_qty + item_data.quantity)

    cart_item = await cart_crud.CartCRUD.add_to_cart(db, current_user.user_id, item_data)
    cart_item_with_product = await cart_crud.CartCRUD.get_cart_item(
        db, current_user.user_id, cart_item.cart_item_id
    )

    price_value = format_price(cart_item_with_product.product.price)
    total_value = format_price(cart_item_with_product.product.price * cart_item_with_product.quantity)

    return {
        "cart_item_id": cart_item_with_product.cart_item_id,
        "product_id": cart_item_with_product.product.product_id,
        "name": cart_item_with_product.product.name,
        "price": price_value,
        "quantity": cart_item_with_product.quantity,
        "total": total_value
    }


@router.put("/items/{item_id}")
async def update_cart_item(
    item_id: int,
    update: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cart_item = await cart_crud.CartCRUD.get_cart_item(db, current_user.user_id, item_id)
    if not cart_item:
        raise HTTPException(status_code=404, detail="Товар не найден в корзине")

    if update.quantity <= 0:
        removed = await cart_crud.CartCRUD.remove_from_cart(db, current_user.user_id, item_id)
        return {"deleted": item_id} if removed else {"cart_item_id": item_id, "quantity": 0}

    product = await check_product_availability(db, cart_item.product_id, update.quantity)
    updated_item = await cart_crud.CartCRUD.update_cart_item(
        db, current_user.user_id, item_id, update.quantity
    )

    if not updated_item:
        return {"deleted": item_id}

    return {
        "cart_item_id": item_id,
        "product_id": product.product_id,
        "quantity": update.quantity,
        "price": format_price(product.price),
        "total": format_price(product.price * update.quantity)
    }


@router.delete("/items/{item_id}")
async def remove_item(item_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = await cart_crud.CartCRUD.remove_from_cart(db, current_user.user_id, item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Товар не найден в корзине")
    return {"deleted": item_id}


@router.post("/clear")
async def clear_cart(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = await cart_crud.CartCRUD.clear_cart(db, current_user.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Корзина не найдена")
    return {"cleared": True}
