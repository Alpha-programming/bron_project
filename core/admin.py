from django.contrib import admin

from core.models import *


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
        "language",
        "created_at",
    )

    search_fields = (
        "username",
        "email",
        "phone",
        "telegram_id",
    )

    readonly_fields = (
        "created_at",
        "last_login",
        "date_joined",
    )

    ordering = ("-created_at",)

    list_per_page = 20


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "owner",
        "category",
        "created_at",
    )

    list_filter = (
        "category",
        "created_at",
    )

    search_fields = (
        "name",
        "address",
        "owner__username",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = ("-created_at",)

    list_per_page = 20


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
        "is_active",
        "category",
    )

    search_fields = (
        "title",
        "category",
        "business__name",
    )

    ordering = ("title",)

    list_per_page = 20


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "service",
        "booking_date",
        "start_time",
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
    )

    readonly_fields = (
        "created_at",
    )

    ordering = ("-created_at",)

    list_per_page = 20


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "booking",
        "amount",
        "payment_method",
        "status",
        "transaction_id",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_method",
        "created_at",
    )

    search_fields = (
        "transaction_id",
        "booking__user__username",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = ("-created_at",)

    list_per_page = 20