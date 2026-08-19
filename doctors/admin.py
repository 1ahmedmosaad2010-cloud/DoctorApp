from django.contrib import admin
from .models import Doctor


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "specialty",
        "license_number",
        "years_of_experience",
        "consultation_fee",
        "is_approved",
    )

    list_filter = (
        "specialty",
        "is_approved",
    )

    search_fields = (
        "user__username",
        "user__email",
        "license_number",
        "specialty",
    )