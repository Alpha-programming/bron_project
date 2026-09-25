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

---

## Загрузка изображений

Общие правила для всех загрузок:
- `multipart/form-data`, поле называется **`image`**
- форматы: JPEG, PNG, WEBP
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
DELETE /api/business-gallery/{image_id}             (auth, владелец)
```

```json
// POST → 200
{"id": 7, "business_id": 2, "image": "https://.../media/business_gallery/photo.jpg", "created_at": "2026-09-25 19:00:21"}

// GET → 200
[{"id": 7, "business_id": 2, "image": "https://...", "created_at": "..."}, ...]
```

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
  {"id": 4, "name": "Clinic", "slug": "clinic", "icon": null, "business_count": 5}
]
```

`business_count` — количество **одобренных** (активных) бизнесов в категории. Пересчитывается автоматически: новый бизнес попадает в счётчик после одобрения админом.

### Создание бизнеса с категорией

```bash
curl -X POST https://bronofficial.com/api/businesses/create \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Iron Gym", "category_id": 1, "address": "Tashkent", "phone": "+998901234567"}'
```

- `200 {"message": "Business created successfully", "business_id": 42}`
- `404 {"detail": "Category not found"}` — если `category_id` не существует или категория отключена
- `422` — если передать старое поле `category` вместо `category_id`

Обновление: `PUT /api/businesses/{id}` с `{"category_id": 2}`.

Список бизнесов в категории (как раньше): `GET /api/businesses/category/{slug}`.

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

Push/Telegram-рассылки пока нет — фронт опрашивает `unread-count`.

---

## Бронирования — новые проверки

`POST /api/bookings/create` теперь возвращает:
- `400 "Business is not accepting bookings yet"` — бизнес ещё не одобрен админом
- `404 "Business, service or branch not found"` — `service_id` / `branch_id` принадлежат другому бизнесу
- `404 "Staff not found"` — сотрудник другого бизнеса
- `400 "end_time must be after start_time"`, `400 "Time must be in HH:MM format"`
- товары (`product_ids`) чужого бизнеса молча не добавляются

`PUT /api/bookings/{id}` — только для `pending` брони, и только `staff_id`.

---

## Telegram-бот

`POST /api/users/telegram/connect` теперь требует заголовок `X-Bot-Secret` (серверный секрет бота). С фронта этот эндпоинт вызывать не нужно.
