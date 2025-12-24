import pytest


@pytest.mark.asyncio
async def test_login_page_renders(async_app_client):
    client, _ = async_app_client
    response = await client.get("/auth/login")
    assert response.status_code == 200
    assert "Вход в СтройМаг" in response.text
    assert "<form" in response.text


@pytest.mark.asyncio
async def test_register_page_renders(async_app_client):
    client, _ = async_app_client
    response = await client.get("/auth/register")
    assert response.status_code == 200
    assert "Регистрация" in response.text
    assert "first_name" in response.text


@pytest.mark.asyncio
async def test_catalog_page_renders(async_app_client):
    client, _ = async_app_client
    response = await client.get("/products/catalog")
    assert response.status_code == 200
    assert "Каталог строительных материалов" in response.text


@pytest.mark.asyncio
async def test_cart_page_renders(async_app_client):
    client, _ = async_app_client
    response = await client.get("/cart/")
    assert response.status_code == 200
    assert "Корзина" in response.text or "Корзины" in response.text


@pytest.mark.asyncio
async def test_root_redirects_to_catalog(async_app_client):
    client, _ = async_app_client
    response = await client.get("/", follow_redirects=True)
    assert response.status_code == 200
    assert "Каталог строительных материалов" in response.text
