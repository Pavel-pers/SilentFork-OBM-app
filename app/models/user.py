from __future__ import annotations
import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.ext.hybrid import hybrid_property, Comparator
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.cart import Cart
    from app.models.order import Order


class UserRole(str, enum.Enum):
    CLIENT = "CLIENT"
    STAFF = "STAFF"


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.CLIENT)

    encrypted_first_name: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_patronymic: Mapped[Optional[str]] = mapped_column(Text)
    encrypted_last_name: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_phone: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    orders: Mapped[list[Order]] = relationship(back_populates="user")
    cart: Mapped[Cart | None] = relationship(back_populates="user", uselist=False)

    @hybrid_property
    def first_name(self) -> str:
        """Расшифрованное имя"""
        from app.core.encryption import encryption_service
        return encryption_service.decrypt(self.encrypted_first_name)

    @first_name.setter
    def first_name(self, value: str) -> None:
        from app.core.encryption import encryption_service
        self.encrypted_first_name = encryption_service.encrypt(value)

    @hybrid_property
    def patronymic(self) -> Optional[str]:
        """Расшифрованное отчество"""
        if not self.encrypted_patronymic:
            return None
        from app.core.encryption import encryption_service
        return encryption_service.decrypt(self.encrypted_patronymic)

    @patronymic.setter
    def patronymic(self, value: Optional[str]) -> None:
        from app.core.encryption import encryption_service
        self.encrypted_patronymic = encryption_service.encrypt(value) if value else None

    @hybrid_property
    def last_name(self) -> str:
        """Расшифрованная фамилия"""
        from app.core.encryption import encryption_service
        return encryption_service.decrypt(self.encrypted_last_name)

    @last_name.setter
    def last_name(self, value: str) -> None:
        from app.core.encryption import encryption_service
        self.encrypted_last_name = encryption_service.encrypt(value)

    @hybrid_property
    def phone(self) -> str:
        """Расшифрованный телефон"""
        from app.core.encryption import encryption_service
        return encryption_service.decrypt(self.encrypted_phone)

    @phone.setter
    def phone(self, value: str) -> None:
        from app.core.encryption import encryption_service
        self.encrypted_phone = encryption_service.encrypt(value)

    @hybrid_property
    def email(self) -> str:
        """Расшифрованный email"""
        from app.core.encryption import encryption_service
        return encryption_service.decrypt(self.encrypted_email)

    @email.setter
    def email(self, value: str) -> None:
        from app.core.encryption import encryption_service
        self.encrypted_email = encryption_service.encrypt(value)
        self.email_hash = encryption_service.hash_email(value)

    @email.comparator
    def email(cls):
        from app.core.encryption import encryption_service

        class EmailComparator(Comparator):
            def __eq__(self, other):
                return cls.email_hash == encryption_service.hash_email(other)

        return EmailComparator(cls.email_hash)

    @classmethod
    def create_with_encryption(
            cls,
            first_name: str,
            last_name: str,
            phone: str,
            email: str,
            password_hash: str,
            patronymic: Optional[str] = None,
            role: UserRole = UserRole.CLIENT
    ) -> User:
        """Создает пользователя с автоматическим шифрованием данных"""
        from app.core.encryption import encryption_service

        return cls(
            encrypted_first_name=encryption_service.encrypt(first_name),
            encrypted_last_name=encryption_service.encrypt(last_name),
            encrypted_phone=encryption_service.encrypt(phone),
            encrypted_email=encryption_service.encrypt(email),
            encrypted_patronymic=encryption_service.encrypt(patronymic) if patronymic else None,
            email_hash=encryption_service.hash_email(email),
            password_hash=password_hash,
            role=role
        )

    def update_encrypted_data(
            self,
            first_name: Optional[str] = None,
            last_name: Optional[str] = None,
            phone: Optional[str] = None,
            email: Optional[str] = None,
            patronymic: Optional[str] = None
    ) -> None:
        """Обновляет зашифрованные данные"""
        from app.core.encryption import encryption_service

        if first_name is not None:
            self.encrypted_first_name = encryption_service.encrypt(first_name)

        if last_name is not None:
            self.encrypted_last_name = encryption_service.encrypt(last_name)

        if phone is not None:
            self.encrypted_phone = encryption_service.encrypt(phone)

        if email is not None:
            self.encrypted_email = encryption_service.encrypt(email)
            self.email_hash = encryption_service.hash_email(email)

        if patronymic is not None:
            self.encrypted_patronymic = encryption_service.encrypt(patronymic) if patronymic else None
