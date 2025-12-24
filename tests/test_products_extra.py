import pytest

from app.features.products import crud as products_crud
from app.features.products.schemas import PrCreate


@pytest.mark.asyncio
async def test_get_products_by_ids_returns_empty_for_empty_list(db):
    products = await products_crud.get_products_by_ids(db, [])
    assert products == []


@pytest.mark.asyncio
async def test_create_product_without_existing_image_sets_null(db):
    product = PrCreate(
        manufacturer="NoImage",
        name="Ghost",
        dimensions="1x1",
        unit="шт",
        price=10,
        quantity_available=1,
        image_path="missing.jpg",
    )
    created = await products_crud.create_product(db, product)
    assert created.image_path is None
