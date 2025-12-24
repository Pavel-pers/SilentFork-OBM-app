from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Form
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.responses import HTMLResponse, RedirectResponse
from app.infra.templates import templates
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import traceback

from app.features.auth.dependencies import (
    get_current_active_user,
    get_current_staff
)
from app.features.users.schemas import (
    UserProfile,
    UserUpdate,
    UserPublic,
    ChangePasswordRequest,
    UserCreate
)
from app.core.security import hash_password, verify_password
from app.infra.db import get_db
from app.models.user import User, UserRole

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/", response_class=HTMLResponse)
async def profile_page(
        request: Request,
        current_user: User = Depends(get_current_active_user)
):
    return templates.TemplateResponse(
        request,
        "users/profile.html",
        {
            "user": current_user
        }
    )


@router.get("/change_password", response_class=HTMLResponse)
async def change_password_page(
        request: Request,
        current_user: User = Depends(get_current_active_user),
        error: Optional[str] = None,
        message: Optional[str] = None
):
    return templates.TemplateResponse(
        request,
        "users/change_password.html",  # создайте этот файл в templates/
        {
            "user": current_user,
            "error": error,
            "message": message
        }
    )


@router.post("/change-password")
async def change_my_password(
        request: Request,
        password_data: Optional[ChangePasswordRequest] = None,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
        current_password: Optional[str] = Form(None),
        new_password: Optional[str] = Form(None),
        confirm_password: Optional[str] = Form(None)
):
    """
    Эндпоинт для смены пароля.
    Поддерживает как JSON API, так и HTML формы.
    """
    try:
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type and password_data:
            current_pass = password_data.current_password
            new_pass = password_data.new_password
            confirm_pass = new_pass
            is_api_request = True
        else:
            if not all([current_password, new_password, confirm_password]):
                return RedirectResponse(
                    f"/profile/change_password?error=Все поля обязательны для заполнения",
                    status_code=303
                )

            current_pass = current_password
            new_pass = new_password
            confirm_pass = confirm_password
            is_api_request = False
            if new_pass != confirm_pass:
                return RedirectResponse(
                    f"/profile/change_password?error=Новый пароль и подтверждение не совпадают",
                    status_code=303
                )

        if not verify_password(current_pass, current_user.password_hash):
            if is_api_request:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный текущий пароль"
                )
            else:
                return RedirectResponse(
                    f"/profile/change_password?error=Неверный текущий пароль",
                    status_code=303
                )

        if verify_password(new_pass, current_user.password_hash):
            if is_api_request:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Новый пароль не должен совпадать с текущим"
                )
            else:
                return RedirectResponse(
                    f"/profile/change_password?error=Новый пароль не должен совпадать с текущим",
                    status_code=303
                )

        try:
            UserCreate.validate_password(new_pass)
        except ValueError as e:
            if is_api_request:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
            else:
                return RedirectResponse(
                    f"/profile/change_password?error={str(e)}",
                    status_code=303
                )

        current_user.password_hash = hash_password(new_pass)

        await db.commit()
        await db.refresh(current_user)

        if is_api_request:
            return {"message": "Пароль успешно изменен"}
        else:
            return RedirectResponse(
                f"/profile/change_password?message=Пароль успешно изменен",
                status_code=303
            )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"ERROR changing password for user {current_user.user_id}: {str(e)}")
        traceback.print_exc()

        if is_api_request:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Произошла ошибка при изменении пароля"
            )
        else:
            return RedirectResponse(
                f"/profile/change_password?error=Произошла ошибка при изменении пароля",
                status_code=303
            )


@router.get("/me/api", response_model=UserProfile)
async def get_my_profile_api(
        current_user: User = Depends(get_current_active_user)
):
    return current_user


@router.put("/me", response_model=UserProfile)
async def update_my_profile(
        update_data: UserUpdate,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
):
    try:
        print(f"DEBUG: Starting profile update for user_id={current_user.user_id}")
        print(f"DEBUG: Update data: {update_data}")

        update_dict = update_data.model_dump(exclude_unset=True)
        print(f"DEBUG: Update dict: {update_dict}")

        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нет данных для обновления"
            )

        updated_fields = []
        for key, value in update_dict.items():
            print(f"DEBUG: Setting {key} = {value}")
            if hasattr(current_user, key):
                old_value = getattr(current_user, key)
                setattr(current_user, key, value)
                updated_fields.append(f"{key}: {old_value} -> {value}")
            else:
                print(f"WARNING: User object has no attribute {key}")

        print(f"DEBUG: Fields changed: {updated_fields}")

        await db.commit()

        await db.refresh(current_user)

        return current_user

    except HTTPException:
        raise

    except ValidationError as e:
        await db.rollback()
        print(f"VALIDATION ERROR: {e.errors()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка валидации: {e.errors()}"
        )

    except IntegrityError as e:
        await db.rollback()
        print(f"INTEGRITY ERROR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка целостности данных (возможно, email уже занят)"
        )

    except SQLAlchemyError as e:
        await db.rollback()
        print(f"SQLALCHEMY ERROR: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка базы данных: {str(e)}"
        )

    except Exception as e:
        await db.rollback()
        print(f"UNEXPECTED ERROR: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Неожиданная ошибка: {type(e).__name__}"
        )


@router.get("/users", response_model=List[UserPublic])
async def get_all_users(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User)
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return users


@router.get("/logout", response_class=HTMLResponse)
async def logout(
        request: Request,
        response: RedirectResponse
):
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="token_type")
    return response


@router.post("/logout", response_class=HTMLResponse)
async def logout_post(
        request: Request,
        response: RedirectResponse
):
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="token_type")
    return response


# скорее всего не будем верстать
# @router.put("/me", response_model=UserProfile)
# async def update_my_profile(
#         update_data: UserUpdate,
#         current_user: User = Depends(get_current_active_user),
#         db: AsyncSession = Depends(get_db)
# ):
#     update_dict = update_data.dict(exclude_unset=True)
#     for key, value in update_dict.items():
#         setattr(current_user, key, value)
#
#     try:
#         await db.commit()
#         await db.refresh(current_user)
#         return current_user
#     except Exception as e:
#         await db.rollback()
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Ошибка при обновлении профиля: {str(e)}"
#         )


# для отладки, смотреть список юзера по айди
@router.get("/users/{user_id}", response_model=UserProfile)
async def get_user_by_id(
        user_id: int,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
):
    if current_user.role != UserRole.STAFF and current_user.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для просмотра этого профиля"
        )

    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    return user
