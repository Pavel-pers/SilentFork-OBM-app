from fastapi import APIRouter, BackgroundTasks, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.infra.templates import templates
from app.infra.db import get_db
from app.features.orders.service import create_simple_order
from app.models.user import User, UserRole
from app.features.auth.dependencies import get_optional_user
from sqlalchemy import select
from app.models.order import Order
import logging
from app.infra.email import send_order_confirmation, send_staff_new_order_notification, smtp_enabled

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(
        request: Request,
        user: User | None = Depends(get_optional_user),
):
    return templates.TemplateResponse("cart/confirmation.html", {"request": request, "user": user})


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

        background_tasks.add_task(
            send_order_confirmation,
            to_email=order.order_email,
            order_id=order.order_id,
            total_price=str(order.total_price),
            address=order.address,
        )

        # Дополнительно: уведомляем всех staff-пользователей о новом заказе.
        # Если SMTP не настроен — пропускаем, чтобы лишний раз не дергать БД.
        if smtp_enabled():
            staff_stmt = select(User).where(User.role == UserRole.STAFF)
            staff_res = await db.execute(staff_stmt)
            staff_users = staff_res.scalars().all()
            for staff_user in staff_users:
                staff_email = getattr(staff_user, "email", None)
                if staff_email:
                    background_tasks.add_task(send_staff_new_order_notification, staff_email, order.order_id)

        return RedirectResponse(
            url=f"/orders/success/{order.order_id}",
            status_code=303,
            background=background_tasks
        )
    except Exception as error:
        logging.error("Ошибка при оформлении заказа: %s", error)
        return RedirectResponse(url=f"/orders/checkout?error={str(error)}", status_code=303)


@router.get("/success/{order_id}", response_class=HTMLResponse)
async def success_page(request: Request, order_id: int, user: User | None = Depends(get_optional_user),
                       db: AsyncSession = Depends(get_db)):
    stmt = select(Order).where(Order.order_id == order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    return templates.TemplateResponse("orders/success.html", {"request": request, "order_id": order_id,
                                                              "order_email": order.order_email, "user": user,
                                                              "smtp_enabled": smtp_enabled()})
