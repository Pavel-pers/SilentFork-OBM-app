from decimal import Decimal
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User

log = logging.getLogger(__name__)


async def create_simple_order(db: AsyncSession, order_email: str, phone: str, address: str, user: User | None) -> Order:
    if not user:
        raise ValueError("Не авторизован")

    user_id = user.user_id
    cart_stmt = (
        select(Cart).options(selectinload(Cart.items).selectinload(CartItem.product)).where(Cart.user_id == user_id))
    cart_res = await db.execute(cart_stmt)
    cart = cart_res.scalar_one_or_none()

    if not cart:
        raise ValueError("Корзина не найдена")

    if not cart.items:
        raise ValueError("Корзина пуста")

    total_price = Decimal("0.0")
    order_items = []

    for cart_item in cart.items:
        product = cart_item.product
        required_quantity = cart_item.quantity

        if hasattr(product, "quantity_available"):
            if product.quantity_available >= required_quantity:
                product.quantity_available -= required_quantity
            else:
                raise ValueError(f"Недостаточно товара '{product.name}'.")

        total_price += product.price * Decimal(required_quantity)

        order_item = OrderItem(
            product_id=product.product_id,
            quantity=required_quantity,
            price_per_unit=product.price,
            total=product.price * Decimal(required_quantity),
        )
        order_items.append(order_item)

    try:
        order = Order.create_with_encryption(
            user_id=user_id,
            order_email=order_email,
            total_price=total_price,
            address=address,
        )
        db.add(order)
        await db.flush()
        for order_item in order_items:
            order_item.order_id = order.order_id
            db.add(order_item)
        for cart_item in cart.items:
            await db.delete(cart_item)
        await db.delete(cart)
        await db.commit()
        await db.refresh(order)
        log.info("Создан заказ id=%s для пользователя id=%s", order.order_id, user_id)
        return order

    except Exception:  # noqa: BLE001
        log.exception("Ошибка при создании заказа")
        await db.rollback()
        raise
