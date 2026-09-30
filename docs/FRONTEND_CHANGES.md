# BRON API: что изменилось для фронтенда

Базовый URL: `https://bronofficial.com/api`
Swagger со всеми полями: https://bronofficial.com/api/docs
Подробный справочник по каждому эндпоинту: [`api-frontend.md`](./api-frontend.md)

В этом файле собраны все изменения API: что сломается в текущем коде, что добавилось и как этим пользоваться на экранах.

---

## 1. Что нужно поправить в текущем коде (breaking changes)

Эти изменения уже на проде. Старые запросы в этих местах получат ошибку или другой ответ.

| Где | Было | Стало | Что сделать |
|---|---|---|---|
| Создание бизнеса `POST /businesses/create` | `"category": "gym"` | `"category_id": 1` | Брать категории из `GET /categories/`, отправлять `id` |
| Создание бизнеса | `email`, `owner_name` не было | **обязательные** поля | Добавить в форму заявки |
| `social_links` бизнеса | любой объект | только `instagram`, `telegram`, `facebook`, `tiktok`, `youtube`, значения — полные URL | Отдельные поля в форме, ссылки с `https://` |
| Категория в ответах бизнеса | строка `"gym"` | объект `{"id", "name", "slug"}` | Показывать `business.category.name` |
| `owner_username` в ответах бизнеса | был | **убран** (раскрывал логин владельца) | Свои бизнесы брать из `GET /businesses/my`, `owner_id` остался |
| Все картинки | `/media/...` | полный URL `https://bronofficial.com/media/...` | Не приклеивать домен вручную |
| `GET /bookings/{id}` | публичный | нужен токен (клиента брони или владельца бизнеса) | Передавать `Authorization` |
| `GET /staff/{id}/bookings`, `GET /bookings/staff/{id}` | публичный / любой пользователь | только владелец бизнеса | Передавать токен владельца |
| `GET /businesses/{id}/stats`, `/analytics` | любой залогиненный | только владелец (иначе 403) | Показывать только в кабинете владельца |
| `PUT /bookings/{id}` | принимал `status` | `status` игнорируется, только `staff_id`, только для `pending` | Статус менять через `/approve`, `/reject`, `/cancel` |
| `PATCH /bookings/{id}/attendance` с неизвестным `status` | `400` | **422**; допустимы `visited`, `late`, `no_show` | Показывать выбор только из трёх статусов (раздел 15) |
| `POST /auth/register` при занятом логине/email/телефоне | 200 и `user_id: null` | **400** и `{"detail": "Email already exists"}` | Показывать `detail` пользователю |
| `POST /bookings/create` | принимал любые данные | новые проверки (см. раздел 13) | Обрабатывать 400/404; товары передавать в `items` (раздел 14) |
| Слоты `GET /bookings/available-slots` | `?business_id&staff_id&target_date` → `{"date", "available_slots": ["09:00", "09:30", ...]}` | `?business_id&service_id&branch_id&date` (+ необязательный `staff_id`) → объект со `slots: [{start_time, end_time, is_available, available_spots}]`; `target_date` → **422** | Поменять параметры и разбор ответа (раздел 13) или перейти на `GET /services/{id}/availability` (раздел 9) |
| Проверка даты `GET /blocked-dates/check` | `?business_id&target_date=...` | `?business_id&date=...`; `target_date` → **422** | Переименовать параметр (раздел 13) |
| Фото товаров (`image` в `/products/...`) | `/media/products/...` | полный URL `https://bronofficial.com/media/products/...` | Не приклеивать домен (раздел 8) |
| Просмотры `POST /businesses/{id}/view` | +1 раз в сутки на пользователя, повтор и владелец → `counted: false` | **каждый** запрос +1, владелец тоже; `counted` всегда `true` | Вызывать строго один раз на открытие страницы (раздел 7) |
| Порядок галереи `GET /business-gallery/business/{id}` | новые фото сверху | по `sort_order`, затем `id`; новое фото — **в конец** | Показывать в порядке ответа, менять порядок через `PUT` (раздел 6) |
| Слоты со `staff_id` (`/services/{id}/availability`, `/available-dates`, `/bookings/available-slots`) | места считались только по броням этого мастера | `available_spots` — по **всем** броням услуги; слот, где мастер уже занят (в любой услуге), приходит с `is_available: false` | Ничего менять не нужно, но «свободно» теперь совпадает с тем, что пропустит бронь |
| Загрузка картинок | проверялся только `Content-Type` | проверяется реальное содержимое; файл сохраняется с расширением по формату | Отправлять настоящие JPEG/PNG/WEBP; расширение в URL может отличаться от имени файла |

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

Сервер смотрит на реальное содержимое файла, а не только на `Content-Type`: переименованный GIF или HTML с типом `image/png` получит `400 "Only JPEG, PNG or WEBP images are allowed"`. Файл сохраняется с расширением по настоящему формату (`.jpg`, `.png`, `.webp`), поэтому URL в ответе может заканчиваться иначе, чем имя загруженного файла — берите URL только из ответа.

---

## 4. Заявка бизнеса (создание)

Для заявки есть два разных запроса:

| Экран | Эндпоинт | Токен | Что появляется на бэкенде |
|---|---|---|---|
| Форма «Регистрация бизнеса»: имя, телефон, email, Instagram/Telegram, комментарий | `POST /business-applications/create` | не нужен | заявка, которую разбирает команда BRON |
| Полная анкета бизнеса: категория, адрес и т.д. | `POST /businesses/create` | нужен | неактивный бизнес, ждёт одобрения |

### Форма «Регистрация бизнеса»

Категория, адрес и название бизнеса здесь не нужны.

```js
const res = await api("/business-applications/create", {
  method: "POST",
  token,                                     // можно не передавать; если пользователь залогинен, заявка привяжется к нему
  body: JSON.stringify({
    full_name: "Arslan Bakhadyrov",          // обязательно, до 150 символов
    phone: "+998 99 999 99 99",              // обязательно, пробелы, дефисы и скобки можно оставить
    email: "info@irongym.uz",                // необязательно
    social: "@irongym",                      // необязательно: Instagram или Telegram, ник или ссылка
    comment: "Хотим подключить два филиала", // необязательно, до 120 символов
  }),
});

if (res.status === 201) {
  // заявка принята → «Спасибо! Мы свяжемся с вами»
} else {
  const { detail } = await res.json();       // 422 — ошибки по полям, 429 — слишком много заявок
}
```

- Успешный ответ — **`201`** (не 200): `{ "id": 7, "full_name": "Arslan Bakhadyrov", "phone": "+998999999999", "email": "", "social": "@irongym", "comment": "", "status": "new", "created_at": "2026-09-26T16:59:53.478Z" }`.
- Необязательные поля можно не отправлять, отправить `""` или `null`: всё это значит «не указано».
- Телефон: 7–15 цифр, `+` в начале по желанию. Сервер сохраняет его без пробелов и скобок.
- `422`: пустое имя, неверный телефон или email, комментарий длиннее 120 символов. Имя поля — последний элемент `loc` (см. раздел 1).
- `429 {"detail": "Too many applications, please try again later"}`: больше 10 заявок за час с одного IP.
- Пока запрос идёт, блокируйте кнопку «Отправить заявку», иначе двойной клик создаст две заявки.

Бизнес по такой заявке не создаётся: команда BRON видит заявки в админке и сама связывается с заявителем.

Дальше описана полная анкета (`POST /businesses/create`).

### Шаг 1: категории для выпадающего списка
```js
const categories = await api("/categories/").then(r => r.json());
// [{ id: 1, name: "Gym", slug: "gym", icon: null, business_count: 12 }, ...]
```
`business_count` — число одобренных бизнесов в категории, его можно показывать на главной. Сами категории заводит админ в админке, фронт их только читает. В списке всегда есть «Other» (раздел 5).

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

### Мои бизнесы и статус заявки

Бизнесы текущего пользователя, новые первыми, **включая неодобренные**:
```js
const mine = await api("/businesses/my", { token }).then(r => r.json());
// [{ id: 42, name: "Iron Gym", status: "pending", ... }]  — тот же формат, что GET /businesses/{id}
```
- `status`: `"pending"` — ждёт одобрения админом, `"approved"` — одобрен и виден в каталоге. Поле приходит во всех ответах бизнеса.
- Пустой массив — у пользователя нет бизнесов.
- Без токена — `401`.

Используйте его для кабинета владельца и пункта «Бизнес страница» вместо перебора `GET /businesses/` и `GET /businesses/{id}` с проверкой `owner_id`. Публичный список отдаёт только одобренные бизнесы, поэтому бизнес на рассмотрении так не найти.

### Шаг 3: логотип и фото
```js
const logo = new FormData(); logo.append("image", logoFile);
await api(`/businesses/${id}/logo`, { method: "POST", token, body: logo });

const photo = new FormData(); photo.append("image", photoFile);
await api(`/business-gallery/upload/${id}`, { method: "POST", token, body: photo }); // по одному файлу, до 20 штук
```
- Галерея: `GET /business-gallery/business/{id}` (публичный), замена фото и порядок: `PUT /business-gallery/{image_id}` (раздел 6), удаление: `DELETE /business-gallery/{image_id}`.
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
  "views_count": 15,
  "status": "approved"
}
```
В `social_links` всегда приходят все пять ключей, незаполненные равны `null`. Иконку показывайте только для непустых.

Редактирование: `PUT /businesses/{id}` с теми же полями, все необязательны. `social_links` при этом **заменяется целиком**, поэтому отправляйте полный набор.

---

## 5. Категория «Other»

`GET /categories/` теперь всегда отдаёт категорию «Other»:
```json
{ "id": 5, "name": "Other", "slug": "other", "icon": null, "business_count": 0 }
```
- Это «прочее» для бизнесов, которым не подошла ни одна категория. В заявке отправляется как обычно: `category_id: other.id`.
- По умолчанию идёт в списке последней. `id` на разных окружениях может отличаться, поэтому ищите её по `slug`: `categories.find(c => c.slug === "other")`.
- Иконки по умолчанию нет (`icon: null`), нужна заглушка. `GET /categories/other` и `GET /businesses/category/other` работают как для остальных категорий.

---

## 6. Галерея бизнеса: порядок и замена фото

Фото приходят в порядке показа: по `sort_order` (меньше — раньше), при равных — по `id`. Сортировать на фронте не нужно.
```json
[{ "id": 5, "business_id": 2, "image": "https://bronofficial.com/media/business_gallery/a.jpg", "sort_order": 0, "created_at": "2026-09-25 19:00:21" }]
```
- Новое фото (`POST /business-gallery/upload/{id}`) добавляется **в конец**: `sort_order` = максимум + 1. Раньше новые были сверху. Порядок уже загруженных фото сохранён.
- Лимиты прежние: JPEG/PNG/WEBP, до 5 МБ, до 20 фото (`400 "Gallery is limited to 20 images"`).

**Заменить фото или поменять позицию** — `PUT /business-gallery/{image_id}`, `multipart/form-data`, хотя бы одно из полей `image`, `sort_order`:
```js
// заменить файл: id и позиция остаются прежними
const form = new FormData();
form.append("image", file);
await api(`/business-gallery/${imageId}`, { method: "PUT", token, body: form });

// drag & drop: отправить новый индекс каждому сдвинутому фото
for (const [index, photo] of photos.entries()) {
  if (photo.sort_order === index) continue;
  const f = new FormData();
  f.append("sort_order", String(index));
  await api(`/business-gallery/${photo.id}`, { method: "PUT", token, body: f });
}
```
- Ответ — обновлённое фото. Остальные фото сервер **не перенумеровывает**, поэтому при перестановке отправляйте индекс каждому фото, у которого он поменялся.
- `400 "Provide image or sort_order"` — не передано ни одного поля; `400` — файл не того типа или больше 5 МБ (старое фото остаётся); `422` — `sort_order` не целое ≥ 0; `403` — не владелец; `404` — фото нет.
- `DELETE /business-gallery/{image_id}` позиции остальных фото не меняет.

---

## 7. Просмотры бизнеса

При открытии страницы бизнеса отправьте **один** запрос:
```js
useEffect(() => {
  api(`/businesses/${id}/view`, { method: "POST", token })   // token можно не передавать
    .then(r => r.json())
    .then(({ views_count }) => setViews(views_count));
}, [id]);
```
- Ответ: `{ "counted": true, "views_count": 16 }`. `counted` теперь всегда `true`, поле оставлено для совместимости, проверять его не нужно.
- **Каждый вызов = +1 просмотр.** Дедупликации больше нет: повторные открытия тем же пользователем и визиты владельца тоже считаются. Не вызывайте запрос на ререндерах, при смене вкладок и т.п. В dev под React StrictMode эффект сработает дважды и даст +2, на проде — один раз.
- Если пользователь залогинен, передавайте токен: просмотр запишется на пользователя, без токена — на IP.
- `views_count` также приходит в данных бизнеса и в статистике владельца (`GET /businesses/{id}/stats`).

---

## 8. Товары: фото

```js
const form = new FormData();
form.append("image", file);
const product = await api(`/products/${productId}/image`, { method: "POST", token, body: form }).then(r => r.json());
// product.image → "https://bronofficial.com/media/products/..."

await api(`/products/${productId}/image`, { method: "DELETE", token }); // image → null
```
- Только владелец бизнеса: `401` без токена, `403` чужой товар, `404` товара нет. Правила как для всех картинок: JPEG/PNG/WEBP, до 5 МБ.
- Новый файл заменяет старый. `DELETE` можно вызывать, даже если фото нет.
- Ответ — товар целиком: `{ id, business_id, name, description, image, price, is_active }`.
- `image` во всех ответах товаров (`/products/`, `/products/{id}`, `/products/search`, `/products/business/{id}`) теперь **полный URL**. Если раньше приклеивали домен к `/media/...`, уберите это.

---

## 9. Услуги: фото, вместимость, свободное время

### Новые поля услуги
- `capacity` — сколько гостей может быть записано **в один слот одновременно**, по умолчанию 1. Например, групповая тренировка на 10 человек.
- `image` — фото услуги (полный URL или `null`).
- `availability` — собственное расписание услуги, `[]` — запись в часы работы бизнеса (раздел 10).

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
- Слоты берутся из расписания услуги, если оно задано (раздел 10), иначе идут с шагом длительности услуги в рамках часов работы бизнеса.
- Занятые слоты тоже приходят (`is_available: false`), их можно показать серыми.
- Если `capacity > 1`, показывайте «осталось N мест» из `available_spots`.
- Пустой `slots` означает, что бизнес в этот день не работает (или дня нет в расписании услуги), дата заблокирована или прошла. Уже начавшиеся сегодня слоты не приходят.
- Можно добавить `&staff_id=5` для записи к конкретному мастеру: места по-прежнему считаются по всем броням услуги, а слоты, где этот мастер уже занят (в любой услуге), придут с `is_available: false`.

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
    staff_id: null,
    items: [],                     // товары и доп. услуги, раздел 14
  }),
});
```
Если за это время кто-то занял места, придёт `400 "Only N places left for this time"`. Покажите сообщение и перезапросите `availability`.

Если у услуги нет своего расписания, свободное время считается по **часам работы** бизнеса (`/working-hours/`). Если владелец их не заполнил, слотов не будет. В кабинете владельца стоит подсказать, что нужно заполнить часы работы или расписание услуги.

---

## 10. Расписание услуги

Владелец может задать услуге точные даты и время записи. Тогда часы работы бизнеса для этой услуги **не действуют**.

```json
"availability": [
  { "date": "2026-10-01", "times": ["10:00", "14:30"] },
  { "date": "2026-10-02", "times": [] }
]
```

| Значение | Что значит |
|---|---|
| `[]` (по умолчанию) | своего расписания нет, запись в часы работы бизнеса |
| дата со временем | запись только в эти моменты; каждое время — начало слота длиной `duration` минут |
| дата с `"times": []` | выходной |
| даты нет в списке | записи нет |

Заблокированные даты закрывают день и при расписании.

### Кабинет владельца: сохранить расписание
```js
await api(`/services/${serviceId}`, {
  method: "PUT", token,
  body: JSON.stringify({
    availability: [
      { date: "2026-10-01", times: ["10:00", "14:30"] },
      { date: "2026-10-02", times: [] },
    ],
  }),
});
// availability: null или [] — убрать расписание и вернуться к часам работы
```
- Список **заменяет** расписание целиком: отправляйте всё расписание, а не только изменённый день. Если поле не передать, расписание не меняется.
- То же поле принимает `POST /services/create`.
- Формат: дата `YYYY-MM-DD`, время `HH:MM` с ведущим нулём (`"09:00"`, не `"9:00"`). Одна дата — один раз. Сервер сортирует даты и время и убирает повторы; показывайте расписание из ответа.
- Слот должен закончиться до 23:59 включительно: при `duration: 60` последнее допустимое время — `22:59`. Иначе `400 "Slot at 23:30 on 2026-10-01 would end after 23:59"`. Та же ошибка, если поменять только `duration`, а сохранённое расписание в него не влезает.
- `422` — неверный формат даты или времени, повтор даты (текст в `msg`, см. раздел 1).
- Уже созданные брони при смене расписания не меняются.

### Клиент: календарь записи
Экран тот же, что в разделе 9, сервер сам учитывает расписание:
1. `GET /services/{id}/available-dates?days=30` — только даты из расписания, где остались места. Остальные дни делайте неактивными.
2. `GET /services/{id}/availability?date=...` — ровно слоты из расписания на эту дату (`end_time` = начало + `duration`) с `available_spots`.
3. `POST /bookings/create` с `start_time` и `end_time` **из выбранного слота**. Не вычисляйте время сами: для услуги с расписанием оно должно совпасть со слотом точно.

Поле `availability` из ответа услуги не заменяет эти запросы: в нём нет броней, блокировок и прошедшего времени.

Ошибки брони и переноса для услуги с расписанием (`400`):

| `detail` | Причина |
|---|---|
| `Service is not available on this date` | даты нет в расписании или это выходной |
| `Selected time is not in the service schedule` | такого времени нет в расписании на эту дату |
| `end_time must be 11:00 for the 10:00 slot` | `end_time` не равен начало + `duration` |

---

## 11. Уведомления

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
| `booking_rescheduled` | другой стороне | клиент или владелец перенёс бронь |

Тексты `title` и `message` пока приходят на английском. Для локализации ориентируйтесь на `notification_type`.

Push-уведомлений нет, только опрос `unread-count`.

---

## 12. Настройки уведомлений

Экран с переключателями «Push», «Email», «Напоминание о брони», «Акции»:
```js
const settings = await api("/users/profile/notifications", { token }).then(r => r.json());
// { push: true, email: true, bookingReminder: true, promotions: false }  — значения по умолчанию

// переключили один тумблер — отправляем только его
const updated = await api("/users/profile/notifications", {
  method: "PUT", token,
  body: JSON.stringify({ promotions: true }),
}).then(r => r.json());
// ответ — все четыре настройки
```
- Ключ `bookingReminder` пишется в camelCase.
- `PUT` частичный: непереданные ключи и `null` не меняются, неизвестные ключи игнорируются.
- `422` — значение не булево; `401` — без токена.
- Пока бэкенд только хранит настройки: уведомления в колокольчике приходят независимо от них.

---

## 13. Бронирования: новые ошибки

`POST /bookings/create` может вернуть:

| Код | `detail` | Причина |
|---|---|---|
| 400 | `Business is not accepting bookings yet` | бизнес ещё не одобрен |
| 400 | `Selected date is blocked` | владелец заблокировал дату |
| 400 | `guest_count must be at least 1` | `guest_count` меньше 1 |
| 400 | `This service allows at most N guests per slot` | `guest_count` больше вместимости |
| 400 | `Only N places left for this time` | в это время не хватает мест |
| 400 | `Selected time is not available: staff member is busy` | у выбранного мастера в это время уже есть бронь (в любой услуге) |
| 400 | `end_time must be after start_time` / `Time must be in HH:MM format` | неверное время |
| 400 | `Service is not available on this date` / `Selected time is not in the service schedule` / `end_time must be HH:MM for the HH:MM slot` | время не из расписания услуги (раздел 10) |
| 400 | `Item not found: product 12` / `Quantity of product 12 must be at most 100` / `Order total is too large` | ошибка в `items` (раздел 14) |
| 404 | `Business, service or branch not found` | услуга или филиал из другого бизнеса |
| 404 | `Staff not found` | мастер из другого бизнеса |

Действия со статусом:
- владелец: `PATCH /bookings/{id}/approve`, `/reject` (только для `pending`);
- клиент или владелец: `PATCH /bookings/{id}/cancel`.

Клиент больше не может сам поставить брони статус `confirmed`.

### Слоты через `GET /bookings/available-slots`

Если экран записи использует этот эндпоинт, поменяйте параметры и разбор ответа:
```js
const params = new URLSearchParams({ business_id, service_id, branch_id, date: "2026-10-01" });
if (staffId) params.set("staff_id", staffId);        // необязательно
const { slots, capacity, duration } = await api(`/bookings/available-slots?${params}`).then(r => r.json());
// slots: [{ start_time: "09:00", end_time: "10:00", is_available: true, available_spots: 2 }, ...]
```
- Было: `?business_id&staff_id&target_date` → `{ date, available_slots: ["09:00", "09:30", ...] }`. Стало: `{ business_id, service_id, branch_id, staff_id, date, duration, capacity, slots }`. `target_date` → `422`, `staff_id` необязателен.
- Слоты те же, что у `GET /services/{id}/availability` (раздел 9): по расписанию услуги или с шагом её длительности в часы работы. Занятые тоже приходят, с `is_available: false`.
- Для неодобренного бизнеса `slots: []`. `404` — бизнес, услуга, филиал или сотрудник не найдены или из другого бизнеса.
- `staff_id` работает так же, как в `/services/{id}/availability`: слоты, где мастер занят, приходят с `is_available: false`.

### Проверка заблокированной даты

```js
const { is_blocked, reason } = await api(`/blocked-dates/check?business_id=${businessId}&date=2026-10-01`).then(r => r.json());
// { business_id: 2, date: "2026-10-01", is_blocked: true, reason: "Санитарный день" }
```
Параметр переименован: `target_date` → `date` (старое имя → `422`). `reason` приходит всегда: `null`, если дата свободна или причина не указана. Для календаря записи отдельно вызывать не нужно: `available-dates` уже пропускает заблокированные дни.

### Перенос брони

```js
const res = await api(`/bookings/${bookingId}/reschedule`, {
  method: "PATCH", token,
  body: JSON.stringify({ booking_date: "2026-10-05", start_time: slot.start_time, end_time: slot.end_time }),
});

if (res.status === 409) {
  // время заняли — показать detail и обновить слоты
  const { detail } = await res.json();
  showError(detail);
  reloadAvailability();
} else if (!res.ok) {
  showError((await res.json()).detail);   // 400: прошлое, выходной, вне часов работы и т.д.
} else {
  const booking = await res.json();        // обновлённая бронь
}
```

- Доступно клиенту брони и владельцу бизнеса; только для `pending` и `confirmed`.
- **Клиент** переносит **подтверждённую** бронь → статус снова `pending`, нужно новое подтверждение владельца. Покажите это пользователю до отправки.
- Другая сторона получает уведомление `booking_rescheduled`.
- Экран выбора времени тот же, что при записи: `available-dates` → `availability` услуги (`booking.service_id`).
- У услуги с расписанием новое время должно быть слотом из расписания, часы работы тогда не проверяются.

---

## 14. Состав заказа в брони (`items`)

К брони можно добавить товары и другие услуги этого же бизнеса. Вместо `product_ids` отправляйте `items`:
```js
await api("/bookings/create", {
  method: "POST", token,
  body: JSON.stringify({
    business_id, service_id, branch_id,
    booking_date: "2026-10-01", start_time: slot.start_time, end_time: slot.end_time,
    guest_count: 1,
    items: [
      { id: service_id, kind: "service", quantity: 1 },   // можно не указывать, сервер добавит сам
      { id: 12, kind: "product", quantity: 2 },
      { id: 9,  kind: "service", quantity: 1 },            // доп. услуга того же бизнеса
    ],
  }),
});
```
Ответ (так же в `GET /bookings/{id}`, `/bookings/my`, `/bookings/business/{id}`):
```json
{
  "id": 31, "status": "pending", "total_price": 165000.0,
  "items": [
    { "id": 7,  "name": "Training", "price": 95000.0, "quantity": 1, "kind": "service" },
    { "id": 12, "name": "Water",    "price": 10000.0, "quantity": 2, "kind": "product" },
    { "id": 9,  "name": "Massage",  "price": 50000.0, "quantity": 1, "kind": "service" }
  ]
}
```
- Каталог для корзины: `GET /products/business/{business_id}` и `GET /services/business/{business_id}` (только активные).
- `kind` — `"service"` или `"product"`, `quantity` — от 1 до 100, по умолчанию 1. `name` и `price` можно оставить в объекте из корзины, сервер их **игнорирует** и берёт название и цену из базы.
- `total_price` считает сервер: сумма `price × quantity`, `guest_count` на цену не влияет. Итог показывайте из ответа, а не из корзины.
- Бронируемая услуга (`service_id`) всегда в заказе: если её нет в `items`, сервер добавит её первой строкой с `quantity: 1`.
- Повторы (тот же `kind` + `id`) объединяются, количества складываются.
- `items` — снимок на момент брони: смена цен потом старые брони не меняет. Брони, созданные до обновления, получили `items` автоматически (услуга и прикреплённые товары по 1 шт.); их сумма может не совпадать с `total_price`, поэтому итог всегда берите из `total_price`.
- `product_ids` устарел: работает, только если `items` пустой (каждый товар по 1 шт., чужие id молча пропускаются). Переходите на `items`.

Ошибки (бронь не создаётся):

| Код | `detail` | Причина |
|---|---|---|
| 400 | `Item not found: product 12` | товар или услуга не найдены, неактивны или из другого бизнеса |
| 400 | `Quantity of product 12 must be at most 100` | после объединения повторов больше 100 |
| 400 | `Order total is too large` | слишком большая сумма заказа |
| 422 | — | `quantity` вне 1–100 или неизвестный `kind` |

---

## 15. Отметка посещения и рейтинг клиента

**Кабинет владельца: отметка посещения.** Для подтверждённой брони:
```js
await api(`/bookings/${bookingId}/attendance`, {
  method: "PATCH",
  body: JSON.stringify({ status: "late", extra_wait_minutes: 5 }),   // visited | late | no_show
});
// ответ — бронь, в attendance_status сохранённая отметка
```
- Только владелец бизнеса (`403` для остальных), только бронь в статусе `confirmed` (`400 "Booking must be confirmed first."`).
- `visited` переводит бронь в `completed`, но отметку можно исправить позже: `late` / `no_show` вернут её в `confirmed`.
- Повторное нажатие той же кнопки безопасно: оценка не задваивается. Смена отметки заменяет прежнюю.
- `extra_wait_minutes` — только для `late`, 0–10.
- Неизвестный `status` теперь даёт `422` (раньше `400`).

**Профиль клиента: рейтинг.** `GET /reviews/customer/{customer_id}/rating` возвращает два независимых рейтинга:

| Поле | Что показывать |
|---|---|
| `rating`, `reviews_count` | рейтинг по отзывам бизнесов (как раньше) |
| `booking_rating` | рейтинг посещений: среднее, `visited` = 5, `late` = 3, `no_show` = 2.5; `null` — «нет оценённых визитов» |
| `evaluated_bookings_count` | сколько визитов учтено |
| `on_time_count`, `late_count`, `no_show_count` | «вовремя / опоздал / не пришёл» |

Отменённые брони в рейтинг посещений не входят.

---

## 16. Чек-лист для фронта

- [ ] Форма «Регистрация бизнеса»: `POST /business-applications/create` (без категории и адреса), успех — `201`, обработка `422`/`429`
- [ ] Полная анкета бизнеса: `category_id` из `/categories/`, поля `email`, `owner_name`, соцсети с полными URL
- [ ] Отображение категории: `business.category.name` вместо строки
- [ ] Убрать приклеивание домена к картинкам, в том числе к фото товаров
- [ ] Обработка `400`/`422` с выводом `detail` (регистрация, заявка, бронь)
- [ ] Кабинет владельца и «Бизнес страница»: `GET /businesses/my`, статус из поля `status` (`pending` — «на рассмотрении»)
- [ ] Профиль: поля имени, загрузка аватара
- [ ] Страница бизнеса: `POST /businesses/{id}/view` строго один раз при открытии, показ `views_count`, `counted` не проверять
- [ ] Услуги: фото, `capacity`, экран записи через `available-dates` → `availability` → `bookings/create`
- [ ] Колокольчик уведомлений: `unread-count`, список, «прочитать все»
- [ ] Запросы броней и статистики — с токеном
- [ ] Перенос брони: `PATCH /bookings/{id}/reschedule`, обработка `409` (время занято)
- [ ] `GET /bookings/available-slots`: параметры `service_id`, `branch_id`, `date` и ответ со `slots` (или переход на `/services/{id}/availability`)
- [ ] `GET /blocked-dates/check`: параметр `date` вместо `target_date`
- [ ] Категория «Other» в списке категорий, иконка-заглушка
- [ ] Галерея: порядок из ответа, перестановка и замена фото через `PUT /business-gallery/{image_id}`
- [ ] Товары: загрузка и удаление фото (`/products/{id}/image`)
- [ ] Кабинет владельца: редактор расписания услуги (`availability`), обработка `400`/`422`
- [ ] Экран записи: `start_time`/`end_time` только из слота, ошибки расписания услуги
- [ ] Бронь: товары и доп. услуги через `items`, показ `items` и `total_price` в карточке брони
- [ ] Настройки уведомлений: `GET/PUT /users/profile/notifications`
- [ ] Бронь к мастеру: обработка `400 "Selected time is not available: staff member is busy"` (создание) и `409` с тем же текстом (перенос, смена мастера через `PUT /bookings/{id}`)
- [ ] Загрузка картинок: брать URL из ответа (расширение может поменяться), показывать `detail` при `400`

Вопросы по API — к бэкенду. Актуальные поля всегда в Swagger: https://bronofficial.com/api/docs
- [ ] Отметка посещения: кнопки `visited` / `late` / `no_show` для подтверждённых броней, `extra_wait_minutes` для `late`
- [ ] Профиль клиента: `booking_rating` (или «нет оценённых визитов» при `null`) и счётчики вовремя / опоздал / не пришёл отдельно от рейтинга отзывов
