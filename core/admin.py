from django.contrib import admin

from core.models import (
    User,
    Business,
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


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
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
    )

    search_fields = (
        "username",
        "email",
        "phone",
    )

    ordering = ("-created_at",)


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "category",
        "phone",
        "is_active",
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
        "owner__username",
    )

    ordering = ("-created_at",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "business",
        "category",
        "price",
        "duration",
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


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "business",
        "service",
        "booking_date",
        "guest_count",
        "status",
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

    ordering = ("-created_at",)

    filter_horizontal = (
        "products",
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
        "title",
        "is_read",
        "created_at",
    )

    list_filter = (
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
class ProductAdmin(admin.ModelAdmin):

    list_display = (
        "id",
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

    ordering = (
        "-created_at",
    )

@admin.register(BusinessGallery)
class BusinessGalleryAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "business",
        "image",
        "created_at",
    )

    search_fields = (
        "business__name",
    )

    ordering = (
        "-created_at",
    )

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