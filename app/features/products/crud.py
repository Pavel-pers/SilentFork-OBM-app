from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlalchemy import select
from app.models.product import Product
from app.features.products.schemas import PrCreate, PrUpdate
from fastapi import HTTPException
from app.infra.media_checker import check_media_file_exists

async def get_product(db: AsyncSession, product_id: int) -> Optional[Product]:
    try:
        stmt = select(Product).where(Product.product_id == product_id)
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()
        return product
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении товара: {str(e)}"
        )

async def get_products(db: AsyncSession) -> List[Product]:
    try:
        stmt = select(Product)
        result = await db.execute(stmt)
        products = list(result.scalars().all())
        return products
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении товаров: {str(e)}"
        )

async def get_products_by_ids(db: AsyncSession, product_ids: List[int]) -> List[Product]:
    try:
        if not product_ids:
            return []
        stmt = select(Product).where(Product.product_id.in_(product_ids))
        result = await db.execute(stmt)
        products = list(result.scalars().all())
        return products
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении товаров: {str(e)}"
        )

# то же самое для staff
async def create_product(db: AsyncSession, product: PrCreate) -> Product:
    try:
        product_data = product.model_dump()
        db_pr = Product(**product_data)

        if db_pr.image_path and not check_media_file_exists(db_pr.image_path):
            db_pr.image_path = None

        db.add(db_pr)
        await db.commit()
        await db.refresh(db_pr)
        
        return db_pr
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании товара: {str(e)}"
        )

# то же самое для staff
async def update_product(db: AsyncSession, product_id: int, update_data: PrUpdate) -> Optional[Product]:
    try:
        stmt = select(Product).where(Product.product_id == product_id)
        result = await db.execute(stmt)
        db_pr = result.scalar_one_or_none()
        
        if not db_pr:
            raise HTTPException(status_code=404, detail="Товар не найден")
        
        updated = update_data.model_dump(exclude_unset=True)

        if 'image_path' in updated:
            if updated['image_path'] and not check_media_file_exists(updated['image_path']):
                updated['image_path'] = None

        for key, value in updated.items():
            setattr(db_pr, key, value)
        
        await db.commit()
        await db.refresh(db_pr)
        
        return db_pr
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обновлении товара: {str(e)}"
        )

# то же самое для staff
async def delete_product(db: AsyncSession, product_id: int) -> bool:
    try:
        stmt = select(Product).where(Product.product_id == product_id)
        result = await db.execute(stmt)
        db_product = result.scalar_one_or_none()
        
        if db_product:
            await db.delete(db_product)
            await db.commit()
            return True
        return False
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при удалении товара: {str(e)}"
        )
