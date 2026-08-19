from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "PATIENT", "Patient"
        DOCTOR = "DOCTOR", "Doctor"

    role = models.CharField(
        max_length=20,
        choices=Role.choices
    )

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    is_verified = models.BooleanField(
        default=False
    )

    def __str__(self):
        return f"{self.username} - {self.role}"


class Doctor(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="my_doctor_profile"
    )

    specialty = models.CharField(
        max_length=100
    )

    bio = models.TextField(
        blank=True
    )

    is_available = models.BooleanField(
        default=True
    )

    consultation_fee = models.FloatField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        name = self.user.get_full_name()

        if name:
            return f"د. {name} - {self.specialty}"

        return (
            f"د. {self.user.username} - "
            f"{self.specialty}"
        )


class DoctorSchedule(models.Model):

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "الاثنين"
        TUESDAY = 1, "الثلاثاء"
        WEDNESDAY = 2, "الأربعاء"
        THURSDAY = 3, "الخميس"
        FRIDAY = 4, "الجمعة"
        SATURDAY = 5, "السبت"
        SUNDAY = 6, "الأحد"

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="schedules"
    )

    weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices,
        default=0
    )

    start_time = models.TimeField()

    end_time = models.TimeField()

    is_active = models.BooleanField(
        default=True
    )

    appointment_duration = models.PositiveIntegerField(
        default=30
    )

    class Meta:
        ordering = [
            "weekday",
            "start_time"
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "doctor",
                    "weekday"
                ],
                name="unique_doctor_weekday"
            )
        ]

    def __str__(self):
        return (
            f"{self.doctor} - "
            f"{self.get_weekday_display()} - "
            f"{self.start_time} إلى "
            f"{self.end_time}"
        )


class Message(models.Model):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )

    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_messages"
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    is_read = models.BooleanField(
        default=False
    )

    class Meta:
        ordering = [
            "created_at"
        ]

    def __str__(self):
        return (
            f"{self.sender.username} "
            f"→ "
            f"{self.receiver.username}"
        )


class Appointment(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "قيد الانتظار"
        ACCEPTED = "ACCEPTED", "مقبول"
        REJECTED = "REJECTED", "مرفوض"
        CANCELLED = "CANCELLED", "ملغي"

    class Attendance(models.TextChoices):
        NOT_MARKED = (
            "NOT_MARKED",
            "لم يتم تحديد الحضور"
        )

        ATTENDED = (
            "ATTENDED",
            "حضر"
        )

        ABSENT = (
            "ABSENT",
            "لم يحضر"
        )

    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="patient_appointments"
    )

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="appointments"
    )

    date = models.DateField()

    time = models.TimeField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    notes = models.TextField(
        blank=True
    )

    attendance = models.CharField(
        max_length=20,
        choices=Attendance.choices,
        default=Attendance.NOT_MARKED
    )

    is_rated = models.BooleanField(
        default=False
    )

    is_follow_up = models.BooleanField(
        default=False
    )

    parent_appointment = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_appointments"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            "date",
            "time"
        ]

    def __str__(self):
        appointment_type = (
            "إعادة كشف"
            if self.is_follow_up
            else "حجز"
        )

        return (
            f"{appointment_type} - "
            f"{self.patient.username} - "
            f"{self.doctor} - "
            f"{self.date} "
            f"{self.time}"
        )

    @property
    def can_rate(self):
        return (
            self.status == self.Status.ACCEPTED
            and
            self.attendance ==
            self.Attendance.ATTENDED
            and
            not self.is_rated
        )


class DoctorReview(models.Model):
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="reviews"
    )

    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="doctor_reviews"
    )

    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="review"
    )

    rating = models.PositiveSmallIntegerField()

    comment = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            "-created_at"
        ]

    def __str__(self):
        return (
            f"{self.doctor} - "
            f"{self.rating}/5 - "
            f"{self.patient.username}"
        )


class FollowUpAppointment(models.Model):
    original_appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="follow_up_records"
    )

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="follow_up_appointments"
    )

    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="follow_up_appointments"
    )

    date = models.DateField()

    time = models.TimeField()

    notes = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            "date",
            "time"
        ]

    def __str__(self):
        return (
            f"إعادة كشف - "
            f"{self.patient.username} - "
            f"{self.doctor} - "
            f"{self.date} "
            f"{self.time}"
        )


class Notification(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    title = models.CharField(
        max_length=200
    )

    message = models.TextField()

    url = models.CharField(
        max_length=500,
        blank=True,
        default=""
    )

    is_read = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            "-created_at"
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.title}"
        )


class PushSubscription(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="push_subscriptions"
    )

    endpoint = models.TextField(
        unique=True
    )

    p256dh = models.TextField()

    auth = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.user.username} - "
            "Push Subscription"
        )


class FCMToken(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="fcm_tokens"
    )

    token = models.TextField(
        unique=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return (
            f"{self.user.username} - "
            "FCM Token"
        )