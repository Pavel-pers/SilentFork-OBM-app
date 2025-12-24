from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from app.core.security import verify_password, decode_access_token
from app.core.encryption import encryption_service
from app.models.user import User

class AuthService:
    def __str__(self) -> str:
        return f"<AuthService>"

    async def authenticate_user(
            self,
            db: AsyncSession,
            email: str,
            password: str
    ):
        email_hash = encryption_service.hash_email(email)
        result = await db.execute(select(User).where(User.email_hash == email_hash))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль"
            )

        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль"
            )

        return user

    def verify_token(self, token: str) -> dict:
        try:
            return decode_access_token(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные"
            )

auth_service = AuthService()
