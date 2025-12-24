# Изменения: SMTP‑уведомления + рефакторинг CSS

Документ описывает изменения, которые были внесены после реализации staff‑панели:
1) добавлены email‑уведомления через SMTP (подтверждение заказа, уведомление staff о новом заказе, уведомление о смене пароля);
2) приведены в порядок стили: большой `styles.css` разделён на несколько логических файлов и исправлена проблема с отсутствующим `bootstrap.min.css`;
3) выполнена повторная проверка в Docker: сервис поднимается, страницы рендерятся, ключевые флоу работают.

---

## 0) Ссылки на изменённые/добавленные файлы

### SMTP / уведомления
- [`../app/infra/email.py`](../app/infra/email.py) — основной модуль SMTP‑отправки (функции `send_email`, `send_order_confirmation` и т.д.)
- [`../app/features/orders/form_router.py`](../app/features/orders/form_router.py) — отправка письма после оформления заказа (через `BackgroundTasks`)
- [`../app/features/users/router.py`](../app/features/users/router.py) — уведомление о смене пароля (через `BackgroundTasks`)
- [`../web/templates/orders/success.html`](../web/templates/orders/success.html) — корректный текст на странице успеха с учётом `smtp_enabled`

### CSS
- [`../web/static/css/styles.css`](../web/static/css/styles.css) — теперь “агрегатор” (только `@import`)
- [`../web/static/css/base.css`](../web/static/css/base.css) — базовые стили/типографика
- [`../web/static/css/layout.css`](../web/static/css/layout.css) — header/footer/layout
- [`../web/static/css/forms.css`](../web/static/css/forms.css) — формы, инпуты, алерты
- [`../web/static/css/components.css`](../web/static/css/components.css) — кнопки/таблицы
- [`../web/static/css/catalog.css`](../web/static/css/catalog.css) — каталог/карточки товаров
- [`../web/static/css/orders.css`](../web/static/css/orders.css) — оформление заказа/суммарная инфа
- [`../web/static/css/bootstrap.min.css`](../web/static/css/bootstrap.min.css) — добавлен локальный bootstrap (раньше ссылка в шаблоне была, файла не было)

---

## 1) SMTP‑уведомления

### 1.1 Конфигурация в `.env`
Используются уже существующие настройки из `Settings` (`app/core/settings.py`):
- `SMTP_HOST`
- `SMTP_PORT` (по умолчанию 587)
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

Логика отправки сделана так, чтобы **при пустом `SMTP_HOST` сайт продолжал работать** (уведомления просто пропускаются).

---

## 2) Модуль отправки почты: `app/infra/email.py`

Файл: [`../app/infra/email.py`](../app/infra/email.py)

### 2.1 `smtp_enabled()` — “флаг включённости”
Секция (примерно строки 14–16):
```py
def smtp_enabled() -> bool:
    return bool(settings.SMTP_HOST)
```

Смысл:
- если `SMTP_HOST` пустой (как в вашем `.env` по умолчанию), мы считаем SMTP “выключенным”;
- это позволяет не пытаться подключаться к SMTP и не падать на пользовательских сценариях.

---

### 2.2 `_build_message(...)` — сборка письма
Секция (примерно строки 18–27):
```py
def _build_message(to_email: str, subject: str, text: str, html: Optional[str] = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg
```

Почему вынесено:
- чтобы `send_email(...)` не раздувался и не повторял заполнение заголовков;
- чтобы можно было легко расширить письмо HTML‑версией (сейчас параметр поддерживается, но мы используем текстовый вариант).

---

### 2.3 `send_email(...)` — единая точка отправки
Секция (примерно строки 29–67):
```py
def send_email(to_email: str, subject: str, text: str, html: Optional[str] = None) -> bool:
    if not smtp_enabled():
        log.info("SMTP не настроен, пропуск отправки письма: to=%s subject=%s", to_email, subject)
        return False
    ...
    try:
        if port == 465:
            with smtplib.SMTP_SSL(...):
                ...
        with smtplib.SMTP(...):
            s.starttls(...)
            ...
        return True
    except Exception:
        log.exception("Ошибка отправки письма: to=%s subject=%s", to_email, subject)
        return False
```

Ключевые решения:
1) **Fail‑safe поведение**: любая ошибка SMTP логируется и возвращает `False`, но не ломает оформление заказа/смену пароля.
2) **TLS/SSL режим**:
   - если порт `465` → используем `SMTP_SSL` (SSL‑соединение сразу);
   - иначе → используем `SMTP + STARTTLS` (типично для 587).
3) **Аутентификация** выполняется только если заданы `SMTP_USER` и `SMTP_PASSWORD`.
4) Добавлен таймаут `SMTP_TIMEOUT_SECONDS = 10`, чтобы “подвисший SMTP” не зависал надолго (это важно даже при `BackgroundTasks`).

---

### 2.4 Специализированные уведомления

#### 2.4.1 Подтверждение заказа клиенту
Функция: `send_order_confirmation(...)` (примерно строки 69–87):
```py
subject = f"Подтверждение заказа №{order_id}"
...
return send_email(to_email, subject, "\n".join(lines))
```

Мы отправляем:
- номер заказа;
- сумму и адрес (если переданы);
- “если вы не оформляли заказ — проигнорируйте”.

#### 2.4.2 Уведомление staff о новом заказе
Функция: `send_staff_new_order_notification(...)` (примерно строки 89–96).
Смысл: простое короткое письмо “поступил новый заказ №...”.

#### 2.4.3 Уведомление о смене пароля
Функция: `send_password_changed_notification(...)` (примерно строки 98–104).
Смысл: базовая security‑практика — уведомлять пользователя, что пароль изменился.

---

## 3) Интеграция SMTP в оформление заказа

Файл: [`../app/features/orders/form_router.py`](../app/features/orders/form_router.py)

### 3.1 Почему используется `BackgroundTasks`
Отправка email через `smtplib` — это сеть/IO и может занимать секунды.
Если делать это “в лоб” внутри запроса, пользователь будет ждать редирект на `/orders/success/...`.

Поэтому письмо отправляется как background‑задача:
- UI получает ответ/редирект сразу;
- письмо отправляется уже после ответа.

Starlette/FastAPI выполнит синхронную background‑функцию безопасно после ответа (под капотом — через threadpool).

---

### 3.2 Где добавлена отправка письма клиенту
Секция `POST /orders/checkout` (примерно строки 25–60), ключевой фрагмент:
```py
background_tasks.add_task(
    send_order_confirmation,
    to_email=order.order_email,
    order_id=order.order_id,
    total_price=str(order.total_price),
    address=order.address,
)
```

Почему берём `order.order_email` и `order.address` из модели:
- они хранятся в БД зашифрованно, но свойства `Order.order_email` и `Order.address` возвращают расшифрованное значение;
- в письмо должна уходить “читаемая” информация.

---

### 3.3 Уведомление staff о новом заказе (опционально)
Там же в `POST /orders/checkout`:
```py
if smtp_enabled():
    staff_stmt = select(User).where(User.role == UserRole.STAFF)
    ...
    for staff_user in staff_users:
        staff_email = getattr(staff_user, "email", None)
        if staff_email:
            background_tasks.add_task(send_staff_new_order_notification, staff_email, order.order_id)
```

Почему делаем `if smtp_enabled()`:
- если SMTP не настроен, нет смысла ходить в БД за staff‑email’ами (лишняя нагрузка);
- при пустом `SMTP_HOST` всё равно письма бы не ушли.

Почему `getattr(staff_user, "email", None)`:
- `User.email` — свойство (decrypt), оно может вернуть `None` если расшифровка не удалась;
- `getattr` позволяет безопасно обработать, даже если структура модели изменится.

---

### 3.4 Корректный редирект (и запуск background‑задач)
Возврат ответа сделан так:
```py
return RedirectResponse(
    url=f"/orders/success/{order.order_id}",
    status_code=303,
    background=background_tasks
)
```
Суть: background‑задачи прикрепляются именно к ответу.

---

## 4) Интеграция SMTP в смену пароля

Файл: [`../app/features/users/router.py`](../app/features/users/router.py)

В `POST /profile/change-password` добавлен параметр `background_tasks` и постановка задачи после успешного `commit()`:

```py
await db.commit()
await db.refresh(current_user)

if current_user.email:
    background_tasks.add_task(send_password_changed_notification, current_user.email)
```

Почему после `commit()`:
- уведомление должно уходить только если пароль действительно изменился в БД;
- если commit упадёт, письмо отправлять нельзя.

Почему background:
- отправка почты не должна тормозить ответ пользователю (редирект/JSON).

---

## 5) UI‑правка: страница успеха заказа не “врет” без SMTP

Файл: [`../web/templates/orders/success.html`](../web/templates/orders/success.html)

Раньше шаблон всегда писал “Письмо отправлено”, даже если SMTP не настроен.
Теперь:
```jinja2
{% if smtp_enabled %}
  Письмо ... отправлено на {{ order_email }}
{% else %}
  SMTP не настроен — письмо не отправлено. Email заказа: {{ order_email }}
{% endif %}
```

Данные `smtp_enabled` передаются из backend (см. `success_page` в [`../app/features/orders/form_router.py`](../app/features/orders/form_router.py)).

---

## 6) Рефакторинг CSS: деление `styles.css` на логические части

### 6.1 Проблема исходного состояния
`web/static/css/styles.css` был большим (≈400+ строк) и содержал:
- дубли `main.container`, `.form-group`, `.product-card` и т.п.;
- разнородные блоки (layout, формы, каталог, заказы) в одном файле;
- местами `!important` и конфликтующие определения (например, `.form-group input` с разными `border-radius`).

Кроме того, в `base.html` подключался `bootstrap.min.css`, но файла в `web/static/css/` не было, из‑за чего страница могла отдавать 404 по CSS.

---

### 6.2 Что сделано
1) `styles.css` превращён в “агрегатор” с `@import`:
   - файл: [`../web/static/css/styles.css`](../web/static/css/styles.css)
   - содержит только:
     ```css
     @import "base.css";
     @import "layout.css";
     ...
     ```
2) Вынесены логические блоки в отдельные файлы:
   - [`../web/static/css/base.css`](../web/static/css/base.css) — типографика, базовые размеры, `main.container`
   - [`../web/static/css/layout.css`](../web/static/css/layout.css) — `.header`, `.footer`, `.page-wrapper`
   - [`../web/static/css/forms.css`](../web/static/css/forms.css) — `.form-container`, `.form-group`, `.alert` и т.д.
   - [`../web/static/css/components.css`](../web/static/css/components.css) — `.btn-custom`, `.table`
   - [`../web/static/css/catalog.css`](../web/static/css/catalog.css) — карточки каталога
   - [`../web/static/css/orders.css`](../web/static/css/orders.css) — блоки оформления заказа
3) Добавлен файл [`../web/static/css/bootstrap.min.css`](../web/static/css/bootstrap.min.css), чтобы ссылка из `base.html` перестала быть “битой”.

---

### 6.3 Почему выбран подход с `@import`
Плюсы в рамках учебного/небольшого проекта:
- `base.html` не надо менять: он как подключал один `styles.css`, так и подключает;
- файлы теперь логически разделены, проще поддерживать.

Минусы (важно понимать):
- `@import` может влиять на скорость загрузки (браузер грузит последовательно).
Для текущего проекта это приемлемо; если понадобится оптимизация — можно собрать всё в один файл на этапе сборки.

---

## 7) Проверка работоспособности в Docker (что именно проверялось)

Я повторно проверил сервис в Docker (у вас это `db` + `web`):
1) контейнеры `docker compose ps` в статусе `Up`;
2) `GET /health` → `200` и JSON `{"status":"ok"}`;
3) `GET /products/catalog` → `200`, HTML отдается корректно;
4) проверка статики:
   - `GET /static/css/styles.css` → `200`
   - `GET /static/css/base.css`/`layout.css`/`forms.css`/`components.css`/`catalog.css`/`orders.css` → `200`
   - `GET /static/css/bootstrap.min.css` → `200`
5) staff‑флоу:
   - логин staff → `303 Location: /staff`
   - `GET /staff` → `200`, страница рендерится
6) client‑флоу заказа:
   - логин клиента → добавление в корзину → `POST /orders/checkout` → `303 Location: /orders/success/{id}`
   - `GET /orders/success/{id}` → `200`, текст про SMTP соответствует настройкам (если `SMTP_HOST` пустой — пишет, что SMTP не настроен).

---

## 8) Как включить реальную отправку писем
Нужно заполнить SMTP‑поля в `.env`, затем перезапустить `web`:
- `SMTP_HOST` (например, smtp сервер провайдера)
- `SMTP_PORT` (587 для STARTTLS, 465 для SSL)
- `SMTP_USER` / `SMTP_PASSWORD`
- `SMTP_FROM`

После этого:
- при оформлении заказа клиенту уйдёт подтверждение;
- всем staff‑пользователям уйдет уведомление о новом заказе;
- при смене пароля пользователю уйдёт security‑уведомление.

