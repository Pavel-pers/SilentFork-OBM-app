from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.order_item import OrderItem
    from app.models.user import User


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)

    encrypted_order_email: Mapped[str] = mapped_column(String(255), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    encrypted_address: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order", cascade="all, delete-orphan")

    @property
    def order_email(self) -> str:
        """Расшифрованный email"""
        from app.core.encryption import encryption_service
        return encryption_service.decrypt(self.encrypted_order_email)

    @property
    def address(self) -> str:
        """Расшифрованный адрес доставки"""
        from app.core.encryption import encryption_service
        return encryption_service.decrypt(self.encrypted_address)

    @classmethod
    def create_with_encryption(
            cls,
            user_id: int,
            order_email: str,
            total_price: Decimal,
            address: str
    ) -> Order:
        """Создает пользователя с автоматическим шифрованием данных"""
        from app.core.encryption import encryption_service

        return cls(
            user_id=user_id,
            encrypted_order_email=encryption_service.encrypt(order_email),
            total_price=total_price,
            encrypted_address=encryption_service.encrypt(address)
        )
