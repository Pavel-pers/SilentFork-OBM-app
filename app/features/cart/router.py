from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.infra.db import get_db
from app.features.cart import crud as cart_crud
from app.features.cart.schemas import CartItemCreate, CartItemUpdate
from app.features.products import crud as product_crud
from app.features.auth.dependencies import get_current_user, get_optional_user
from app.infra.templates import templates
from app.models.user import User

router = APIRouter(prefix="/cart", tags=["cart"])


async def check_product_availability(db: AsyncSession, product_id: int, required_quantity: int):
    product = await product_crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if product.quantity_available < required_quantity:
        raise HTTPException(status_code=400, detail="Недостаточно товара на складе")
    return product


@router.get("/", response_class=HTMLResponse)
async def cart_page(req: Request, user: User | None = Depends(get_optional_user)):
    return templates.TemplateResponse(req, "cart/view.html", {"user": user})


@router.get("/api")
async def get_cart(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = await cart_crud.CartCRUD.get_cart_items(db, current_user.user_id)
    if not items:
        return {"items": [], "total_price": 0}
    data = []
    total_price = 0
    for item in items:
        if item.product:
            item_total = item.product.price * item.quantity
            data.append({
                "cart_item_id": item.cart_item_id,
                "product_id": item.product.product_id,
                "name": item.product.name,
                "price": item.product.price,
                "quantity": item.quantity,
                "total": item_total
            })
            total_price += item_total

    return {"items": data, "total_price": total_price}


@router.post("/items/")
async def add_item(item_data: CartItemCreate, db: AsyncSession = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    await check_product_availability(db, item_data.product_id, item_data.quantity)
    cart_item = await cart_crud.CartCRUD.add_to_cart(db, current_user.user_id, item_data)
    cart_item_with_product = await cart_crud.CartCRUD.get_cart_item(db, current_user.user_id, cart_item.cart_item_id)
    price_rub = cart_item_with_product.product.price / 100
    return {"cart_item_id": cart_item_with_product.cart_item_id,
            "product_id": cart_item_with_product.product.product_id,
            "name": cart_item_with_product.product.name, "price": price_rub,
            "quantity": cart_item_with_product.quantity, "total": price_rub * cart_item_with_product.quantity}


@router.put("/items/{item_id}")
async def update_cart_item(item_id: int, update: CartItemUpdate, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    cart_item = await cart_crud.CartCRUD.get_cart_item(db, current_user.user_id, item_id)
    if not cart_item:
        raise HTTPException(status_code=404, detail="Товар не найден в корзине")
    product = await check_product_availability(db, cart_item.product_id, update.quantity)
    updated_item = await cart_crud.CartCRUD.update_cart_item(db, current_user.user_id, item_id, update.quantity)

    if not updated_item:
        return {"deleted": item_id}

    return {"cart_item_id": item_id, "product_id": product.product_id,
            "quantity": update.quantity, "total": product.price * update.quantity / 100}


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
