from django.contrib import admin

from core.models import *


@admin.register(User)
class UserAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "username",
        "email",
        "phone",
        "role",
        "is_verified",
        "created_at",
    )

    list_filter = (
        "role",
        "is_verified",
        "language",
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
        "created_at",
    )

    list_filter = (
        "category",
    )

    search_fields = (
        "name",
        "address",
    )

    ordering = ("-created_at",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "title",
        "business",
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
    )

    ordering = ("title",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "service",
        "booking_date",
        "start_time",
        "status",
    )

    list_filter = (
        "status",
        "booking_date",
    )

    search_fields = (
        "user__username",
        "service__title",
    )

    ordering = ("-created_at",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "booking",
        "amount",
        "payment_method",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_method",
    )

    search_fields = (
        "transaction_id",
    )

    ordering = ("-created_at",)