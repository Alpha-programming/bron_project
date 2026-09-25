# BRON API: что изменилось для фронтенда

Базовый URL: `https://bronofficial.com/api`
Swagger со всеми полями: https://bronofficial.com/api/docs
Подробный справочник по каждому эндпоинту: [`api-frontend.md`](./api-frontend.md)

В этом файле собраны все изменения API: что сломается в текущем коде, что добавилось и как этим пользоваться на экранах.

---

## 1. Что нужно поправить в текущем коде (breaking changes)

Эти изменения уже на проде. Старые запросы в этих местах получат ошибку.

| Где | Было | Стало | Что сделать |
|---|---|---|---|
| Создание бизнеса `POST /businesses/create` | `"category": "gym"` | `"category_id": 1` | Брать категории из `GET /categories/`, отправлять `id` |
| Создание бизнеса | `email`, `owner_name` не было | **обязательные** поля | Добавить в форму заявки |
| `social_links` бизнеса | любой объект | только `instagram`, `telegram`, `facebook`, `tiktok`, `youtube`, значения — полные URL | Отдельные поля в форме, ссылки с `https://` |
| Категория в ответах бизнеса | строка `"gym"` | объект `{"id", "name", "slug"}` | Показывать `business.category.name` |
| Все картинки | `/media/...` | полный URL `https://bronofficial.com/media/...` | Не приклеивать домен вручную |
| `GET /bookings/{id}` | публичный | нужен токен (клиента брони или владельца бизнеса) | Передавать `Authorization` |
| `GET /staff/{id}/bookings`, `GET /bookings/staff/{id}` | публичный / любой пользователь | только владелец бизнеса | Передавать токен владельца |
| `GET /businesses/{id}/stats`, `/analytics` | любой залогиненный | только владелец (иначе 403) | Показывать только в кабинете владельца |
| `PUT /bookings/{id}` | принимал `status` | `status` игнорируется, только `staff_id`, только для `pending` | Статус менять через `/approve`, `/reject`, `/cancel` |
| `POST /auth/register` при занятом логине/email/телефоне | 200 и `user_id: null` | **400** и `{"detail": "Email already exists"}` | Показывать `detail` пользователю |
| `POST /bookings/create` | принимал любые данные | новые проверки (см. раздел 8) | Обрабатывать 400/404 |

Ошибки валидации (422) приходят в формате:
```json
{"detail": [{"loc": ["body", "payload", "email"], "msg": "Value error, Enter a valid email address"}]}
```
Последний элемент `loc` — имя поля, к которому надо привязать ошибку в форме.

---

## 2. Авторизация (напоминание)

```js
const api = (path, { token, ...opts } = {}) =>
  fetch(`https://bronofficial.com/api${path}`, {
    ...opts,
    headers: {
      ...(opts.body && !(opts.body instanceof FormData) && { "Content-Type": "application/json" }),
      ...(token && { Authorization: `Bearer ${token}` }),
      ...opts.headers,
    },
  });
```

Токен выдаёт `POST /auth/login`, живёт 7 дней. Для загрузки файлов **не** ставьте `Content-Type` вручную: браузер сам проставит `multipart/form-data` с boundary.

---

## 3. Профиль пользователя

### Имя
Отдельного эндпоинта нет, имя сохраняется через обычное обновление профиля:
```js
await api("/users/profile", {
  method: "PUT", token,
  body: JSON.stringify({ first_name: "Арслан", last_name: "Бахадыров" }),
});
```
В ответе и в `GET /users/profile` есть `first_name`, `last_name`, `full_name`. `GET /auth/me` тоже отдаёт `first_name`, `last_name` и `avatar`, так что шапку можно отрисовать сразу после логина.

При регистрации `first_name` и `last_name` можно передать сразу, они необязательны.

### Аватар
```js
const form = new FormData();
form.append("image", file);                       // поле называется именно image
const profile = await api("/users/profile/avatar", { method: "POST", token, body: form }).then(r => r.json());
// profile.avatar → "https://bronofficial.com/media/avatars/..."

await api("/users/profile/avatar", { method: "DELETE", token }); // avatar → null
```

Правила для всех картинок в API: **JPEG, PNG или WEBP, до 5 МБ**. Иначе сервер ответит `400` с текстом в `detail`. Лучше проверять это на фронте до отправки.

---

## 4. Заявка бизнеса (создание)

### Шаг 1: категории для выпадающего списка
```js
const categories = await api("/categories/").then(r => r.json());
// [{ id: 1, name: "Gym", slug: "gym", icon: null, business_count: 12 }, ...]
```
`business_count` — число одобренных бизнесов в категории, его можно показывать на главной. Сами категории заводит админ в админке, фронт их только читает.

### Шаг 2: отправка заявки
```js
await api("/businesses/create", {
  method: "POST", token,
  body: JSON.stringify({
    name: "Iron Gym",
    category_id: 1,                       // обязательно
    address: "Tashkent, Amir Temur 10",   // обязательно
    phone: "+998901234567",               // обязательно
    email: "info@irongym.uz",             // обязательно
    owner_name: "Ivan Petrov",            // обязательно, имя владельца
    website: "https://irongym.uz",
    social_links: {
      instagram: "https://instagram.com/irongym",
      telegram: "https://t.me/irongym",
      facebook: "",                        // пусто = не указано
    },
    description: "", latitude: null, longitude: null, tin: "", comments: "",
  }),
});
// → { message: "Business created successfully", business_id: 42 }
```

**Важно:** новый бизнес создаётся **неактивным** и появляется в каталоге, поиске и `business_count` только после одобрения админом. Пока бизнес не одобрен, на него нельзя забронировать (`400 "Business is not accepting bookings yet"`). Владельцу стоит показать статус «Заявка на рассмотрении».

### Шаг 3: логотип и фото
```js
const logo = new FormData(); logo.append("image", logoFile);
await api(`/businesses/${id}/logo`, { method: "POST", token, body: logo });

const photo = new FormData(); photo.append("image", photoFile);
await api(`/business-gallery/upload/${id}`, { method: "POST", token, body: photo }); // по одному файлу, до 20 штук
```
- Галерея: `GET /business-gallery/business/{id}` (публичный), удаление: `DELETE /business-gallery/{image_id}`.
- Удалить логотип: `DELETE /businesses/{id}/logo`.

### Чтение бизнеса
В ответах `GET /businesses/{id}`, `/businesses/`, `/search`, `/category/{slug}` добавились поля:
```json
{
  "email": "info@irongym.uz",
  "owner_name": "Ivan Petrov",
  "category": { "id": 1, "name": "Gym", "slug": "gym" },
  "social_links": { "instagram": "https://...", "telegram": "https://...", "facebook": null, "tiktok": null, "youtube": null },
  "logo": "https://bronofficial.com/media/business_logos/...",
  "views_count": 15
}
```
В `social_links` всегда приходят все пять ключей, незаполненные равны `null`. Иконку показывайте только для непустых.

Редактирование: `PUT /businesses/{id}` с теми же полями, все необязательны. `social_links` при этом **заменяется целиком**, поэтому отправляйте полный набор.

---

## 5. Просмотры бизнеса

При открытии страницы бизнеса отправьте **один** запрос:
```js
useEffect(() => {
  api(`/businesses/${id}/view`, { method: "POST", token })   // token можно не передавать
    .then(r => r.json())
    .then(({ views_count }) => setViews(views_count));
}, [id]);
```
- Ответ: `{ "counted": true, "views_count": 15 }`. `counted: false` значит, что просмотр уже учтён ранее. Это не ошибка.
- Один пользователь (по токену, без токена — по IP) засчитывается не чаще раза в сутки на бизнес. Владелец свой бизнес не накручивает. Поэтому повторные вызовы безопасны, но в React StrictMode не удивляйтесь двойному запросу в dev.
- Если пользователь залогинен, передавайте токен, тогда учёт идёт по пользователю, а не по IP.
- `views_count` также приходит в данных бизнеса и в статистике владельца (`GET /businesses/{id}/stats`).

---

## 6. Услуги: фото, вместимость, свободное время

### Новые поля услуги
- `capacity` — сколько гостей может быть записано **в один слот одновременно**, по умолчанию 1. Например, групповая тренировка на 10 человек.
- `image` — фото услуги (полный URL или `null`).

```js
await api("/services/create", {
  method: "POST", token,
  body: JSON.stringify({ business_id: 2, title: "Group Yoga", description: "...", category: "yoga",
                         duration: 60, price: "30000", capacity: 10 }),
});

const img = new FormData(); img.append("image", file);
await api(`/services/${serviceId}/image`, { method: "POST", token, body: img });   // DELETE — убрать фото
```

### Экран записи: календарь → время → бронь

**1. Даты для календаря** (с сегодняшнего дня, где есть свободные места):
```js
const dates = await api(`/services/${serviceId}/available-dates?days=30`).then(r => r.json());
// [{ date: "2026-09-27", free_slots: 5 }, { date: "2026-09-29", free_slots: 1 }, ...]
```
Дни, которых нет в списке, делайте неактивными. `days` принимает значения от 1 до 60, по умолчанию 14.

**2. Время на выбранную дату:**
```js
const { slots, capacity } = await api(`/services/${serviceId}/availability?date=2026-09-29`).then(r => r.json());
// slots: [{ start_time: "10:00", end_time: "11:00", available_spots: 2, is_available: true }, ...]
```
- Слоты идут с шагом длительности услуги в рамках часов работы бизнеса.
- Занятые слоты тоже приходят (`is_available: false`), их можно показать серыми.
- Если `capacity > 1`, показывайте «осталось N мест» из `available_spots`.
- Пустой `slots` означает, что бизнес в этот день не работает, дата заблокирована или прошла. Уже начавшиеся сегодня слоты не приходят.
- Можно добавить `&staff_id=5`, чтобы считать занятость конкретного мастера.

**3. Бронь:**
```js
await api("/bookings/create", {
  method: "POST", token,
  body: JSON.stringify({
    business_id, service_id, branch_id,
    booking_date: "2026-09-29",
    start_time: slot.start_time,   // берите время прямо из слота
    end_time: slot.end_time,
    guest_count: 2,                // не больше slot.available_spots
    staff_id: null, product_ids: [],
  }),
});
```
Если за это время кто-то занял места, придёт `400 "Only N places left for this time"`. Покажите сообщение и перезапросите `availability`.

Свободное время считается по **часам работы** бизнеса (`/working-hours/`). Если владелец их не заполнил, слотов не будет. В кабинете владельца стоит подсказать, что часы работы нужно заполнить.

---

## 7. Уведомления

Все эндпоинты требуют токен.

```js
// бейдж на колокольчике — опрашивать, например, раз в 30–60 секунд
const { count } = await api("/notifications/unread-count", { token }).then(r => r.json());

// список (пагинация limit/offset)
const { items, count: total } = await api("/notifications/?limit=20&offset=0", { token }).then(r => r.json());
// ?unread_only=true — только непрочитанные

await api(`/notifications/${id}/read`, { method: "PATCH", token });  // прочитать одно
await api("/notifications/read-all", { method: "PATCH", token });    // прочитать все → { updated: 3 }
await api(`/notifications/${id}`, { method: "DELETE", token });
```

Элемент списка:
```json
{ "id": 15, "notification_type": "booking_confirmed", "title": "Booking confirmed",
  "message": "Iron Gym confirmed your booking on 2026-10-01 at 10:00",
  "is_read": false, "booking_id": 8, "created_at": "2026-09-25T19:16:57.346Z" }
```
По клику открывайте бронь `GET /bookings/{booking_id}`.

| `notification_type` | Кому | Когда |
|---|---|---|
| `booking_created` | владельцу бизнеса | клиент создал бронь |
| `booking_confirmed` | клиенту | владелец подтвердил |
| `booking_rejected` | клиенту | владелец отклонил |
| `booking_cancelled` | другой стороне | клиент или владелец отменил |

Тексты `title` и `message` пока приходят на английском. Для локализации ориентируйтесь на `notification_type`.

Push-уведомлений нет, только опрос `unread-count`.

---

## 8. Бронирования: новые ошибки

`POST /bookings/create` может вернуть:

| Код | `detail` | Причина |
|---|---|---|
| 400 | `Business is not accepting bookings yet` | бизнес ещё не одобрен |
| 400 | `Selected date is blocked` | владелец заблокировал дату |
| 400 | `This service allows at most N guests per slot` | `guest_count` больше вместимости |
| 400 | `Only N places left for this time` | в это время не хватает мест |
| 400 | `end_time must be after start_time` / `Time must be in HH:MM format` | неверное время |
| 404 | `Business, service or branch not found` | услуга или филиал из другого бизнеса |
| 404 | `Staff not found` | мастер из другого бизнеса |

Действия со статусом:
- владелец: `PATCH /bookings/{id}/approve`, `/reject` (только для `pending`);
- клиент или владелец: `PATCH /bookings/{id}/cancel`.

Клиент больше не может сам поставить брони статус `confirmed`.

---

## 9. Чек-лист для фронта

- [ ] Форма заявки бизнеса: `category_id` из `/categories/`, поля `email`, `owner_name`, соцсети с полными URL
- [ ] Отображение категории: `business.category.name` вместо строки
- [ ] Убрать приклеивание домена к картинкам
- [ ] Обработка `400`/`422` с выводом `detail` (регистрация, заявка, бронь)
- [ ] Статус «на рассмотрении» для неодобренного бизнеса
- [ ] Профиль: поля имени, загрузка аватара
- [ ] Страница бизнеса: `POST /businesses/{id}/view` при открытии, показ `views_count`
- [ ] Услуги: фото, `capacity`, экран записи через `available-dates` → `availability` → `bookings/create`
- [ ] Колокольчик уведомлений: `unread-count`, список, «прочитать все»
- [ ] Запросы броней и статистики — с токеном

Вопросы по API — к бэкенду. Актуальные поля всегда в Swagger: https://bronofficial.com/api/docs
