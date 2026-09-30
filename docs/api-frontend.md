# BRON API — изменения для фронтенда

Полная интерактивная документация: `GET /api/docs` (Swagger). Ниже — только то, что добавилось или изменилось.

Все защищённые эндпоинты принимают заголовок `Authorization: Bearer <access_token>` (токен из `POST /api/auth/login`).

---

## ⚠️ Breaking changes

| Было | Стало |
|---|---|
| `POST /api/businesses/create` принимал `"category": "gym"` | принимает `"category_id": 1` (id из `GET /api/categories/`) |
| В ответах бизнеса `"category": "gym"` | `"category": {"id": 1, "name": "Gym", "slug": "gym"}` |
| Картинки приходили как `/media/...` | абсолютный URL: `https://bronofficial.com/media/...` |
| `PUT /api/bookings/{id}` принимал `status` | `status` игнорируется; смена статуса только через `/approve`, `/reject`, `/cancel` |
| `GET /api/bookings/{id}` был публичным | требует токен; доступен клиенту брони и владельцу бизнеса |
| `GET /api/staff/{id}/bookings`, `GET /api/bookings/staff/{id}` | требуют токен владельца бизнеса |
| `GET /api/businesses/{id}/stats`, `/analytics` | только владелец бизнеса (иначе 403) |
| `POST /api/auth/register` при занятом username/email/phone отвечал 200 с `user_id: null` | отвечает **400** с `{"detail": "Email already exists"}` |
| `POST /api/businesses/create`: полей `email` и `owner_name` не было | **обязательны** (422 без них) |
| `GET /api/bookings/available-slots?business_id&staff_id&target_date` → `{"date", "available_slots": ["09:00", "09:30", ...]}` (шаг 30 минут) | параметры `business_id`, `service_id`, `branch_id`, `date` (+ необязательный `staff_id`); ответ — объект со `slots: [{start_time, end_time, is_available, available_spots}]`, шаг = длительность услуги. `target_date` → **422**. См. [Свободные слоты для брони](#свободные-слоты-для-брони) |
| `GET /api/blocked-dates/check?business_id&target_date` | `?business_id&date`; `target_date` → **422** |
| `image` товаров (`/api/products/...`) приходил как `/media/products/...` | абсолютный URL, как у остальных картинок |
| `POST /api/businesses/{id}/view` засчитывал просмотр раз в 24 часа, повтор и владелец → `counted: false` | засчитывается **каждый** запрос, владелец тоже; `counted` всегда `true` |
| Галерея бизнеса: новые фото сверху | порядок по `sort_order`, затем `id`; новое фото добавляется **в конец** |
| `social_links` — произвольный словарь | только ключи `instagram`, `telegram`, `facebook`, `tiktok`, `youtube`; значение — полный URL с `http(s)://` |
| В ответах бизнеса было `owner_username` | поле убрано; свои бизнесы — `GET /api/businesses/my` |
| `PATCH /api/bookings/{id}/attendance` с неизвестным `status` → `400` | → `422`; допустимы только `visited`, `late`, `no_show` |

---

## Имя пользователя в профиле

Отдельного эндпоинта нет — имя сохраняется через существующий `PUT /api/users/profile`:

```bash
curl -X PUT https://bronofficial.com/api/users/profile \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"first_name": "Арслан", "last_name": "Бахадыров"}'
```

Профиль (`GET/PUT /api/users/profile`) и `GET /api/auth/me` теперь содержат `first_name` и `last_name`, профиль — ещё и `full_name`:
```json
{"id": 1, "username": "arslan", "first_name": "Арслан", "last_name": "Бахадыров", "full_name": "Арслан Бахадыров", "email": "...", "phone": "...", "avatar": null, "role": "customer"}
```

`POST /api/auth/register` тоже принимает необязательные `first_name` и `last_name`.

---

## Загрузка изображений

Общие правила для всех загрузок:
- `multipart/form-data`, поле называется **`image`**
- форматы: JPEG, PNG, WEBP — проверяется **реальное содержимое файла**, а не только `Content-Type`: HTML, SVG, GIF или битый файл, отправленные как `image/png`, дают `400 "Only JPEG, PNG or WEBP images are allowed"`. `image/jpg` принимается как `image/jpeg`
- файл сохраняется с расширением по реальному формату (`.jpg`, `.png`, `.webp`), поэтому в URL ответа расширение может отличаться от имени загруженного файла
- максимум **5 МБ**
- при нарушении — `400 {"detail": "..."}`

### Аватар пользователя

```
POST   /api/users/profile/avatar     (auth)  → профиль пользователя
DELETE /api/users/profile/avatar     (auth)  → профиль пользователя
```

```bash
curl -X POST https://bronofficial.com/api/users/profile/avatar \
  -H "Authorization: Bearer $TOKEN" \
  -F "image=@avatar.jpg"
```

Ответ (тот же, что `GET /api/users/profile`, теперь с полем `avatar`):
```json
{
  "id": 1,
  "username": "john",
  "email": "john@example.com",
  "phone": "+998901234567",
  "telegram_id": null,
  "avatar": "https://bronofficial.com/media/avatars/avatar.jpg",
  "role": "customer",
  "language": "en",
  "is_verified": false,
  "rating": 0.0,
  "reviews_count": 0
}
```
После `DELETE` поле `avatar` = `null`.

### Логотип бизнеса (аватарка бизнеса)

```
POST   /api/businesses/{business_id}/logo   (auth, владелец)  → {"id": 2, "logo": "https://.../media/business_logos/x.png"}
DELETE /api/businesses/{business_id}/logo   (auth, владелец)  → {"message": "Logo deleted successfully"}
```

Логотип также приходит в `GET /api/businesses/`, `GET /api/businesses/{id}`, `/search`, `/category/{slug}`.

### Галерея бизнеса (фотки самого бизнеса)

```
POST   /api/business-gallery/upload/{business_id}   (auth, владелец)  — до 20 фото на бизнес
GET    /api/business-gallery/business/{business_id} (публичный)
PUT    /api/business-gallery/{image_id}             (auth, владелец)  — заменить фото и/или сменить позицию
DELETE /api/business-gallery/{image_id}             (auth, владелец)  → {"message": "Image deleted successfully"}
```

```json
// POST → 200
{"id": 7, "business_id": 2, "image": "https://.../media/business_gallery/photo.jpg", "sort_order": 3, "created_at": "2026-09-25 19:00:21"}

// GET → 200
[{"id": 5, "business_id": 2, "image": "https://...", "sort_order": 0, "created_at": "..."}, ...]
```

- `GET` отдаёт фото по возрастанию `sort_order`, при равных — по `id`. Неизвестный бизнес → `[]`.
- Новое фото встаёт **в конец**: `sort_order` = текущий максимум + 1 (у первого фото `0`).
- 21-е фото → `400 {"detail": "Gallery is limited to 20 images"}`.

**Замена и порядок.** `PUT /api/business-gallery/{image_id}`, `multipart/form-data`, нужно хотя бы одно поле:
- `image` — новый файл вместо текущего, старый файл удаляется. Правила те же: JPEG/PNG/WEBP, до 5 МБ;
- `sort_order` — целое ≥ 0, меньше = раньше.

```bash
curl -X PUT https://bronofficial.com/api/business-gallery/7 \
  -H "Authorization: Bearer $TOKEN" \
  -F "sort_order=0"                 # и/или -F "image=@new.jpg"
```

- `200` — обновлённый объект фото (тот же формат, что в `GET`).
- Остальные фото сервер **не перенумеровывает**. Чтобы сохранить порядок после перетаскивания, отправьте `PUT` с новым индексом каждому фото, у которого он поменялся.
- `400 "Provide image or sort_order"` — нет ни одного поля; `400` — файл не того типа или больше 5 МБ (старое фото остаётся); `422` — `sort_order` не целое ≥ 0; `403` — не владелец; `404 "Image not found"`.

### Фото товара

```
POST   /api/products/{product_id}/image   (auth, владелец бизнеса)  multipart, поле image
DELETE /api/products/{product_id}/image   (auth, владелец бизнеса)
```

```bash
curl -X POST https://bronofficial.com/api/products/12/image \
  -H "Authorization: Bearer $TOKEN" \
  -F "image=@water.jpg"
```

Ответ — товар:
```json
{"id": 12, "business_id": 2, "name": "Water", "description": "0.5 л", "image": "https://bronofficial.com/media/products/water.jpg", "price": 10000.0, "is_active": true}
```

- Новый файл заменяет старый. После `DELETE` — `"image": null`; вызывать можно и когда фото нет.
- `image` теперь **абсолютный URL** во всех ответах товаров: `GET /api/products/`, `/{id}`, `/search`, `/business/{business_id}`.
- `401` — без токена, `403` — не владелец бизнеса, `404 "Product not found"`.

---

## Категории

Категории заводятся администратором в админке. Фронт только читает список.

```
GET /api/categories/         (публичный)
GET /api/categories/{slug}   (публичный)
```

```json
[
  {"id": 1, "name": "Gym",    "slug": "gym",    "icon": null, "business_count": 12},
  {"id": 2, "name": "Spa",    "slug": "spa",    "icon": "https://.../media/category_icons/spa.png", "business_count": 3},
  {"id": 3, "name": "Salon",  "slug": "salon",  "icon": null, "business_count": 0},
  {"id": 4, "name": "Clinic", "slug": "clinic", "icon": null, "business_count": 5},
  {"id": 5, "name": "Other",  "slug": "other",  "icon": null, "business_count": 0}
]
```

`business_count` — количество **одобренных** (активных) бизнесов в категории. Пересчитывается автоматически: новый бизнес попадает в счётчик после одобрения админом.

В списке всегда есть категория **«Other»** (`slug: "other"`), по умолчанию последняя. Это «прочее» для бизнесов, которым не подошла ни одна категория; в заявке передаётся как обычно, через `category_id`. `id` на разных окружениях может отличаться, ищите её по `slug`.

### Заявка бизнеса (создание)

Обязательные поля: `name`, `category_id`, `address`, `phone`, `email`, `owner_name` (имя владельца / контактного лица).
Необязательные: `description`, `latitude`, `longitude`, `tin`, `website`, `social_links`, `comments`.

```bash
curl -X POST https://bronofficial.com/api/businesses/create \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "Iron Gym",
    "category_id": 1,
    "address": "Tashkent, Amir Temur 10",
    "phone": "+998901234567",
    "email": "info@irongym.uz",
    "owner_name": "Ivan Petrov",
    "website": "https://irongym.uz",
    "social_links": {
      "instagram": "https://instagram.com/irongym",
      "telegram": "https://t.me/irongym",
      "facebook": "",
      "tiktok": null
    }
  }'
```

- `200 {"message": "Business created successfully", "business_id": 42}`
- `422` — нет `email`/`owner_name`, некорректный email, или ссылка в `social_links` не начинается с `http://`/`https://`. В `detail[].loc` указано проблемное поле. Пустая строка или `null` в соцсети = «не указано».
- `404 {"detail": "Category not found"}` — если `category_id` не существует или категория отключена
- `422` — если передать старое поле `category` вместо `category_id`

В ответах (`GET /api/businesses/{id}`, `/search`, `/category/{slug}`) всегда приходят все пять ключей `social_links`, незаполненные — `null`:
```json
{
  "id": 42,
  "name": "Iron Gym",
  "email": "info@irongym.uz",
  "owner_name": "Ivan Petrov",
  "phone": "+998901234567",
  "website": "https://irongym.uz",
  "social_links": {"instagram": "https://instagram.com/irongym", "telegram": "https://t.me/irongym", "facebook": null, "tiktok": null, "youtube": null},
  "category": {"id": 1, "name": "Gym", "slug": "gym"},
  "status": "pending",
  "...": "..."
}
```

`status` приходит во всех ответах бизнеса (в том числе в `GET /api/businesses/`): `"pending"` — ждёт одобрения админом, `"approved"` — одобрен.

### Мои бизнесы

```
GET /api/businesses/my   (auth)  → [бизнес, ...]
```

Все бизнесы текущего пользователя, новые первыми, включая неодобренные (`status: "pending"`). Формат элемента — как у `GET /api/businesses/{id}`. Нет бизнесов — `[]`, без токена — `401`.

Обновление: `PUT /api/businesses/{id}` принимает те же поля (все необязательные), например `{"category_id": 2}`. `social_links` заменяется целиком, а не сливается с прежним.

Список бизнесов в категории (как раньше): `GET /api/businesses/category/{slug}`.

---

## Форма «Регистрация бизнеса» (короткая заявка)

Отдельный эндпоинт для формы с контактами: категория, адрес и название бизнеса не нужны. Бизнес не создаётся, заявку разбирает команда BRON в админке.

```
POST /api/business-applications/create   (публичный; Bearer-токен необязателен)
```

| Поле | Обязательно | Ограничения |
|---|---|---|
| `full_name` | да | 1–150 символов |
| `phone` | да | 7–15 цифр, `+` в начале по желанию; пробелы, дефисы, точки и скобки убираются |
| `email` | нет | корректный email |
| `social` | нет | Instagram или Telegram: ник или ссылка, до 255 символов |
| `comment` | нет | до 120 символов |

Необязательное поле можно не передавать, передать `""` или `null`. Пробелы по краям всех полей обрезаются.

```bash
curl -X POST https://bronofficial.com/api/business-applications/create \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Arslan Bakhadyrov",
    "phone": "+998 99 999 99 99",
    "email": "info@irongym.uz",
    "social": "@irongym",
    "comment": "Хотим подключить два филиала"
  }'
```

- `201`:
  ```json
  {"id": 7, "full_name": "Arslan Bakhadyrov", "phone": "+998999999999", "email": "info@irongym.uz",
   "social": "@irongym", "comment": "Хотим подключить два филиала", "status": "new",
   "created_at": "2026-09-26T16:59:53.478Z"}
  ```
- `422` — ошибка в поле, в `detail[].loc` указано какое.
- `429 {"detail": "Too many applications, please try again later"}` — больше 10 заявок за час с одного IP.

Если передан валидный токен, заявка привязывается к пользователю. Неверный или просроченный токен не мешает отправке, заявка просто уйдёт без привязки.

---

## Просмотры бизнеса

При открытии страницы бизнеса фронт **один раз** вызывает:

```
POST /api/businesses/{business_id}/view
```

Авторизация не обязательна, тело не нужно. Если токен есть — передавайте его: просмотр запишется на пользователя, без токена — на IP. Неверный токен не мешает, просмотр запишется как анонимный.

```bash
curl -X POST https://bronofficial.com/api/businesses/42/view \
  -H "Authorization: Bearer $TOKEN"        # опционально
```

```json
{"counted": true, "views_count": 16}
```

- **Каждый запрос = +1 просмотр.** Уникальности больше нет: повторные открытия тем же пользователем и визиты владельца тоже считаются. Поэтому вызывайте ровно один раз на открытие страницы, а не на каждый ререндер.
- `counted` всегда `true`, поле оставлено для совместимости.
- `views_count` — актуальное значение с учётом этого просмотра, можно сразу показывать.
- `404` — бизнеса нет.

Поле `views_count` также приходит в `GET /api/businesses/`, `GET /api/businesses/{id}`, `/search`, `/category/{slug}` и в статистике владельца `GET /api/businesses/{id}/stats`.

---

## Уведомления

Все эндпоинты требуют токен и работают только с уведомлениями текущего пользователя. Чужой `id` → `404`.

```
GET    /api/notifications/?limit=20&offset=0&unread_only=false
GET    /api/notifications/unread-count
PATCH  /api/notifications/read-all
PATCH  /api/notifications/{id}/read
DELETE /api/notifications/{id}
```

```json
// GET /api/notifications/?limit=20 → 200
{
  "items": [
    {
      "id": 15,
      "notification_type": "booking_confirmed",
      "title": "Booking confirmed",
      "message": "Iron Gym confirmed your booking on 2026-10-01 at 10:00",
      "is_read": false,
      "booking_id": 8,
      "created_at": "2026-09-25T19:16:57.346Z"
    }
  ],
  "count": 1
}

// GET /api/notifications/unread-count → {"count": 1}
// PATCH /api/notifications/read-all  → {"updated": 3}
// PATCH /api/notifications/15/read   → объект уведомления с is_read: true
// DELETE /api/notifications/15       → {"message": "Notification deleted successfully"}
```

`booking_id` — чтобы по клику открыть `GET /api/bookings/{booking_id}`.

### Когда создаются уведомления

| Событие | Кому | `notification_type` |
|---|---|---|
| Клиент создал бронь (`POST /bookings/create`) | владельцу бизнеса | `booking_created` |
| Владелец подтвердил (`PATCH /bookings/{id}/approve`) | клиенту | `booking_confirmed` |
| Владелец отклонил (`PATCH /bookings/{id}/reject`) | клиенту | `booking_rejected` |
| Клиент отменил (`PATCH /bookings/{id}/cancel`) | владельцу | `booking_cancelled` |
| Владелец отменил (`PATCH /bookings/{id}/cancel`) | клиенту | `booking_cancelled` |
| Клиент перенёс (`PATCH /bookings/{id}/reschedule`) | владельцу | `booking_rescheduled` |
| Владелец перенёс (`PATCH /bookings/{id}/reschedule`) | клиенту | `booking_rescheduled` |

Push/Telegram-рассылки пока нет — фронт опрашивает `unread-count`.

### Настройки уведомлений

```
GET /api/users/profile/notifications   (auth)
PUT /api/users/profile/notifications   (auth)
```

```json
// GET → 200 (значения по умолчанию у нового пользователя)
{"push": true, "email": true, "bookingReminder": true, "promotions": false}
```

`PUT` — частичное обновление: передавайте только изменённые переключатели. Отсутствующие ключи и `null` не меняются, неизвестные ключи игнорируются. Ответ — все четыре настройки.

```bash
curl -X PUT https://bronofficial.com/api/users/profile/notifications \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"promotions": true}'
# → {"push": true, "email": true, "bookingReminder": true, "promotions": true}
```

- Ключ `bookingReminder` пишется в camelCase (не `booking_reminder`).
- `422` — значение не булево (например, `"maybe"`); `401` — без токена.
- Пока бэкенд только хранит настройки: уведомления в колокольчике (`/api/notifications/`) приходят независимо от них.

---

## Услуги: фото, вместимость, расписание, свободное время

### Вместимость (`capacity`)

`capacity` — сколько гостей может быть записано **в один и тот же слот одновременно** (например, групповая тренировка на 10 человек). По умолчанию `1` — обычная индивидуальная услуга.

```bash
curl -X POST https://bronofficial.com/api/services/create \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"business_id": 2, "title": "Group Yoga", "description": "...", "category": "yoga",
       "duration": 60, "price": "30000", "capacity": 10}'
```

- `capacity`: от 1 до 1000; `duration` (минуты) — от 1. Меняется через `PUT /api/services/{id}`.
- `capacity` и `image` приходят во всех ответах услуг: `GET /api/services/`, `/{id}`, `/business/{id}`, `/search`.

### Фото услуги

```
POST   /api/services/{service_id}/image   (auth, владелец)  multipart, поле image
DELETE /api/services/{service_id}/image   (auth, владелец)
```
Правила те же, что для остальных картинок: JPEG/PNG/WEBP, до 5 МБ. Ответ — объект услуги с `"image": "https://bronofficial.com/media/services/..."` (после удаления `null`).

### Собственное расписание услуги (`availability`)

По умолчанию услугу бронируют в часы работы бизнеса. Если у услуги заполнено поле `availability`, её можно забронировать **только** в перечисленные даты и время:

```json
"availability": [
  {"date": "2026-10-01", "times": ["10:00", "14:30"]},
  {"date": "2026-10-02", "times": []}
]
```

- Каждое время в `times` — начало слота длиной `duration` минут: `10:00` при `duration: 60` — это слот 10:00–11:00.
- `[]` (по умолчанию) — своего расписания нет, действуют часы работы бизнеса.
- Непустой список — часы работы **игнорируются** (можно записать и в нерабочий день, и вне часов). Даты, которых нет в списке, недоступны; дата с `"times": []` — выходной.
- Заблокированные даты (`/api/blocked-dates/`) закрывают день и при расписании.
- Слот должен закончиться не позже 23:59 (время + `duration`).
- Формат: дата `YYYY-MM-DD`, время `HH:MM` с ведущим нулём (`09:00`, не `9:00`). Каждая дата — один раз. Сервер сортирует даты и время и убирает повторы времени, в ответе приходит нормализованный вариант.

Задаётся в `POST /api/services/create` и `PUT /api/services/{id}`:

```bash
curl -X PUT https://bronofficial.com/api/services/7 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"availability": [{"date": "2026-10-01", "times": ["10:00", "14:30"]}, {"date": "2026-10-02", "times": []}]}'
```

В `PUT`: поля нет — расписание не меняется; список — **заменяет** расписание целиком; `null` или `[]` — удаляет его (снова часы работы). Уже созданные брони не меняются.

Ошибки:
- `422` — неверный формат даты или времени, одна дата дважды (`msg`: `"Value error, Date 2026-10-01 appears more than once"`), больше 366 дат или больше 288 времён на дату;
- `400 "Slot at 23:30 on 2026-10-01 would end after 23:59"` — слот выходит за 23:59. То же при `PUT` только с новым `duration`, если сохранённое расписание в него не влезает.

`availability` приходит во всех ответах услуг: `GET /api/services/`, `/{id}`, `/business/{id}`, `/search` (`[]`, если расписания нет).

Не путайте: поле `availability` — расписание, которое задаёт владелец, а `GET /api/services/{id}/availability` — свободные слоты на дату с учётом броней (ниже).

### Свободное время на дату

```
GET /api/services/{service_id}/availability?date=2026-10-01[&staff_id=5]
```

```json
{
  "service_id": 7,
  "date": "2026-10-01",
  "duration": 60,
  "capacity": 3,
  "slots": [
    {"start_time": "10:00", "end_time": "11:00", "available_spots": 0, "is_available": false},
    {"start_time": "11:00", "end_time": "12:00", "available_spots": 3, "is_available": true}
  ]
}
```

- Откуда слоты: у услуги с расписанием — ровно время из `availability` на эту дату (конец = начало + `duration`); без расписания — подряд с шагом `duration` в пределах часов работы бизнеса (`/api/working-hours/`) на этот день недели.
- `available_spots` = `capacity` − гости в активных бронях (`pending`, `confirmed`), пересекающихся со слотом.
- Занятые слоты тоже приходят (`is_available: false`) — их можно показать серыми.
- Пустой `slots`: бизнес в этот день не работает, даты нет в расписании услуги или это выходной по расписанию, дата заблокирована (`/api/blocked-dates/`), дата в прошлом. На сегодня уже начавшиеся слоты не отдаются.
- `staff_id` — опционально. `available_spots` всегда считается по **всем** броням услуги. Если передан сотрудник, слоты, где у него уже есть активная бронь (в любой услуге), приходят с `is_available: false` и `available_spots: 0`. Сотрудник другого бизнеса → `404`.

Для записи используйте `start_time`/`end_time` слота в `POST /api/bookings/create`.

### Доступные даты (для календаря)

```
GET /api/services/{service_id}/available-dates?days=14[&staff_id=5]
```
```json
[{"date": "2026-09-26", "free_slots": 2}, {"date": "2026-09-27", "free_slots": 2}, {"date": "2026-09-29", "free_slots": 1}]
```
Даты начиная с сегодня, где есть хотя бы один свободный слот. `days` — от 1 до 60 (по умолчанию 14), иначе `400`. У услуги с расписанием сюда попадают только даты из `availability` в пределах `days`.

---

## Бронирования — новые проверки

`POST /api/bookings/create` теперь возвращает:
- `400 "Business is not accepting bookings yet"` — бизнес ещё не одобрен админом
- `400 "Selected date is blocked"` — дата заблокирована владельцем
- `404 "Business, service or branch not found"` — `service_id` / `branch_id` принадлежат другому бизнесу
- `404 "Staff not found"` — сотрудник другого бизнеса
- `400 "end_time must be after start_time"`, `400 "Time must be in HH:MM format"`
- `400 "Service is not available on this date"` — у услуги есть расписание, а этой даты в нём нет (или это выходной)
- `400 "Selected time is not in the service schedule"` — времени нет в расписании услуги на эту дату
- `400 "end_time must be 11:00 for the 10:00 slot"` — у услуги с расписанием `end_time` должен быть ровно начало + `duration`
- `400 "guest_count must be at least 1"`
- `400 "This service allows at most N guests per slot"` — `guest_count` больше вместимости услуги
- `400 "Only N places left for this time"` — в выбранное время не хватает свободных мест
- `400 "Selected time is not available: staff member is busy"` — у выбранного сотрудника в это время уже есть активная бронь (в любой услуге)
- ошибки состава заказа — см. [Состав заказа](#состав-заказа-items)

`PUT /api/bookings/{id}` — только для `pending` брони, и только `staff_id`. Если новый сотрудник в это время занят другой бронью → `409 "Selected time is not available: staff member is busy"`.

Любой JSON-эндпоинт, получивший `multipart/form-data` вместо JSON, отвечает `400 {"detail": "Request body must be JSON"}` (раньше было 500).

### Состав заказа (`items`)

К брони можно добавить товары и другие услуги того же бизнеса. Поле `items` заменяет `product_ids`:

```bash
curl -X POST https://bronofficial.com/api/bookings/create \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "business_id": 2, "service_id": 7, "branch_id": 3, "staff_id": null,
    "booking_date": "2026-10-01", "start_time": "10:00", "end_time": "11:00",
    "guest_count": 1,
    "items": [
      {"id": 7,  "kind": "service", "quantity": 1},
      {"id": 12, "kind": "product", "quantity": 2}
    ]
  }'
```

Ответ `200` (тот же формат у `GET /api/bookings/{id}`, `/business/{id}`, `/staff/{id}`, `approve`/`reject`/`cancel`/`reschedule`):
```json
{
  "id": 31, "user_id": 5, "business_id": 2, "service_id": 7, "branch_id": 3, "staff_id": null,
  "booking_date": "2026-10-01", "start_time": "10:00:00", "end_time": "11:00:00",
  "guest_count": 1, "total_price": 115000.0, "status": "pending",
  "attendance_status": "not_set", "extra_wait_minutes": 0,
  "items": [
    {"id": 7,  "name": "Training", "price": 95000.0, "quantity": 1, "kind": "service"},
    {"id": 12, "name": "Water",    "price": 10000.0, "quantity": 2, "kind": "product"}
  ]
}
```
`GET /api/bookings/my` тоже отдаёт `items` и `total_price` у каждой брони.

Правила:
- Элемент: `id`, `kind` (`"service"` или `"product"`), `quantity` (1–100, по умолчанию 1). `name` и `price` можно передать, но сервер их **игнорирует**: название и цена берутся из базы.
- `total_price` = сумма `price × quantity` по `items`, считается на сервере. `guest_count` на цену не влияет.
- Бронируемая услуга (`service_id`) всегда входит в заказ: если её нет в `items`, сервер добавит её первой строкой с `quantity: 1`.
- Повторы (тот же `kind` + `id`) объединяются в одну строку, количества складываются.
- `items` в ответе — снимок на момент брони: последующая смена цен старые брони не меняет. Брони, созданные до этого обновления, получили `items` автоматически (услуга и прикреплённые товары по 1 шт., по ценам на момент обновления), поэтому у них сумма `items` может не совпадать с `total_price`. Итог всегда берите из `total_price`.
- `product_ids` **устарел**: используется, только если `items` пустой (каждый товар по 1 шт., чужие и неизвестные id молча пропускаются). При непустом `items` игнорируется.

Ошибки (бронь не создаётся):
- `400 "Item not found: product 12"` — товар или услуга не найдены, неактивны или из другого бизнеса (для услуги — `"Item not found: service 9"`);
- `400 "Quantity of product 12 must be at most 100"` — после объединения повторов количество больше 100;
- `400 "Order total is too large"`;
- `422` — `quantity` вне 1–100 или `kind` не `service`/`product`.

### Свободные слоты для брони

```
GET /api/bookings/available-slots?business_id=2&service_id=7&branch_id=3&date=2026-10-01[&staff_id=5]
```

Публичный. `business_id`, `service_id`, `branch_id`, `date` (`YYYY-MM-DD`) обязательны, `staff_id` — нет. Старого `target_date` больше нет (→ `422`), `staff_id` больше не обязателен.

```json
{
  "business_id": 2, "service_id": 7, "branch_id": 3, "staff_id": null,
  "date": "2026-10-01", "duration": 60, "capacity": 2,
  "slots": [
    {"start_time": "09:00", "end_time": "10:00", "is_available": true,  "available_spots": 2},
    {"start_time": "10:00", "end_time": "11:00", "is_available": false, "available_spots": 0}
  ]
}
```

- Слоты те же, что у `GET /api/services/{service_id}/availability`: по расписанию услуги, если оно есть, иначе с шагом `duration` в часы работы бизнеса. Занятые приходят с `is_available: false`.
- `slots: []` — выходной, даты нет в расписании услуги, заблокированная дата, дата в прошлом или бизнес ещё не одобрен. Уже начавшиеся сегодня слоты не приходят.
- `staff_id` — места (`available_spots`) считаются по всем броням услуги; слоты, где выбранный сотрудник уже занят (в любой услуге), приходят с `is_available: false`. В ответе `staff_id` возвращается как передан (`null`, если не передан).
- `404` — `"Business not found"`, `"Service not found"`, `"Branch not found"`, `"Staff not found"` (в том числе если объект из другого бизнеса); `422` — нет обязательного параметра или `date` не в формате `YYYY-MM-DD`.

---

### Перенос брони

```
PATCH /api/bookings/{booking_id}/reschedule     (auth: клиент брони или владелец бизнеса)
```
```json
{ "booking_date": "2026-10-05", "start_time": "12:00", "end_time": "13:00" }
```

- `200` — обновлённая бронь (тот же формат, что `GET /bookings/{id}`).
- `409` — новое время занято: `"Selected time is not available: only 0 places left"` или `"... staff member is busy"`. Покажите сообщение и перезапросите `GET /services/{service_id}/availability?date=...`.
- `400` — время в прошлом, `end_time` ≤ `start_time`, неверный формат, дата заблокирована, бизнес в этот день не работает, время вне часов работы, время не из расписания услуги (те же сообщения, что при создании брони), бронь уже на этом времени, статус не `pending`/`confirmed`.
- `403` — чужая бронь; `401` — без токена.

Правила:
- Переносить можно только брони в статусе `pending` или `confirmed`.
- Если **клиент** переносит **подтверждённую** бронь, она возвращается в `pending` и владелец должен подтвердить её заново. Перенос владельцем статус не меняет.
- Другая сторона получает уведомление `booking_rescheduled`.
- Время выбирайте из `availability` услуги. Сама бронь при проверке не считается занятой, поэтому можно сдвинуть её внутри своего же слота.
- У услуги с собственным расписанием новое время должно быть слотом из расписания; часы работы бизнеса тогда не проверяются.

---

## Отметка посещения и рейтинг клиента

### Отметка посещения

```
PATCH /api/bookings/{booking_id}/attendance     (auth: только владелец бизнеса этой брони)
```
```json
{"status": "late", "extra_wait_minutes": 5}
```

- `status` — одно из: `visited` (пришёл вовремя), `late` (опоздал), `no_show` (не пришёл). Другое значение → `422`.
- `extra_wait_minutes` — только для `late`, от 0 до 10 (сколько бизнес ждал). Для остальных статусов сбрасывается в `0`.
- Отмечать можно только подтверждённую бронь (`confirmed`). `visited` переводит бронь в `completed`, но отметку можно поменять и после этого: `late` / `no_show` вернут бронь в `confirmed`.
- Ответ `200` — бронь целиком, в `attendance_status` сохранённая отметка.
- Повторная отправка той же отметки ничего не меняет. Новая отметка **заменяет** прежнюю, а не добавляет вторую оценку.
- Ошибки: `400 "Booking must be confirmed first."` — бронь не подтверждена (`pending`, `cancelled`, `rejected`); `400` — `extra_wait_minutes` больше 10 или меньше 0; `401` — без токена; `403 "Only the business owner can update attendance."`; `404 "Booking not found."`.

### Рейтинг клиента

```
GET /api/reviews/customer/{customer_id}/rating      (публичный)
```
```json
{
  "user_id": 5, "username": "+998901234567",
  "rating": 4.0, "reviews_count": 1,
  "booking_rating": 3.5,
  "evaluated_bookings_count": 3,
  "on_time_count": 1, "late_count": 1, "no_show_count": 1
}
```

- `rating` и `reviews_count` — как раньше, только отзывы бизнесов о клиенте.
- `booking_rating` — отдельный рейтинг посещений: среднее по отметкам, `visited` = 5, `late` = 3, `no_show` = 2.5, округление до 2 знаков. `null`, если ни одна бронь не отмечена.
- `evaluated_bookings_count` = `on_time_count` + `late_count` + `no_show_count`. Учитывается только текущая отметка каждой брони; отменённые брони не учитываются (даже если были отмечены до отмены).
- `404 "Customer not found."` — пользователя нет или он не клиент.

---

## Заблокированные даты: проверка дня

```
GET /api/blocked-dates/check?business_id=2&date=2026-10-01     (публичный)
```

```json
{"business_id": 2, "date": "2026-10-01", "is_blocked": true, "reason": "Санитарный день"}
```

- Параметр даты теперь называется `date` (было `target_date`, старое имя → `422`). Оба параметра обязательны, `date` — `YYYY-MM-DD`.
- `reason` приходит всегда: `null`, если дата свободна или причина не указана.
- Неизвестный бизнес — не ошибка, `is_blocked: false`.
- Для экрана записи отдельно вызывать не нужно: заблокированные дни уже исключены из `available-dates`, а `availability` и `available-slots` отдают для них пустой `slots`.

---

## Telegram-бот

`POST /api/users/telegram/connect` теперь требует заголовок `X-Bot-Secret` (серверный секрет бота). С фронта этот эндпоинт вызывать не нужно.
