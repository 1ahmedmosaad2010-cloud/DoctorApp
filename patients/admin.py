from django.contrib import admin
from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "date_of_birth",
        "gender",
        "blood_type",
        "emergency_contact_name",
        "emergency_contact_phone",
    )

    list_filter = (
        "gender",
        "blood_type",
    )

    search_fields = (
        "user__username",
        "user__email",
        "emergency_contact_name",
        "emergency_contact_phone",
    )