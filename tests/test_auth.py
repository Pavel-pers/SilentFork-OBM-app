import pytest
from fastapi import HTTPException
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from app.features.auth.service import AuthService
from app.features.auth.schemas import Token, UserLogin
from app.models.user import UserRole


class TestAuthService:
    """Тесты для AuthService"""

    def test_auth_service_initialization(self):
        """Проверяет инициализацию AuthService."""
        service = AuthService()
        assert service is not None
        assert hasattr(service, 'authenticate_user')
        assert hasattr(service, 'verify_token')

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, db):
        """Проверяет успешную аутентификацию пользователя."""
        from app.models.user import User

        user = User.create_with_encryption(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            phone="+7 999 123-45-67",
            password_hash="$2b$12$testhash123",
            role=UserRole.CLIENT
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        service = AuthService()

        with patch('app.features.auth.service.verify_password', return_value=True):
            result = await service.authenticate_user(db, "test@example.com", "password123")
            assert result is not None
            assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, db):
        """Проверяет аутентификацию с неправильным паролем."""
        service = AuthService()
        from app.models.user import User

        user = User.create_with_encryption(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            phone="+7 999 123-45-67",
            password_hash="$2b$12$testhash123",
            role=UserRole.CLIENT
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        with patch('app.features.auth.service.verify_password', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await service.authenticate_user(db, "test@example.com", "wrong_password")

            assert exc_info.value.status_code == 401
            assert "Неверный email или пароль" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, db):
        """Проверяет аутентификацию несуществующего пользователя."""
        service = AuthService()

        with pytest.raises(HTTPException) as exc_info:
            await service.authenticate_user(db, "nonexistent@example.com", "password")

        assert exc_info.value.status_code == 401
        assert "Неверный email или пароль" in str(exc_info.value.detail)

    def test_verify_token_success(self):
        """Проверяет успешную верификацию токена."""
        service = AuthService()

        mock_payload = {"sub": "1", "role": "CLIENT", "email": "test@example.com"}
        with patch('app.features.auth.service.decode_access_token', return_value=mock_payload):
            result = service.verify_token("valid_token")
            assert result == mock_payload

    def test_verify_token_failure(self):
        """Проверяет верификацию невалидного токена."""
        service = AuthService()

        with patch('app.features.auth.service.decode_access_token') as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")

            with pytest.raises(HTTPException) as exc_info:
                service.verify_token("invalid_token")

            assert exc_info.value.status_code == 401
            assert "Неверные учетные данные" in str(exc_info.value.detail)


class TestAuthSchemas:
    """Тесты для схем Pydantic"""

    def test_token_schema_structure(self):
        """Проверяет структуру схемы Token."""
        token = Token(
            access_token="test_token_123",
            token_type="bearer",
            user_id=42,
            role="CLIENT"
        )
        assert token.access_token == "test_token_123"
        assert token.token_type == "bearer"
        assert token.user_id == 42
        assert token.role == "CLIENT"

    def test_user_login_schema_validation(self):
        """Проверяет валидацию схемы UserLogin."""
        login_data = UserLogin(
            email="valid@example.com",
            password="SecurePass123!"
        )
        assert login_data.email == "valid@example.com"
        assert login_data.password == "SecurePass123!"

    def test_user_login_rejects_invalid_email(self):
        """Проверяет что невалидный email вызывает ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UserLogin(email="неправильный-емейл", password="password123")


class TestAuthAPIEndpoints:
    """Тесты для API эндпоинтов"""

    @pytest.mark.asyncio
    async def test_login_json_endpoint_returns_401_for_wrong_credentials(self, client):
        """Проверяет что неправильные учетные данные возвращают 401."""
        with patch('app.features.auth.router.auth_service.authenticate_user') as mock_auth:
            mock_auth.side_effect = HTTPException(status_code=401, detail="Неверный email или пароль")

            response = client.post(
                "/auth/login-json",
                json={"email": "nonexistent@example.com", "password": "wrong"}
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Неверный email или пароль"

    @pytest.mark.asyncio
    async def test_login_json_endpoint_returns_token_for_valid_credentials(self, client):
        """Проверяет что правильные учетные данные возвращают токен."""
        from app.models.user import UserRole

        mock_user = MagicMock()
        mock_user.user_id = 1
        mock_user.email = "success@example.com"
        mock_user.role = UserRole.CLIENT

        with patch('app.features.auth.router.auth_service.authenticate_user') as mock_auth:
            mock_auth.return_value = mock_user

            with patch('app.features.auth.router.create_access_token') as mock_create_token:
                mock_create_token.return_value = "mock_jwt_token"

                response = client.post(
                    "/auth/login-json",
                    json={"email": "success@example.com", "password": "correct"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["access_token"] == "mock_jwt_token"
                assert data["token_type"] == "bearer"
                assert data["user_id"] == 1
                assert data["role"] == "CLIENT"

    @pytest.mark.asyncio
    async def test_login_oauth2_endpoint_works_with_form_data(self, client):
        """Проверяет OAuth2 endpoint с form-data."""
        with patch('app.features.auth.router.auth_service.authenticate_user') as mock_auth:
            mock_auth.side_effect = HTTPException(status_code=401, detail="Неверный email или пароль")

            response = client.post(
                "/auth/login",
                data={"username": "test@example.com", "password": "wrong"}
            )
            assert response.status_code == 401
            assert "Неверный email или пароль" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_verify_token_endpoint_validates_valid_token(self, client):
        """Проверяет endpoint /auth/verify-token с валидным токеном."""
        with patch('app.core.security.decode_access_token') as mock_decode:
            mock_decode.return_value = {"sub": "100", "role": "CLIENT"}

            response = client.post(
                "/auth/verify-token",
                headers={"Authorization": "Bearer valid_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert data["user_id"] == 100
            assert data["role"] == "CLIENT"

    @pytest.mark.asyncio
    async def test_verify_token_endpoint_rejects_invalid_token(self, client):
        """Проверяет endpoint /auth/verify-token с невалидным токеном."""
        with patch('app.core.security.decode_access_token') as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")

            response = client.post(
                "/auth/verify-token",
                headers={"Authorization": "Bearer invalid_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False


class TestRegistrationAPI:
    """Тесты для API регистрации"""
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self):
        """Проверяет что нельзя зарегистрироваться с существующим email."""
        from app.features.auth.router import register
        from app.features.users.schemas import UserCreate
        from app.models.user import User

        mock_session = AsyncMock()

        mock_existing_user = MagicMock(spec=User)
        mock_existing_user.email = "existing@example.com"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing_user
        mock_session.execute.return_value = mock_result

        with patch('app.features.auth.router.select') as mock_select:
            mock_where = MagicMock()
            mock_where.where.return_value = mock_where

            mock_select_obj = MagicMock()
            mock_select_obj.where.return_value = mock_where
            mock_select.return_value = mock_select_obj

            user_data = UserCreate(
                email="existing@example.com",
                first_name="Новый",
                last_name="Пользователь",
                phone="+7 999 222-33-44",
                password="TestPassword123",
                password_confirm="TestPassword123"
            )

            with patch('app.features.auth.router.hash_password') as mock_hash:
                mock_hash.return_value = "$2b$12$hashedpassword"

                with pytest.raises(HTTPException) as exc_info:
                    await register(user_data, mock_session)

                assert exc_info.value.status_code == 400
                assert "уже существует" in str(exc_info.value.detail)

                mock_session.add.assert_not_called()
                mock_session.commit.assert_not_called()


class TestPasswordSecurity:
    """Тесты для безопасности паролей"""

    def test_password_hashing_and_verification(self):
        """Проверяет хеширование и проверку паролей."""
        from app.core.security import hash_password, verify_password

        password = "MySecurePassword123!"
        result_hash = hash_password(password)

        assert result_hash != password
        assert verify_password(password, result_hash) is True
        assert verify_password("wrong-password", result_hash) is False


@pytest.mark.asyncio
class TestAuthIntegration:
    """Интеграционные тесты аутентификации"""

    async def test_create_and_find_user(self, db):
        """Проверяет создание пользователя и поиск по email."""
        from app.models.user import User
        from sqlalchemy import select
        from app.core.encryption import encryption_service

        test_email = "integration_test@example.com"
        user = User.create_with_encryption(
            first_name="Интеграция",
            last_name="Тест",
            phone="+7 777 777-77-77",
            email=test_email,
            password_hash="$2b$12$testhash",
            role=UserRole.CLIENT
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        stmt = select(User).where(User.email_hash == encryption_service.hash_email(test_email))
        result = await db.execute(stmt)
        found_user = result.scalar_one_or_none()

        assert found_user is not None
        assert found_user.email == test_email
        return user

    async def test_user_not_found(self, db):
        """Проверяет что поиск несуществующего пользователя возвращает None."""
        from sqlalchemy import select
        from app.models.user import User
        from app.core.encryption import encryption_service

        stmt = select(User).where(User.email_hash == encryption_service.hash_email("nonexistent@example.com"))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        assert user is None


def test_error_messages_in_russian():
    """Проверяет что сообщения об ошибках на русском языке."""
    service = AuthService()

    with patch('app.features.auth.service.decode_access_token') as mock_decode:
        mock_decode.side_effect = Exception("Invalid token")

        try:
            service.verify_token("invalid")
        except HTTPException as e:
            assert e.status_code == 401
            assert "Неверные учетные данные" in str(e.detail)
