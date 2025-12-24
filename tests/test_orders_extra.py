import pytest

from app.features.orders.schemas import OrderCreate
from app.features.orders.service import create_simple_order
from app.models.cart import Cart
from app.models.user import User, UserRole


def test_order_create_schema_holds_email():
    data = OrderCreate(email="test@example.com")
    assert data.email == "test@example.com"


@pytest.mark.asyncio
async def test_create_simple_order_requires_authenticated_user(db):
    with pytest.raises(ValueError, match="Не авторизован"):
        await create_simple_order(db, order_email="a@b.c", phone="+7 999", address="addr", user=None)


@pytest.mark.asyncio
async def test_create_simple_order_with_empty_cart(db):
    user = User.create_with_encryption(
        first_name="Test",
        last_name="User",
        phone="+7 999 111-22-33",
        email="emptycart@example.com",
        password_hash="hash",
        role=UserRole.CLIENT,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    cart = Cart(user_id=user.user_id)
    db.add(cart)
    await db.commit()

    with pytest.raises(ValueError, match="Корзина пуста"):
        await create_simple_order(db, order_email=user.email, phone=user.phone, address="addr", user=user)
