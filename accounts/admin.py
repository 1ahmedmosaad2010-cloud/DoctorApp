from django.contrib import admin
from .models import Doctor, User, Message


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "phone",
        "is_verified",
    )

    list_filter = (
        "role",
        "is_verified",
    )

    search_fields = (
        "username",
        "email",
        "phone",
    )


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "specialty",
        "is_available",
        "created_at",
    )

    list_filter = (
        "specialty",
        "is_available",
    )

    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "specialty",
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "sender",
        "receiver",
        "content",
        "created_at",
        "is_read",
    )

    list_filter = (
        "is_read",
    )

    search_fields = (
        "sender__username",
        "receiver__username",
        "content",
    )