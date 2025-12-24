# OnlineBuildingMaterialsStore
Online store for building materials company

Команды запуска для тестирования:
1) создать .env из заготовки:
- cp .env.example .env
2) поднять сервисы:
- docker compose up -d --build
3) создать таблицы (первый запуск или если БД пустая)
- docker compose exec web python -m app.infra.init_db
4) открываем в браузере:
сайт: http://localhost:8000/
health: http://localhost:8000/health
swagger (если нужен): http://localhost:8000/docs
5) остановить:
- docker compose down
6) сбросить БД полностью:
- docker compose down -v

В тестах conftest стирает данные бд каждый раз, поэтому создаете тестовую бд:
1) Создать тестовую БД один раз
- docker compose exec db psql -U app -d postgres -c "CREATE DATABASE app_test;"
  (если скажет “already exists” — это нормально.)

2) Запуск тестов внутри контейнера web (рекомендую, проще всем одинаково)
- docker compose exec -e DATABASE_URL=postgresql+asyncpg://app:app@db:5432/app_test web pytest -q
3) запуск только health
- docker compose exec -e DATABASE_URL=postgresql+asyncpg://app:app@db:5432/app_test web pytest -q tests/test_health.py

Pytest уже настроен на проверку покрытия (см. pytest.ini) и падает, если покрытие кода каталога `app` ниже 65%.

## ЕСЛИ ЧТО-ТО МЕНЯЕТЕ В КОДЕ НУЖНО ПЕРЕЗАПУСКАТЬ ДОКЕР ДЛЯ АКТУАЛЬНОСТИ РАБОТЫ ВАШЕГО СЕРВЕРА:
docker compose up -d --build
---


Фиксируем URLs для параллельной разработки:
## Общие
- GET /health — healthcheck (для тестов/CI)

## Auth - features/auth (dev2)
1) чисто бэк:
- POST /auth/login — логин - есть
- POST /auth/register — регистрация - есть
2) Отрисовка страниц при запросе (response_model=HTMLResponse):
- GET /auth/register — страница регистрации - есть
- GET /auth/login — страница логина - есть
3) Редирект страниц (response_model=RedirectResponse)
- POST /auth/register/redirect - при успехе редирект на страницу каталога, при ошибках редирект на страницу - есть
регистрации с аргументом error={str(e)} в url
- POST /auth/login/redirect - то же самое, что в предыдущем пункте - нет

## ЛК клиента - features/users (dev2)
Только Отрисовка страниц при запросе (response_model=HTMLResponse)
- GET /profile/me — страница профиля - переделать

## Каталог/товары - features/products (dev5 + dev4)
1) Чисто бэк
- GET /products — каталог товаров
- POST /products - добавить новый товар в БД - думаю надо в стафф это (уже написано)
- PUT products/{product_id} - обновить товар
- delete products/{product_id} - удалить товар - НУЖНО проверить связи между таблицами: 
если удаляем товар из таблицы, а он уже записан в других таблицах в настройках таблиц должно быть каскадное удаление,
так же надо будет продумать момент с обновлением странички корзины, где лежит товар, а его удалили
2) Отрисовка страниц (response_model=HTMLResponse):
- GET /products/catalog - страница каталога
3) Редирект страниц (response_model=RedirectResponse)
- POST /catalog/redirect_to_cart - перенаправление на страницу корзины /cart


## Корзина - features/cart (dev3 + dev4) ???
1) бэк
- GET /cart - возврат json с товарами корзины
- GET /cart/clear - очистить корзину
- ???
2) Отрисовка страниц (response_model=HTMLResponse):
- GET /cart/page — страница корзины
- GET /cart/confirmation - страница подтверждения заказа и ввода почты

[//]: # (- POST /cart/items/add — добавить товар &#40;product_id, quantity&#41;)

[//]: # (- POST /cart/items/{cart_item_id}/set — изменить количество &#40;quantity&#41;)

[//]: # (- POST /cart/items/{cart_item_id}/delete — удалить позицию)

## Оформление заказа (dev3 + dev4)
- GET /orders/checkout — страница ввода email
- POST /orders/checkout — создать заказ (email -> orders.order_email)
- GET /orders/success/{order_id} — страница успеха с номером


## Staff - features/staff (dev5 + dev4)
1) чисто бэк:
- GET /staff/produсts_json - импорт функции get_products по crud из features.products
- POST /staff/products/{product_id}/stock — изменить остаток (приход или уход)
- GET + POST /staff/products/new — добавить товар в бд (с фото - это image_path в модели Product)
2) Отрисовка страниц (response_model=HTMLResponse):
- GET /staff — страница панели работника (для Маши: на ней кнопка таблица товаров, кнопка добавить товар, кнопка изменить колво товара)
- GET /staff/products — таблица товаров
- GET /staff/products/{product_id}/stock - страница изменения колва (здесь форма: принимаем product_id, поле "приход или уход", delta)
3) Редирект страниц (response_model=RedirectResponse)
- POST /staff/products/redirect/list - после нажатия кнопки таблица товаров редирект на таблицу товаров /staff/products
- POST /staff/products/redirect/item - при нажатии на кнопку новый товар, редирект на страницу с формой добавления
- POST /staff/products/redirect-to-stock - после нажатия на кнопку изменить колво товара редирект на /staff/products/stock

- POST /staff/products/add_item/redirect - редирект на страницу успеха web/templates/staff/add_item_success 
при нажатии кнопки добавить товар или вывод ошибки
(после введенных данных в форму)
(маше: страницу можно сверстать аналогично странице успеха с оформлением заказа,
только уже надпись "Успешное добавление")
- POST /staff/products/update_stock/redirect
