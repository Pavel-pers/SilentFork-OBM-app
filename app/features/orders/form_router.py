from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import get_optional_user
from app.features.orders.service import create_simple_order
from app.infra.db import get_db
from app.infra.email import is_smtp_configured, send_order_confirmation
from app.infra.templates import templates
from app.models.order import Order
from app.models.user import User

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request, user: User | None = Depends(get_optional_user),
                        db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse(request, "cart/confirmation.html", {"user": user})


@router.post("/checkout", response_class=RedirectResponse)
async def checkout_form(
        background_tasks: BackgroundTasks,
        order_email: str = Form(),
        phone: str = Form(None),
        address: str = Form(),
        db: AsyncSession = Depends(get_db),
        user: User | None = Depends(get_optional_user)
):
    try:
        order = await create_simple_order(db, order_email, phone, address, user)
        email_configured = is_smtp_configured()
        if email_configured:
            background_tasks.add_task(send_order_confirmation, order_email, order.order_id, address, phone)
        return RedirectResponse(
            url=f"/orders/success/{order.order_id}?email={'1' if email_configured else '0'}",
            status_code=303
        )
    except Exception as error:  # noqa: BLE001
        return RedirectResponse(url=f"/orders/checkout?error={str(error)}", status_code=303)


@router.get("/success/{order_id}", response_class=HTMLResponse)
async def success_page(request: Request, order_id: int, user: User | None = Depends(get_optional_user),
                       db: AsyncSession = Depends(get_db)):
    stmt = select(Order).where(Order.order_id == order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    email_scheduled = request.query_params.get("email", "0") == "1"
    return templates.TemplateResponse(
        request,
        "orders/success.html",
        {
            "order_id": order_id,
            "order_email": order.order_email,
            "user": user,
            "email_scheduled": email_scheduled,
            "smtp_configured": is_smtp_configured(),
        },
    )
