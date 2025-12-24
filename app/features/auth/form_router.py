from fastapi import APIRouter, Request, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import HTMLResponse, RedirectResponse
from app.infra.templates import templates
from app.infra.db import get_db
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["authentication-forms"])


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/register/redirect", response_class=RedirectResponse)
async def register_redirect(
        request: Request,
        email: str = Form(),
        first_name: str = Form(),
        last_name: str = Form(),
        patronymic: str = Form(None),
        phone: str = Form(None),
        password: str = Form(),
        password_confirm: str = Form(),
        role: str = Form("CLIENT"),
        db: AsyncSession = Depends(get_db)
):
    try:
        from app.features.auth.router import register_from_form_data

        user_profile = await register_from_form_data(
            email=email,
            first_name=first_name,
            last_name=last_name,
            patronymic=patronymic,
            phone=phone,
            password=password,
            password_confirm=password_confirm,
            role=role,
            db=db
        )

        access_token = create_access_token(
            user_id=user_profile.user_id,
            role=user_profile.role,
            expires_minutes=120
        )

        response = RedirectResponse(
            url="/products/catalog",
            status_code=303
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=120 * 60,
            samesite="lax"
        )
        return response

    except Exception as e:
        error_msg = str(getattr(e, 'detail', 'Ошибка при регистрации'))
        return RedirectResponse(
            url=f"/auth/register?error={error_msg}"
                f"&email={email}"
                f"&first_name={first_name}"
                f"&last_name={last_name}"
                f"&patronymic={patronymic or ''}"
                f"&phone={phone or ''}",
            status_code=303
        )


@router.post("/login/redirect", response_class=RedirectResponse)
async def login_redirect(
        email: str = Form(),
        password: str = Form(),
        db: AsyncSession = Depends(get_db)
):
    try:
        from app.features.auth.router import login_json
        from app.features.auth.schemas import UserLogin

        login_data = UserLogin(email=email, password=password)
        token_data = await login_json(login_data, db)

        target_url = "/staff" if token_data.role == "STAFF" else "/products/catalog"

        response = RedirectResponse(
            url=target_url,
            status_code=303
        )
        response.set_cookie(
            key="access_token",
            value=token_data.access_token,
            httponly=True,
            max_age=120 * 60,
            samesite="lax",
            path="/"
        )
        return response

    except Exception as e:
        error_msg = str(getattr(e, 'detail', 'Ошибка при входе'))
        return RedirectResponse(
            url=f"/auth/login?error={error_msg}",
            status_code=303
        )
