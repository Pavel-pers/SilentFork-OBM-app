import pytest

from app.models.product import Product


@pytest.mark.asyncio
async def test_registration_login_cart_checkout_flow(async_app_client):
    client, session_factory = async_app_client

    async with session_factory() as session:
        product = Product(
            manufacturer="Flow Inc.",
            name="Поточный товар",
            dimensions="10x10x10",
            unit="шт",
            price=1000,
            quantity_available=5,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        product_id = product.product_id

    email = "flow@example.com"
    password = "StrongPass123"
    user_payload = {
        "email": email,
        "first_name": "Flow",
        "last_name": "Tester",
        "phone": "+7 999 111-22-33",
        "password": password,
        "password_confirm": password,
        "role": "CLIENT",
    }

    register_response = await client.post("/auth/register", json=user_payload)
    assert register_response.status_code == 201

    login_response = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    client.cookies.set("access_token", token)

    add_to_cart_response = await client.post(
        "/cart/items/",
        json={"product_id": product_id, "quantity": 2},
    )
    assert add_to_cart_response.status_code == 200

    checkout_response = await client.post(
        "/orders/checkout",
        data={
            "order_email": email,
            "phone": "+7 999 111-22-33",
            "address": "Тестовый адрес, д. 1",
        },
        follow_redirects=False,
    )

    assert checkout_response.status_code == 303
    assert "location" in checkout_response.headers

    success_page = await client.get(checkout_response.headers["location"])
    assert success_page.status_code == 200
    assert "Заказ успешно оформлен" in success_page.text
    assert "Номер заказа" in success_page.text
