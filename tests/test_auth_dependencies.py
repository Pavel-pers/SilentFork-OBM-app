import pytest
from fastapi import HTTPException
from unittest.mock import patch

from app.features.auth.dependencies import get_current_user


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db):
    with patch("app.features.auth.dependencies.decode_access_token", side_effect=ValueError):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(access_token="bad", db=db)
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_user_not_found(db):
    with patch("app.features.auth.dependencies.decode_access_token", return_value={"sub": "999"}):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(access_token="token", db=db)
        assert exc.value.status_code == 401
        assert "Пользователь не найден" in str(exc.value.detail)
