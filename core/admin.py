import json
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Max
from django.forms.utils import pretty_name
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from ninja.errors import HttpError

from core.services.booking import MAX_TOTAL_PRICE
from core.services.business_gallery import MAX_SORT_ORDER
from core.utils.validators import validate_image
from core.models import (
    User,
    Category,
    Business,
    BusinessApplication,
    BusinessView,
    Service,
    Booking,
    Payment,
    Review,
    Notification,
    Favorite,
    WorkingHours,
    Product,
    BusinessGallery,
    Staff,
    Chat,
    Branch,
    BlockedDate,
    Message,
    TelegramLinkToken
)


# --- Shared display helpers ---

THUMBNAIL_STYLE = "width:48px;height:48px;object-fit:cover;border-radius:4px;"
PREVIEW_STYLE = "max-width:240px;max-height:160px;border-radius:4px;"
INLINE_PREVIEW_STYLE = "max-width:96px;max-height:64px;border-radius:4px;"


def image_html(file, style, link=False):
    if not file:
        return "-"
    img = format_html('<img src="{}" alt="" style="{}">', file.url, style)
    if link:
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', file.url, img)
    return img


def place_after(fields, name, anchor):
    """Moves `name` right after `anchor` in a field list (readonly fields go last by default)."""
    fields = list(fields)
    if name in fields and anchor in fields:
        fields.remove(name)
        fields.insert(fields.index(anchor) + 1, name)
    return fields


class ImagePreviewMixin:
    """Read-only preview of `image` next to the upload field, plus a list thumbnail."""

    preview_style = PREVIEW_STYLE

    @admin.display(description="Preview")
    def image_preview(self, obj):
        return image_html(obj.image if obj else None, self.preview_style, link=True)

    @admin.display(description="Image")
    def thumbnail(self, obj):
        return image_html(obj.image, THUMBNAIL_STYLE)

    def get_fields(self, request, obj=None):
        return place_after(super().get_fields(request, obj), "image_preview", "image")


def schedule_summary(availability):
    """One-line description of Service.availability for lists and inlines."""
    if not availability:
        return "Working hours"

    entries = [e for e in availability if isinstance(e, dict)] if isinstance(availability, list) else []
    label = "1 date" if len(entries) == 1 else f"{len(entries)} dates"

    # Stored dates are ISO strings, so string comparison is date order
    today = timezone.localdate().isoformat()
    future = [e for e in entries if isinstance(e.get("date"), str) and e["date"] >= today]
    # A listed date with no times is a day off, not a bookable date
    bookable = sorted(e["date"] for e in future if e.get("times"))

    if bookable:
        return f"{label}, next {bookable[0]}"
    if future:
        return f"{label}, no upcoming times"
    return f"{label} (all past)"


def _decimal(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _quantity(value):
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _money(value):
    return "-" if value is None else f"{value:.2f}"


CENT = Decimal("0.01")


def booking_snapshot(service, products):
    """
    Items and total for a booking made in the admin: one of each chosen
    line at its current price, in the shape the API stores
    (core.services.booking._price_order).
    """
    lines = [("service", service, service.title)]
    lines += [("product", product, product.name) for product in products]

    items, total = [], Decimal("0")
    for kind, obj, name in lines:
        price = obj.price.quantize(CENT)
        total += price
        items.append({
            "id": obj.id,
            "name": name,
            "price": str(price),
            "quantity": 1,
            "kind": kind,
        })
    return items, total


def next_gallery_position(business_id, exclude_pk=None):
    """
    Position after the last picture of a business, as API uploads get
    (capped like there, ties at the cap go by id).
    """
    pictures = BusinessGallery.objects.filter(business_id=business_id)
    if exclude_pk is not None:
        pictures = pictures.exclude(pk=exclude_pk)
    last = pictures.aggregate(last=Max("sort_order"))["last"]
    return 0 if last is None else min(last + 1, MAX_SORT_ORDER)


# --- Forms ---

SCHEDULE_HELP = mark_safe(
    'Own schedule as JSON: <code>[{"date": "YYYY-MM-DD", "times": ["HH:MM", ...]}, ...]</code>, '
    'e.g. <code>[{"date": "2026-10-01", "times": ["10:00", "14:30"]}]</code>.<br>'
    "Each time starts a slot lasting the service duration; slots must end by 23:59. "
    "When set, the service can be booked only on the listed dates and times; "
    "a date with an empty times list is a day off.<br>"
    "Empty list <code>[]</code> = bookable within the business working hours. "
    "Dates and times are sorted and de-duplicated on save."
)


class ScheduleJSONField(forms.JSONField):
    """Renders one schedule entry per line so long schedules stay readable."""

    def prepare_value(self, value):
        if isinstance(value, list) and value and all(isinstance(e, dict) for e in value):
            lines = ",\n".join("  " + json.dumps(e, ensure_ascii=False) for e in value)
            return f"[\n{lines}\n]"
        return super().prepare_value(value)


class ImageRulesForm(forms.ModelForm):
    """
    Same upload rules as the API (validate_image: JPEG, PNG or WEBP up to
    5 MB) for a newly chosen `image`. A stored picture is not checked again
    when only other fields are edited.
    """

    def clean_image(self):
        image = self.cleaned_data.get("image")
        # A new upload is an UploadedFile; the stored one is a FieldFile
        if isinstance(image, UploadedFile):
            try:
                validate_image(image)
            except HttpError as exc:
                raise ValidationError(exc.message)
        return image


GALLERY_ORDER_HELP = "Leave empty to put the picture at the end"


class BusinessGalleryForm(ImageRulesForm):
    # Optional here, unlike the model field: empty means "after the last picture"
    sort_order = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=MAX_SORT_ORDER,
        label="Sort order",
        help_text=GALLERY_ORDER_HELP,
    )

    class Meta:
        model = BusinessGallery
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model default 0 would put a new picture before all but the first.
        # An empty value also keeps an untouched extra inline row unchanged.
        if self.instance._state.adding and "sort_order" not in (kwargs.get("initial") or {}):
            self.initial.pop("sort_order", None)

    def save(self, commit=True):
        if self.cleaned_data.get("sort_order") is None:
            # Looked up on save, so several new inline rows line up one after another
            self.instance.sort_order = next_gallery_position(
                self.instance.business_id, self.instance.pk,
            )
        return super().save(commit)


class ServiceAdminForm(ImageRulesForm):
    # Only the widget and help text change: the value still goes through
    # Service.clean(), which validates and normalizes it.
    availability = ScheduleJSONField(
        required=False,
        label="Availability",
        help_text=SCHEDULE_HELP,
        widget=forms.Textarea(attrs={"rows": 8, "cols": 70, "style": "font-family: monospace;"}),
    )

    class Meta:
        model = Service
        fields = "__all__"


class ReportHiddenFieldErrorsForm(forms.ModelForm):
    """
    Model.clean() can reject a field the form does not show: the services
    inline hides availability, yet a longer duration can push a scheduled
    slot past 23:59. Django would crash with "has no field named ...",
    so such errors are shown as row errors instead.
    """

    def add_error(self, field, error):
        if field is None and isinstance(error, ValidationError) and hasattr(error, "error_dict"):
            shown = {}
            for name, errors in error.error_dict.items():
                if name == NON_FIELD_ERRORS or name in self.fields:
                    shown.setdefault(name, []).extend(errors)
                    continue
                shown.setdefault(NON_FIELD_ERRORS, []).extend(
                    ValidationError(f"{pretty_name(name)}: {message}")
                    for message in ValidationError(errors).messages
                )
            error = ValidationError(shown)
        super().add_error(field, error)


class ServiceInlineForm(ReportHiddenFieldErrorsForm, ImageRulesForm):
    pass


class BookingAdminForm(forms.ModelForm):

    class Meta:
        model = Booking
        fields = "__all__"
        # The admin reads a read-only field's help text from here
        help_texts = {
            "total_price": "Sum of the order items, calculated when the booking is created",
        }

    def clean(self):
        cleaned_data = super().clean()
        # Add page only (the change page shows service and products read-only):
        # the computed total must fit Booking.total_price
        service = cleaned_data.get("service")
        if self.instance._state.adding and service is not None:
            _, total = booking_snapshot(service, cleaned_data.get("products") or [])
            if total > MAX_TOTAL_PRICE:
                raise ValidationError("Order total is too large")
        return cleaned_data


# --- Inlines ---

class BusinessGalleryInline(ImagePreviewMixin, admin.TabularInline):
    fk_name = 'business'
    model = BusinessGallery
    form = BusinessGalleryForm
    extra = 1
    fields = ("image", "image_preview", "sort_order")
    readonly_fields = ("image_preview",)
    ordering = ("sort_order", "id")
    preview_style = INLINE_PREVIEW_STYLE

class StaffInline(admin.TabularInline):
    fk_name = 'business'
    model = Staff
    extra = 1

class WorkingHoursInline(admin.TabularInline):
    fk_name = 'business'
    model = WorkingHours
    extra = 1

class ServicesInline(admin.TabularInline):
    fk_name = 'business'
    model = Service
    form = ServiceInlineForm
    extra = 1
    # The JSON schedule does not fit a table row; it is edited on the service page
    exclude = ("availability",)
    readonly_fields = ("schedule",)
    show_change_link = True

    @admin.display(description="Schedule")
    def schedule(self, obj):
        return schedule_summary(obj.availability)

class BranchInline(admin.TabularInline):
    fk_name = 'business'
    model = Branch
    extra = 1

class ProductsInline(ImagePreviewMixin, admin.TabularInline):
    fk_name = 'business'
    model = Product
    form = ImageRulesForm
    extra = 1
    readonly_fields = ("image_preview",)
    preview_style = INLINE_PREVIEW_STYLE


# Django's UserAdmin hashes passwords. A plain ModelAdmin saved them as raw
# text, so accounts created in the admin could never log in.
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("BRON", {"fields": ("phone", "role", "telegram_id", "avatar", "language", "is_verified")}),
        # Same settings as GET/PUT /api/users/profile/notifications
        ("Notifications", {"fields": ("notify_push", "notify_email", "notify_booking_reminder", "notify_promotions")}),
    )

    # email and phone are unique, so the add form must ask for them
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "phone", "role", "usable_password", "password1", "password2"),
            },
        ),
    )

    list_display = (
        "id",
        "username",
        "email",
        "phone",
        "telegram_id",
        "role",
        "is_verified",
        "is_staff",
        "created_at",
    )

    list_filter = (
        "role",
        "is_verified",
        "is_staff",
        "notify_promotions",
    )

    search_fields = (
        "username",
        "email",
        "phone",
    )

    ordering = ("-created_at",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "slug",
        "order",
        "is_active",
    )

    list_filter = ("is_active",)

    search_fields = ("name", "slug")

    prepopulated_fields = {"slug": ("name",)}

    ordering = ("order", "name")


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "owner_name",
        "category",
        "phone",
        "email",
        "is_active",
        "views_count",
        "created_at",
    )

    list_filter = (
        "category",
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "address",
        "email",
        "owner_name",
        "owner__username",
    )

    ordering = ("-created_at",)
    inlines = [BusinessGalleryInline, WorkingHoursInline, BranchInline, ServicesInline, StaffInline, ProductsInline]

@admin.register(BusinessView)
class BusinessViewAdmin(admin.ModelAdmin):
    """
    Log written by POST /api/businesses/{id}/view, one row per request.
    Business.views_count is incremented alongside, so rows are not added or
    edited here (a manual row would not change the counter).
    """

    list_display = (
        "id",
        "business",
        "user",
        "ip",
        "viewed_at",
    )

    list_filter = ("business",)

    list_select_related = ("business", "user")

    readonly_fields = ("business", "user", "ip", "viewed_at")

    ordering = ("-viewed_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BusinessApplication)
class BusinessApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "phone",
        "email",
        "social",
        "comment",
        "status",
        "user",
        "created_at",
    )

    list_editable = ("status",)

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "full_name",
        "phone",
        "email",
        "social",
    )

    list_select_related = ("user",)

    readonly_fields = (
        "user",
        "ip",
        "created_at",
    )

    ordering = ("-created_at",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    form = ServiceAdminForm

    list_display = (
        "id",
        "title",
        "business",
        "category",
        "price",
        "duration",
        "capacity",
        "schedule",
        "is_active",
    )

    list_filter = (
        "category",
        "is_active",
    )

    search_fields = (
        "title",
        "business__name",
    )

    list_select_related = ("business",)

    @admin.display(description="Schedule")
    def schedule(self, obj):
        return schedule_summary(obj.availability)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    form = BookingAdminForm

    list_display = (
        "id",
        "user",
        "business",
        "service",
        "booking_date",
        "guest_count",
        "status",
        "items_count",
        "total_price",
        "created_at",
    )

    list_filter = (
        "status",
        "booking_date",
        "created_at",
    )

    search_fields = (
        "user__username",
        "service__title",
        "business__name",
    )

    list_select_related = ("user", "business", "service")

    ordering = ("-created_at",)

    filter_horizontal = (
        "products",
    )

    # items is the price snapshot taken when the booking was made, so it is
    # shown as a table and never edited here
    exclude = ("items",)

    def get_readonly_fields(self, request, obj=None):
        # The snapshot is what was ordered and charged, so the lines it was
        # built from and its total cannot drift from it afterwards. A new
        # booking gets its total computed from the chosen lines (save_related).
        if obj is None:
            return ("total_price", "items_table")
        return ("service", "products", "total_price", "items_table")

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        # Read-only fields are appended by default; keep the model's order
        # so the add and change pages look alike
        model_fields = sorted([*self.opts.fields, *self.opts.many_to_many])
        position = {field.name: index for index, field in enumerate(model_fields)}
        fields = sorted(fields, key=lambda name: position.get(name, len(position)))
        return place_after(fields, "items_table", "products")

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        booking = form.instance
        # Products are only known once the M2M is saved
        if not change and not booking.items:
            booking.items, booking.total_price = booking_snapshot(
                booking.service, booking.products.order_by("id"),
            )
            booking.save(update_fields=["items", "total_price"])

    @admin.display(description="Items")
    def items_count(self, obj):
        return len(obj.items) if isinstance(obj.items, list) else 0

    @admin.display(description="Order items")
    def items_table(self, obj):
        items = obj.items if obj and isinstance(obj.items, list) else []
        rows = []
        total = Decimal("0.00")

        for item in items:
            if not isinstance(item, dict):
                continue
            price = _decimal(item.get("price"))
            quantity = _quantity(item.get("quantity"))
            line_total = price * quantity if price is not None and quantity is not None else None
            if line_total is not None:
                total += line_total
            rows.append((
                item.get("name") or "-",
                item.get("kind") or "-",
                "-" if quantity is None else quantity,
                _money(price),
                _money(line_total),
            ))

        if not rows:
            return "No items"

        # Inline alignment: jazzmin themes mix Bootstrap 4 and 5 class names
        body = format_html_join(
            "",
            '<tr><td>{}</td><td>{}</td><td style="text-align:right">{}</td>'
            '<td style="text-align:right">{}</td><td style="text-align:right">{}</td></tr>',
            rows,
        )
        return format_html(
            '<table class="table table-sm table-bordered mb-0 booking-items" style="width:auto">'
            "<thead><tr><th>Name</th><th>Kind</th><th>Quantity</th>"
            "<th>Unit price</th><th>Line total</th></tr></thead>"
            "<tbody>{}</tbody>"
            '<tfoot><tr><th colspan="4" style="text-align:right">Total</th>'
            '<th style="text-align:right">{}</th></tr></tfoot>'
            "</table>",
            body,
            _money(total),
        )

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "amount",
        "payment_method",
        "status",
        "paid_at",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_method",
    )

    search_fields = (
        "transaction_id",
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "business",
        "rating",
        "created_at",
    )

    list_filter = (
        "rating",
    )

    search_fields = (
        "business__name",
        "user__username",
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "notification_type",
        "title",
        "booking",
        "is_read",
        "created_at",
    )

    list_filter = (
        "notification_type",
        "is_read",
    )


@admin.register(Favorite)
class FavouriteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "business",
        "created_at",
    )

    search_fields = (
        "user__username",
        "business__name",
    )


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "business",
        "day_of_week",
        "open_time",
        "close_time",
        "is_closed",
    )

    list_filter = (
        "day_of_week",
        "is_closed",
    )

    search_fields = (
        "business__name",
    )

@admin.register(Product)
class ProductAdmin(ImagePreviewMixin, admin.ModelAdmin):
    form = ImageRulesForm

    list_display = (
        "id",
        "thumbnail",
        "name",
        "business",
        "price",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "created_at",
    )

    search_fields = (
        "name",
        "business__name",
    )

    list_select_related = ("business",)

    readonly_fields = ("image_preview",)

    ordering = (
        "-created_at",
    )

@admin.register(BusinessGallery)
class BusinessGalleryAdmin(ImagePreviewMixin, admin.ModelAdmin):
    # The list_editable sort_order on the changelist keeps Django's own
    # (required) field; this form serves the add and change pages
    form = BusinessGalleryForm

    list_display = (
        "id",
        "thumbnail",
        "business",
        "sort_order",
        "created_at",
    )

    # Display order within a business: lower first, ties by id
    list_editable = ("sort_order",)

    list_filter = ("business",)

    search_fields = (
        "business__name",
    )

    list_select_related = ("business",)

    readonly_fields = ("image_preview",)

    ordering = ("business", "sort_order", "id")

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "full_name",
        "business",
        "position",
        "phone",
        "is_active",
    )

    list_filter = (
        "is_active",
        "position",
    )

    search_fields = (
        "full_name",
        "business__name",
    )

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "business",
        "phone",
        "is_active",
    )

    search_fields = (
        "name",
        "business__name",
    )

    list_filter = (
        "is_active",
    )

@admin.register(BlockedDate)
class BlockedDateAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "business",
        "date",
        "reason",
    )

    list_filter = (
        "date",
    )

    search_fields = (
        "business__name",
    )

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "business",
        "created_at",
    )

    search_fields = (
        "user__username",
        "business__name",
    )

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "chat",
        "sender",
        "is_read",
        "created_at",
    )

    list_filter = (
        "is_read",
    )

@admin.register(TelegramLinkToken)
class TelegramLinkTokenAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "token",
        "is_used",
        "expires_at",
        "created_at",
    )

    list_filter = (
        "is_used",
    )
