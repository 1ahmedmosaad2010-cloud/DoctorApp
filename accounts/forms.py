from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import DoctorSchedule, User


# =========================================================
# REGISTER FORM
# =========================================================

class RegisterForm(UserCreationForm):

    class Meta:
        model = User

        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields["username"].label = "اسم المستخدم"
        self.fields["first_name"].label = "الاسم الأول"
        self.fields["last_name"].label = "اسم العائلة"
        self.fields["email"].label = "البريد الإلكتروني"
        self.fields["phone"].label = "رقم الهاتف"
        self.fields["role"].label = "نوع الحساب"
        self.fields["password1"].label = "كلمة المرور"
        self.fields["password2"].label = "تأكيد كلمة المرور"

        self.fields["role"].choices = [
            (User.Role.PATIENT, "مريض"),
            (User.Role.DOCTOR, "دكتور"),
        ]


# =========================================================
# DOCTOR SCHEDULE FORM
# =========================================================

class DoctorScheduleForm(forms.ModelForm):

    class Meta:
        model = DoctorSchedule

        fields = [
            "weekday",
            "start_time",
            "end_time",
            "is_active",
        ]

        labels = {
            "weekday": "اليوم",
            "start_time": "من الساعة",
            "end_time": "إلى الساعة",
            "is_active": "متاح للحجز",
        }

        widgets = {

            "weekday": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "start_time": forms.TimeInput(
                format="%H:%M",
                attrs={
                    "type": "time",
                    "class": "form-control",
                }
            ),

            "end_time": forms.TimeInput(
                format="%H:%M",
                attrs={
                    "type": "time",
                    "class": "form-control",
                }
            ),

            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "schedule-checkbox",
                }
            ),
        }

    def clean(self):

        cleaned_data = super().clean()

        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if start_time and end_time:

            if start_time >= end_time:

                raise forms.ValidationError(
                    "وقت بداية العمل يجب أن يكون قبل وقت نهاية العمل."
                )

        return cleaned_data