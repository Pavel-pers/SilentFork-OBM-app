# Изменения: панель работника (роль `STAFF`) — максимально подробное описание

Этот документ описывает все изменения, которые были внесены для реализации “интереса работника” (роль `STAFF`):
- после **авторизации** `STAFF` пользователь попадает на панель управления;
- на панели есть 3 действия: **изменить сток**, **добавить товар (с фото)**, **посмотреть таблицу товаров без корзины**;
- функционал клиента (`CLIENT`) не менялся по логике (изменения изолированы на уровне staff-роутов и шаблонов).

---

## 0) Кратко: что появилось

### Новые страницы / URL
- `GET /staff` — панель управления (3 кнопки)
- `GET /staff/products` — таблица товаров (без корзины)
- `GET /staff/products/stock` — форма изменения стока
- `POST /staff/products/stock` — применить приход/расход + дельта
- `GET /staff/products/new` — форма добавления товара
- `POST /staff/products/new` — создать товар + (опционально) сохранить фото

### Измененный URL
- `POST /auth/login/redirect` — теперь, если роль `STAFF`, редирект на `/staff` (для `CLIENT` — как раньше `/products/catalog`)

---

## 1) Список файлов, которые были изменены/добавлены

### Изменены
- `app/main.py` — подключен staff-роутер через `app.include_router(...)`
- `app/features/auth/form_router.py` — добавлена логика редиректа после логина по роли
- `app/features/staff/router.py` — полностью реализован staff-функционал (handlers + загрузка фото + изменение стока)
- `web/templates/header.html` — ссылка “Панель” для staff-пользователя

### Добавлены
- `web/templates/staff/dashboard.html` — панель работника (3 ссылки)
- `web/templates/staff/stock.html` — страница/форма изменения стока + сообщения
- `web/templates/staff/add_product.html` — форма добавления товара (multipart) + сообщения
- `web/templates/staff/products.html` — таблица товаров без кнопок корзины

---

## 2) Подключение staff-роутов в приложение

### Зачем это нужно
В FastAPI роуты “существуют” только если их зарегистрировать через `app.include_router(...)`.
До изменения `app/main.py` вы могли написать `app/features/staff/router.py`, но `/staff` все равно возвращал бы `404 Not Found`, потому что роутер не был включен в приложение.

### Что сделано
Файл: `app/main.py` — добавлен импорт и регистрация:

```py
from app.features.staff.router import router as staff_router
...
app.include_router(staff_router)
```

### Почему именно так
Проект уже использует схему “каждая фича — отдельный роутер” (auth/users/products/cart/orders), и staff подключается аналогично, без изобретения новой архитектуры.

---

## 3) Редирект после логина: `STAFF` → `/staff`

### Где происходит логин через HTML-форму
В проекте есть два логина:
- API логин (`/auth/login` и `/auth/login-json`) — возвращают JSON токен;
- HTML-логин (`POST /auth/login/redirect`) — принимает форму, получает токен и ставит cookie, после чего делает редирект.

Требование из задачи относится именно к “авторизации” как к пользовательскому действию в UI, т.е. к `POST /auth/login/redirect`.

### Что изменено
Файл: `app/features/auth/form_router.py` (endpoint `login_redirect`).
После вызова:
```py
token_data = await login_json(login_data, db)
```
я добавил выбор URL на основании роли:
```py
target_url = "/staff" if token_data.role == "STAFF" else "/products/catalog"
response = RedirectResponse(url=target_url, status_code=303)
```

### Почему это корректно
- `login_json` возвращает `Token`, где уже есть `role`, то есть **нам не нужен второй запрос** в БД за ролью.
- Для клиентов (`CLIENT`) поведение сохранено (редирект в каталог), то есть клиентские сценарии не ломаются.

### Что я сознательно НЕ менял
`POST /auth/register/redirect` (форма регистрации) по-прежнему ведет в каталог. В ТЗ было “при авторизации”, т.е. про логин. Если нужно — можно отдельно добавить аналогичный редирект после регистрации staff-аккаунта, но это отдельное UX-решение.

---

## 4) Ссылка на панель в шапке (видна только для `STAFF`)

### Где находится шапка
Шапка подключается в `web/templates/base.html` через:
```html
{% include 'header.html' %}
```
Это означает, что `header.html` появляется на большинстве страниц, и изменения в нем сразу отражаются в UI.

### Что сделано
Файл: `web/templates/header.html`. Я добавил условный блок:
```html
{% if user and (user.role == 'STAFF' or (user.role and user.role.value == 'STAFF')) %}
<a href="/staff">Панель</a>
{% endif %}
```

### Почему условие такое “двойное”
В разных местах проекта `user.role` может быть:
- строкой (`"STAFF"`), например если вы сериализуете user и передаете как dict;
- Enum-ом SQLAlchemy (`UserRole.STAFF`), тогда для сравнения со строкой нужен `.value`.

Чтобы не зависеть от конкретного способа передачи, я поддержал оба случая.

---

## 5) Контроль доступа: staff-страницы доступны только для `STAFF`

### Какая зависимость используется
Проект уже содержит механизм ограничения доступа по ролям:
- `get_current_user`/`get_current_active_user`
- `get_current_staff` (это `require_role(UserRole.STAFF)`)

Внутри `get_current_staff`:
1) берется cookie `access_token`,
2) JWT декодируется,
3) пользователь ищется в БД по `user_id`,
4) проверяется `current_user.role == UserRole.STAFF`.

### Как это применено
Во всех staff-endpoint’ах в `app/features/staff/router.py` я добавил:
```py
user = Depends(get_current_staff)
```

### Что это дает
- `CLIENT` не может открыть `/staff/...` (получит 403).
- “весь функционал клиента выполняется корректно” — мы его не трогаем, потому что staff-эндпоинты отдельные и защищены.

---

## 6) Реализация staff-функционала: `app/features/staff/router.py`

Файл `app/features/staff/router.py` стал основным местом, где реализован весь staff-UI.
Он построен в стиле проекта:
- FastAPI endpoints;
- `templates.TemplateResponse(...)`;
- `AsyncSession` через `Depends(get_db)`;
- переиспользование существующего `product_crud`.

### 6.1 Роутер и общий префикс
```py
router = APIRouter(prefix="/staff", tags=["staff"])
```
Суть: все staff-страницы живут под `/staff/...`, что:
- логически отделяет staff от клиента;
- упрощает навигацию и дальнейшую разработку.

---

### 6.2 Хелпер `_get_products`
```py
async def _get_products(db: AsyncSession) -> List[Product]:
    products = await product_crud.get_products(db)
    return products
```
Почему добавлен:
- чтобы не дублировать по 3–4 строки получения списка товаров в нескольких endpoints;
- он опирается на существующий CRUD слой, не меняя бизнес-логику.

---

### 6.3 Хелпер `_save_product_image` (загрузка фото)
Цель: сохранить загруженный файл в `MEDIA_ROOT/products` и вернуть относительный путь для записи в `Product.image_path`.

Ключевые фрагменты:
```py
media_root = Path(settings.MEDIA_ROOT)
media_root.mkdir(parents=True, exist_ok=True)
products_dir = media_root / "products"
products_dir.mkdir(parents=True, exist_ok=True)
```
Почему так:
- `MEDIA_ROOT` уже используется в проекте (и монтируется в docker-compose как volume `./media:/app/media`),
- папка `products` уже ожидаема (у вас есть `.keep` и `.gitignore` на `media/products/*`).

Дальше генерация имени:
```py
extension = Path(upload.filename).suffix or ".jpg"
filename = f"{uuid4().hex}{extension}"
dest_path = products_dir / filename
```
Почему так:
- берём расширение из оригинального имени файла (минимально удобно),
- `uuid4` снижает вероятность коллизий,
- если расширения нет — используем `.jpg` как дефолт.

Сохранение:
```py
content = await upload.read()
dest_path.write_bytes(content)
return f"products/{filename}"
```
Суть:
- сохраняем файл на диск внутри контейнера (но каталог смонтирован — значит сохранится и на хосте),
- возвращаем **относительный** путь, потому что в шаблонах (каталог) картинка строится как `/media/{{ product.image_path }}`.

Важный нюанс:
- это синхронная запись (`write_bytes`) внутри async endpoint’а. Для больших файлов это может блокировать event loop. Но в задаче требование “минимально рабоче”, поэтому сделано максимально просто; при необходимости можно заменить на асинхронную запись через `aiofiles`.

---

### 6.4 `GET /staff` — панель работника
Endpoint:
```py
@router.get("/", response_class=HTMLResponse)
async def staff_dashboard(request: Request, user=Depends(get_current_staff)):
    return templates.TemplateResponse("staff/dashboard.html", {"request": request, "user": user})
```
Суть: страница-меню с тремя действиями (по ТЗ).

Шаблон: `web/templates/staff/dashboard.html` — 3 ссылки:
- `/staff/products/stock`
- `/staff/products/new`
- `/staff/products`

---

### 6.5 Таблица товаров (без корзины): `GET /staff/products`
Endpoint:
```py
products = await _get_products(db)
return templates.TemplateResponse("staff/products.html", {"products": products, ...})
```
Почему отдельный шаблон:
- клиентский каталог (`web/templates/catalog/list.html`) содержит кнопки и JS корзины,
- требование: “как каталог, но без кнопок добавить в корзину”,
- поэтому безопаснее и проще сделать отдельную страницу без лишних элементов.

Шаблон `web/templates/staff/products.html`:
- простая `<table>` с колонками id/название/производитель/размеры/цена/ед/остаток.

---

### 6.6 Изменение стока: `GET /staff/products/stock`
Endpoint показывает форму и (если есть) сообщения:
```py
products = await _get_products(db)
return templates.TemplateResponse("staff/stock.html", {"products": products, "message": message, "error": error, ...})
```
Тут `message`/`error` поддерживаются как query параметры (но реально основной сценарий — после POST мы рендерим ту же страницу с заполненными полями).

Шаблон `web/templates/staff/stock.html`:
- `select name="product_id"` (список всех товаров с id и текущим остатком),
- `select name="operation"` (`in`/`out`),
- `input name="delta"` (дельта, минимум 1),
- вывод `alert-success`/`alert-danger` для результата.

---

### 6.7 Изменение стока: `POST /staff/products/stock`
Здесь реализована основная логика “приход/расход + сообщение”.

Параметры формы:
```py
product_id: int = Form(...)
operation: str = Form(...)  # in|out
delta: int = Form(...)
```

Валидации:
```py
if delta <= 0:
    error = "Дельта должна быть положительной"
elif operation not in {"in", "out"}:
    error = "Некорректная операция"
```
Смысл: не даём сохранить “нулевую” или отрицательную дельту и не даём неожиданные операции.

Получение товара и расчет:
```py
product = await product_crud.get_product(db, product_id)
...
new_quantity = product.quantity_available + delta if operation == "in" else product.quantity_available - delta
```

Запрет ухода в минус:
```py
if new_quantity < 0:
    error = "Недостаточно товара на складе для списания"
```

Коммит и сообщение:
```py
product.quantity_available = new_quantity
await db.commit()
await db.refresh(product)
message = f"Количество доступного продукта {product.name} изменено: {product.quantity_available}"
```
Почему так:
- самый прямой апдейт через SQLAlchemy model instance;
- в текущем проекте нет отдельного “staff crud” для таких операций, поэтому делаем минимально.

Rollback при исключении:
```py
except Exception as exc:
    await db.rollback()
    error = f"Ошибка при обновлении стока: {exc}"
```

Поведение UI:
- После выполнения я повторно загружаю список товаров `products = await _get_products(db)` уже после коммита, чтобы в `select` отображался актуальный остаток.
- Я передаю `current_product_id/current_operation/current_delta` в шаблон, чтобы форма “не сбрасывалась” после сабмита.

---

### 6.8 Добавление товара: `GET /staff/products/new`
Endpoint:
```py
return templates.TemplateResponse("staff/add_product.html", {"message": None, "error": None, ...})
```
Суть: отрисовать форму добавления товара.

---

### 6.9 Добавление товара: `POST /staff/products/new` (multipart + файл)
Параметры формы соответствуют полям `Product`:
```py
manufacturer: str = Form(...)
name: str = Form(...)
dimensions: Optional[str] = Form(None)
unit: str = Form(...)
price: float = Form(...)
quantity_available: int = Form(0)
image: UploadFile | None = File(None)
```

Ключевые решения:
1) Количество не может быть отрицательным:
```py
if quantity_available < 0:
    raise ValueError("Количество не может быть отрицательным")
```

2) Файл сохраняем опционально:
```py
image_path = await _save_product_image(image)
```
Если файл не выбран, `image_path=None` и товар создается без фото.

3) Приведение цены:
Схема `PrCreate` ожидает `price: int`, поэтому:
```py
price_value = int(round(float(price)))
```
Это простое решение “минимально рабоче”: цена хранится как целое (рубли). В БД `Numeric(12,2)` все равно будет отображаться как `100.00`.

4) Создание товара через существующий CRUD:
```py
product = PrCreate(..., image_path=image_path)
created = await product_crud.create_product(db, product)
message = f"Товар добавлен: {created.name}"
```
Почему через CRUD:
- `product_crud.create_product` уже содержит обработку image_path (проверку существования через `check_media_file_exists`),
- централизованная логика сохранения и commit/refresh.

Шаблон `web/templates/staff/add_product.html`:
- `enctype="multipart/form-data"` (обязательно для файлов),
- выводит `message`/`error` в bootstrap alerts,
- содержит `<input type="file" name="image" accept="image/*">`.

---

## 7) Почему изменения не ломают клиента
- Клиентский каталог `/products/catalog` и его шаблон `web/templates/catalog/list.html` не изменялись.
- Логика корзины и профиля не затрагивалась.
- Новые страницы лежат в `web/templates/staff/` и имеют отдельные URL `/staff/...`.
- Доступ ограничен `get_current_staff`, то есть клиент не увидит staff-страницы.

---

## 8) Как я проверял работоспособность (реальный запуск)

Я не ограничился “подумать головой” или “прогнать unit tests”, а запускал приложение и проверял рабочие сценарии:

1) Сборка и запуск:
   - `docker compose build web`
   - `docker compose up -d db web`
2) Инициализация таблиц:
   - `docker compose exec web python -m app.infra.init_db`
3) Создание staff-пользователя (API):
   - `POST /auth/register` с `role=STAFF`
4) Логин через форму:
   - `POST /auth/login/redirect` → ответ `303`, `Location: /staff`, cookie `access_token=...`
5) Проверка страниц с cookie:
   - `GET /staff` (панель)
   - `GET/POST /staff/products/stock` (приход/расход и сообщение “Количество доступного продукта ... изменено: ...”)
   - `GET/POST /staff/products/new` (сообщение “Товар добавлен: ...”)
   - `GET /staff/products` (таблица товаров без корзины)

Нюанс API `/products`:
В FastAPI включен strict slash, поэтому `POST /products` может вернуть `307` на `/products/`. В curl это решается `-L` или сразу запросом на `/products/`.

---

## 9) Ограничения (сознательно минимально)
- Для загрузки файла нет ограничений по размеру/типу (кроме `accept="image/*"` в браузере).
- Сохранение файла делается через `write_bytes` (синхронно); для больших файлов можно заменить на `aiofiles`.
- Цена конвертируется в `int` для совместимости со схемой `PrCreate`. Если нужно хранить копейки, нужно менять схему/логику.
