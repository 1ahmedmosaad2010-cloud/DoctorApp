from datetime import datetime, timedelta

from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from firebase_admin import credentials, initialize_app, get_app
from firebase_admin import messaging

from .forms import RegisterForm
from .models import (
    Appointment,
    Doctor,
    DoctorReview,
    DoctorSchedule,
    FCMToken,
    FollowUpAppointment,
    Message,
    Notification,
    User,
)


def get_firebase_app():
    try:
        return get_app()
    except ValueError:
        credentials_path = settings.FIREBASE_CREDENTIALS

        if not credentials_path.exists():
            print(
                "Firebase credentials file not found:",
                credentials_path
            )
            return None

        try:
            cred = credentials.Certificate(
                str(credentials_path)
            )
            return initialize_app(cred)

        except Exception as error:
            print(
                "Firebase initialization error:",
                error
            )
            return None


def send_push_notification(
    user,
    title,
    body,
    url="/accounts/dashboard/"
):
    tokens = FCMToken.objects.filter(
        user=user
    )

    if not tokens.exists():
        return

    app = get_firebase_app()

    if app is None:
        return

    for token_object in tokens:

        token = token_object.token

        if not token:
            continue

        firebase_message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data={
                "url": url,
            },
            token=token,
        )

        try:
            messaging.send(
                firebase_message,
                app=app
            )
        except Exception as error:
            print(
                "Firebase notification error:",
                error
            )


def create_user_notification(
    user,
    title,
    message,
    url="/accounts/dashboard/",
):
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        url=url,
    )

    send_push_notification(
        user=user,
        title=title,
        body=message,
        url=url,
    )


def home(request):
    return render(
        request,
        "accounts/home.html"
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form
        }
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    error = None

    if request.method == "POST":
        username_or_email = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        if not username_or_email or not password:
            error = (
                "من فضلك أدخل اسم المستخدم وكلمة المرور."
            )

        else:
            user = authenticate(
                request,
                username=username_or_email,
                password=password
            )

            if user is None:
                email_user = User.objects.filter(
                    email__iexact=username_or_email
                ).first()

                if email_user:
                    user = authenticate(
                        request,
                        username=email_user.username,
                        password=password
                    )

            if user is not None:
                if not user.is_active:
                    error = (
                        "هذا الحساب غير مفعل حاليًا."
                    )
                else:
                    login(request, user)

                    next_url = request.POST.get(
                        "next",
                        ""
                    ).strip()

                    if next_url.startswith("/"):
                        return redirect(next_url)

                    return redirect("dashboard")

            else:
                error = (
                    "اسم المستخدم أو البريد الإلكتروني "
                    "أو كلمة المرور غير صحيحة."
                )

    return render(
        request,
        "accounts/login.html",
        {
            "error": error
        }
    )


@login_required
def dashboard(request):
    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    if request.user.role == User.Role.DOCTOR:
        dashboard_appointments_url = reverse(
            "doctor_appointments"
        )
        dashboard_messages_url = reverse(
            "doctor_messages"
        )
    else:
        dashboard_appointments_url = reverse(
            "my_appointments"
        )
        dashboard_messages_url = reverse(
            "patient_messages"
        )

    return render(
        request,
        "accounts/dashboard.html",
        {
            "unread_count":
                unread_count,

            "dashboard_appointments_url":
                dashboard_appointments_url,

            "dashboard_messages_url":
                dashboard_messages_url,
        }
    )


@login_required
def doctors(request):
    doctors_list = (
        Doctor.objects
        .select_related("user")
        .prefetch_related("reviews")
        .all()
    )

    for doctor in doctors_list:
        reviews = list(
            doctor.reviews.all()
        )

        if reviews:
            total = sum(
                review.rating
                for review in reviews
            )

            doctor.average_rating = round(
                total / len(reviews),
                1
            )
        else:
            doctor.average_rating = 0

        doctor.reviews_count = len(reviews)

    return render(
        request,
        "accounts/doctors.html",
        {
            "doctors":
                doctors_list
        }
    )


@login_required
def doctor_reviews(request, doctor_id):
    doctor = get_object_or_404(
        Doctor.objects.select_related("user"),
        id=doctor_id
    )

    reviews = (
        DoctorReview.objects
        .filter(doctor=doctor)
        .select_related("patient")
        .order_by("-created_at")
    )

    reviews_count = reviews.count()

    if reviews_count > 0:
        total_rating = sum(
            review.rating
            for review in reviews
        )

        average_rating = round(
            total_rating / reviews_count,
            1
        )
    else:
        average_rating = 0

    return render(
        request,
        "accounts/doctor_reviews.html",
        {
            "doctor": doctor,
            "reviews": reviews,
            "reviews_count": reviews_count,
            "average_rating": average_rating,
        }
    )


@login_required
def doctor_schedule(request):
    if request.user.role != User.Role.DOCTOR:
        return redirect("dashboard")

    doctor = get_object_or_404(
        Doctor,
        user=request.user
    )

    if request.method == "POST":

        consultation_fee = request.POST.get(
            "consultation_fee",
            ""
        ).strip()

        if consultation_fee:
            try:
                fee = float(
                    consultation_fee
                )

                if fee >= 0:
                    doctor.consultation_fee = fee
                    doctor.save(
                        update_fields=[
                            "consultation_fee"
                        ]
                    )
            except (ValueError, TypeError):
                pass

        for weekday in range(7):

            start_time = request.POST.get(
                f"start_time_{weekday}"
            )

            end_time = request.POST.get(
                f"end_time_{weekday}"
            )

            is_active = (
                request.POST.get(
                    f"is_active_{weekday}"
                ) == "on"
            )

            appointment_duration = request.POST.get(
                f"appointment_duration_{weekday}",
                "30"
            )

            try:
                appointment_duration = int(
                    appointment_duration
                )

                if appointment_duration < 5:
                    appointment_duration = 30

            except (ValueError, TypeError):
                appointment_duration = 30

            if start_time and end_time:

                DoctorSchedule.objects.update_or_create(
                    doctor=doctor,
                    weekday=weekday,
                    defaults={
                        "start_time": start_time,
                        "end_time": end_time,
                        "is_active": is_active,
                        "appointment_duration":
                            appointment_duration,
                    }
                )

            else:

                DoctorSchedule.objects.filter(
                    doctor=doctor,
                    weekday=weekday
                ).update(
                    is_active=False
                )

        return redirect(
            "doctor_schedule"
        )

    schedules = (
        DoctorSchedule.objects
        .filter(doctor=doctor)
        .order_by("weekday", "start_time")
    )

    schedules_by_day = {
        schedule.weekday: schedule
        for schedule in schedules
    }

    saturday_first_weekdays = [
        5, 6, 0, 1, 2, 3, 4
    ]

    weekday_names = {
        value: label
        for value, label in DoctorSchedule.Weekday.choices
    }

    weekdays = [
        (weekday, weekday_names[weekday])
        for weekday in saturday_first_weekdays
    ]

    return render(
        request,
        "accounts/doctor_schedule.html",
        {
            "doctor": doctor,
            "schedules": schedules,
            "schedules_by_day": schedules_by_day,
            "weekdays": weekdays,
        }
    )


@login_required
def patient_messages(request):
    if request.user.role != User.Role.PATIENT:
        return redirect("dashboard")

    all_messages = (
        Message.objects
        .filter(
            Q(sender=request.user)
            |
            Q(receiver=request.user)
        )
        .select_related(
            "sender",
            "receiver"
        )
        .order_by("-created_at")
    )

    conversations = []
    seen_users = set()

    for message in all_messages:

        if message.sender_id == request.user.id:
            other_user = message.receiver
        else:
            other_user = message.sender

        if other_user.id in seen_users:
            continue

        seen_users.add(
            other_user.id
        )

        unread_count = (
            Message.objects.filter(
                sender=other_user,
                receiver=request.user,
                is_read=False
            ).count()
        )

        conversations.append(
            {
                "user": other_user,
                "last_message": message,
                "unread_count": unread_count,
            }
        )

    return render(
        request,
        "accounts/patient_messages.html",
        {
            "conversations":
                conversations
        }
    )


@login_required
def chat(request, doctor_id):
    if request.user.role != User.Role.PATIENT:
        return redirect("dashboard")

    doctor = get_object_or_404(
        Doctor.objects.select_related("user"),
        id=doctor_id
    )

    if request.method == "POST":

        content = request.POST.get(
            "message",
            ""
        ).strip()

        if content:

            Message.objects.create(
                sender=request.user,
                receiver=doctor.user,
                content=content
            )

            patient_name = (
                request.user.get_full_name()
                or request.user.username
            )

            chat_url = reverse(
                "doctor_chat",
                kwargs={
                    "user_id":
                        request.user.id
                }
            )

            create_user_notification(
                user=doctor.user,
                title="رسالة جديدة 💬",
                message=(
                    f"أرسل لك المريض "
                    f"{patient_name} "
                    f"رسالة جديدة."
                ),
                url=chat_url
            )

        return redirect(
            "chat",
            doctor_id=doctor.id
        )

    chat_messages = (
        Message.objects
        .filter(
            Q(
                sender=request.user,
                receiver=doctor.user
            )
            |
            Q(
                sender=doctor.user,
                receiver=request.user
            )
        )
        .select_related(
            "sender",
            "receiver"
        )
        .order_by("created_at")
    )

    Message.objects.filter(
        sender=doctor.user,
        receiver=request.user,
        is_read=False
    ).update(
        is_read=True
    )

    return render(
        request,
        "accounts/chat.html",
        {
            "doctor": doctor,
            "messages": chat_messages
        }
    )


@login_required
def doctor_messages(request):
    if request.user.role != User.Role.DOCTOR:
        return redirect("dashboard")

    all_messages = (
        Message.objects
        .filter(
            Q(sender=request.user)
            |
            Q(receiver=request.user)
        )
        .select_related(
            "sender",
            "receiver"
        )
        .order_by("-created_at")
    )

    conversations = []
    seen_users = set()

    for message in all_messages:

        if message.sender_id == request.user.id:
            other_user = message.receiver
        else:
            other_user = message.sender

        if other_user.id in seen_users:
            continue

        seen_users.add(
            other_user.id
        )

        unread_count = (
            Message.objects.filter(
                sender=other_user,
                receiver=request.user,
                is_read=False
            ).count()
        )

        conversations.append(
            {
                "user": other_user,
                "last_message": message,
                "unread_count": unread_count,
            }
        )

    return render(
        request,
        "accounts/doctor_messages.html",
        {
            "conversations":
                conversations
        }
    )


@login_required
def doctor_chat(request, user_id):

    if request.user.role != User.Role.DOCTOR:
        return redirect("dashboard")

    doctor = get_object_or_404(
        Doctor,
        user=request.user,
    )

    appointment = (
        Appointment.objects
        .filter(
            doctor=doctor,
            patient_id=user_id,
        )
        .select_related(
            "patient",
        )
        .order_by(
            "-date",
            "-time",
            "-id",
        )
        .first()
    )

    if appointment is None:
        return redirect(
            "doctor_messages"
        )

    patient = appointment.patient

    if request.method == "POST":

        content = request.POST.get(
            "message",
            "",
        ).strip()

        if content:

            Message.objects.create(
                sender=request.user,
                receiver=patient,
                content=content,
            )

            doctor_name = (
                request.user.get_full_name()
                or request.user.username
            )

            chat_url = reverse(
                "chat",
                kwargs={
                    "doctor_id": doctor.id,
                },
            )

            create_user_notification(
                user=patient,
                title="رسالة جديدة 💬",
                message=(
                    f"أرسل لك الدكتور "
                    f"{doctor_name} "
                    f"رسالة جديدة."
                ),
                url=chat_url,
            )

        return redirect(
            "doctor_chat",
            user_id=patient.id,
        )

    chat_messages = (
        Message.objects
        .filter(
            Q(
                sender=request.user,
                receiver=patient,
            )
            |
            Q(
                sender=patient,
                receiver=request.user,
            )
        )
        .select_related(
            "sender",
            "receiver",
        )
        .order_by(
            "created_at",
        )
    )

    Message.objects.filter(
        sender=patient,
        receiver=request.user,
        is_read=False,
    ).update(
        is_read=True,
    )

    return render(
        request,
        "accounts/doctor_chat.html",
        {
            "patient":
                patient,

            "messages":
                chat_messages,

            "appointment":
                appointment,
        },
    )


def get_current_week_range():

    today = timezone.localdate()

    week_start = today

    week_end = (
        today +
        timedelta(days=6)
    )

    return (
        today,
        week_start,
        week_end
    )


def get_booking_days():

    today = timezone.localdate()

    booking_end = (
        today +
        timedelta(days=6)
    )

    booking_dates = [
        today + timedelta(days=index)
        for index in range(7)
    ]

    return (
        today,
        booking_end,
        booking_dates
    )


@login_required
def book_appointment(request, doctor_id):

    if request.user.role != User.Role.PATIENT:
        return redirect("dashboard")

    doctor = get_object_or_404(
        Doctor.objects.select_related("user"),
        id=doctor_id
    )

    error = None

    (
        today,
        booking_end,
        booking_dates
    ) = get_booking_days()

    if request.method == "POST":

        date_value = request.POST.get(
            "date",
            ""
        ).strip()

        time_value = request.POST.get(
            "time",
            ""
        ).strip()

        notes = request.POST.get(
            "notes",
            ""
        ).strip()

        if not date_value or not time_value:
            error = "من فضلك اختر اليوم والساعة."

        elif not doctor.is_available:
            error = "هذا الدكتور غير متاح للحجز حاليًا."

        else:

            try:

                selected_date = datetime.strptime(
                    date_value,
                    "%Y-%m-%d"
                ).date()

                selected_time = datetime.strptime(
                    time_value,
                    "%H:%M"
                ).time()

            except ValueError:

                error = "التاريخ أو الساعة غير صحيحة."
                selected_date = None
                selected_time = None

            if not error:

                if (
                    selected_date < today
                    or
                    selected_date > booking_end
                ):

                    error = (
                        "يمكن الحجز فقط خلال "
                        "الأيام السبعة الحالية."
                    )

            if not error:

                weekday = selected_date.weekday()

                schedule = (
                    DoctorSchedule.objects
                    .filter(
                        doctor=doctor,
                        weekday=weekday,
                        is_active=True
                    )
                    .first()
                )

                if not schedule:
                    error = (
                        "الدكتور لا يعمل في هذا اليوم."
                    )

            if not error:

                if not (
                    schedule.start_time
                    <= selected_time
                    <
                    schedule.end_time
                ):

                    error = (
                        "الساعة التي اخترتها خارج "
                        "مواعيد عمل الدكتور."
                    )

            if not error:

                minutes_from_start = (
                    (
                        selected_time.hour * 60
                        +
                        selected_time.minute
                    )
                    -
                    (
                        schedule.start_time.hour * 60
                        +
                        schedule.start_time.minute
                    )
                )

                if (
                    minutes_from_start < 0
                    or
                    minutes_from_start
                    %
                    schedule.appointment_duration
                    != 0
                ):

                    error = (
                        "الساعة المختارة ليست ضمن "
                        "مواعيد الحجز المتاحة."
                    )

            if not error:

                appointment_exists = (
                    Appointment.objects
                    .filter(
                        doctor=doctor,
                        date=selected_date,
                        time=selected_time,
                        status__in=[
                            Appointment.Status.PENDING,
                            Appointment.Status.ACCEPTED,
                        ]
                    )
                    .exists()
                )

                follow_up_exists = (
                    FollowUpAppointment.objects
                    .filter(
                        doctor=doctor,
                        date=selected_date,
                        time=selected_time,
                    )
                    .exists()
                )

                if (
                    appointment_exists
                    or
                    follow_up_exists
                ):

                    error = (
                        "هذا الموعد محجوز بالفعل، "
                        "اختر موعدًا آخر."
                    )

            if not error:

                same_patient_booking = (
                    Appointment.objects
                    .filter(
                        patient=request.user,
                        doctor=doctor,
                        date=selected_date,
                        time=selected_time,
                        status__in=[
                            Appointment.Status.PENDING,
                            Appointment.Status.ACCEPTED,
                        ]
                    )
                    .exists()
                )

                if same_patient_booking:

                    error = (
                        "لديك بالفعل حجز مع هذا "
                        "الدكتور في نفس الموعد."
                    )

            if not error:

                try:

                    with transaction.atomic():

                        locked_appointment = (
                            Appointment.objects
                            .select_for_update()
                            .filter(
                                doctor=doctor,
                                date=selected_date,
                                time=selected_time,
                                status__in=[
                                    Appointment.Status.PENDING,
                                    Appointment.Status.ACCEPTED,
                                ]
                            )
                            .first()
                        )

                        if locked_appointment:

                            error = (
                                "هذا الموعد تم حجزه للتو، "
                                "اختر موعدًا آخر."
                            )

                        else:

                            locked_follow_up = (
                                FollowUpAppointment.objects
                                .select_for_update()
                                .filter(
                                    doctor=doctor,
                                    date=selected_date,
                                    time=selected_time,
                                )
                                .exists()
                            )

                            if locked_follow_up:

                                error = (
                                    "هذا الموعد محجوز كإعادة كشف، "
                                    "اختر موعدًا آخر."
                                )

                            else:

                                appointment = (
                                    Appointment.objects.create(
                                        patient=request.user,
                                        doctor=doctor,
                                        date=selected_date,
                                        time=selected_time,
                                        notes=notes
                                    )
                                )

                except Exception as error_object:

                    print(
                        "Appointment creation error:",
                        error_object
                    )

                    error = (
                        "حدث خطأ أثناء إنشاء الحجز."
                    )

                if not error:

                    patient_name = (
                        request.user.get_full_name()
                        or request.user.username
                    )

                    create_user_notification(
                        user=doctor.user,
                        title="حجز جديد 📅",
                        message=(
                            f"قام المريض {patient_name} "
                            f"بحجز موعد معك يوم "
                            f"{appointment.date} "
                            f"الساعة "
                            f"{appointment.time}."
                        ),
                        url=reverse(
                            "doctor_appointments"
                        )
                    )

                    return redirect(
                        "my_appointments"
                    )

    booked_queryset = (
        Appointment.objects
        .filter(
            doctor=doctor,
            date__gte=today,
            date__lte=booking_end,
            status__in=[
                Appointment.Status.PENDING,
                Appointment.Status.ACCEPTED,
            ]
        )
        .values(
            "date",
            "time"
        )
    )

    booked_appointments = []

    for item in booked_queryset:

        booked_appointments.append(
            {
                "date":
                    item["date"].strftime(
                        "%Y-%m-%d"
                    ),

                "time":
                    item["time"].strftime(
                        "%H:%M"
                    ),
            }
        )

    schedules = (
        DoctorSchedule.objects
        .filter(
            doctor=doctor,
            is_active=True
        )
        .order_by(
            "weekday",
            "start_time"
        )
    )

    schedules_data = []

    for schedule in schedules:

        schedules_data.append(
            {
                "weekday":
                    schedule.weekday,

                "weekday_name":
                    schedule.get_weekday_display(),

                "start_time":
                    schedule.start_time.strftime(
                        "%H:%M"
                    ),

                "end_time":
                    schedule.end_time.strftime(
                        "%H:%M"
                    ),

                "appointment_duration":
                    schedule.appointment_duration,
            }
        )

    week_days = []

    for current_date in booking_dates:

        weekday = current_date.weekday()

        schedule = (
            DoctorSchedule.objects
            .filter(
                doctor=doctor,
                weekday=weekday,
                is_active=True
            )
            .first()
        )

        week_days.append(
            {
                "date":
                    current_date,

                "weekday":
                    weekday,

                "weekday_name": (
                    schedule.get_weekday_display()
                    if schedule
                    else
                    current_date.strftime(
                        "%A"
                    )
                ),

                "schedule":
                    schedule,
            }
        )

    return render(
        request,
        "accounts/book_appointment.html",
        {
            "doctor": doctor,
            "error": error,
            "booked_appointments":
                booked_appointments,
            "schedules":
                schedules,
            "schedules_data":
                schedules_data,
            "week_days":
                week_days,
            "today":
                today,
            "current_week_start":
                today,
            "current_week_end":
                booking_end,
        }
    )


@login_required
def my_appointments(request):
    if request.user.role != User.Role.PATIENT:
        return redirect("dashboard")

    appointments = list(
        Appointment.objects
        .filter(patient=request.user)
        .select_related(
            "doctor",
            "doctor__user",
        )
        .prefetch_related(
            "doctor__reviews",
        )
        .annotate(
            status_order=Case(
                When(
                    status=Appointment.Status.PENDING,
                    then=Value(0),
                ),
                When(
                    status=Appointment.Status.ACCEPTED,
                    then=Value(1),
                ),
                When(
                    status=Appointment.Status.REJECTED,
                    then=Value(2),
                ),
                When(
                    status=Appointment.Status.CANCELLED,
                    then=Value(3),
                ),
                default=Value(4),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "date",
            "time",
            "status_order",
            "id",
        )
    )

    normal_appointments = [
        appointment
        for appointment in appointments
        if not appointment.is_follow_up
    ]

    follow_up_appointments = [
        appointment
        for appointment in appointments
        if appointment.is_follow_up
    ]

    today = timezone.localdate()
    now = timezone.localtime()
    current_tz = timezone.get_current_timezone()

    for appointment in appointments:
        appointment_datetime = timezone.make_aware(
            datetime.combine(
                appointment.date,
                appointment.time,
            ),
            current_tz,
        )

        appointment.can_mark_attendance = (
            appointment.status == Appointment.Status.ACCEPTED
            and now >= appointment_datetime
        )

        appointment.is_past_datetime = (
            appointment_datetime <= now
        )

    # =====================================================
    # NEXT NORMAL APPOINTMENT
    # كل حجوزات المريض العادية مع أي دكتور
    # =====================================================

    active_normal_appointments = [
        appointment
        for appointment in normal_appointments
        if (
            appointment.status
            in (
                Appointment.Status.PENDING,
                Appointment.Status.ACCEPTED,
            )
            and not appointment.is_past_datetime
        )
    ]

    past_normal_appointments = [
        appointment
        for appointment in normal_appointments
        if appointment.is_past_datetime
    ]

    active_normal_appointments.sort(
        key=lambda appointment: (
            appointment.date,
            appointment.time,
            appointment.id,
        )
    )

    past_normal_appointments.sort(
        key=lambda appointment: (
            appointment.date,
            appointment.time,
            appointment.id,
        ),
        reverse=True,
    )

    next_appointment = next(
        (
            appointment
            for appointment in active_normal_appointments
            if appointment.status == Appointment.Status.ACCEPTED
        ),
        None,
    )

    # =====================================================
    # FOLLOW-UP ACTIVE / PAST
    # =====================================================

    active_follow_up_appointments = [
        appointment
        for appointment in follow_up_appointments
        if (
            appointment.status
            == Appointment.Status.ACCEPTED
            and not appointment.is_past_datetime
        )
    ]

    past_follow_up_appointments = [
        appointment
        for appointment in follow_up_appointments
        if appointment.is_past_datetime
    ]

    active_follow_up_appointments.sort(
        key=lambda appointment: (
            appointment.date,
            appointment.time,
            appointment.id,
        )
    )

    past_follow_up_appointments.sort(
        key=lambda appointment: (
            appointment.date,
            appointment.time,
            appointment.id,
        ),
        reverse=True,
    )

    next_follow_up_appointment = (
        active_follow_up_appointments[0]
        if active_follow_up_appointments
        else None
    )

    # =====================================================
    # WEEK STRIP - اليوم الحالي + 6 أيام قادمة
    # =====================================================

    week_days = []

    for index in range(7):
        current_date = (
            today + timedelta(days=index)
        )

        day_appointments = [
            appointment
            for appointment in appointments
            if appointment.date == current_date
        ]

        week_days.append(
            {
                "date": current_date,
                "appointments": day_appointments,
            }
        )

    arabic_weekdays = {
        0: "الاثنين",
        1: "الثلاثاء",
        2: "الأربعاء",
        3: "الخميس",
        4: "الجمعة",
        5: "السبت",
        6: "الأحد",
    }

    appointment_filter_days = [
        {
            "date": day["date"],
            "weekday_name": arabic_weekdays.get(
                day["date"].weekday(),
                day["date"].strftime("%A"),
            ),
        }
        for day in week_days
    ]

    follow_up_notifications_count = (
        Notification.objects
        .filter(
            user=request.user,
            is_read=False,
            title__icontains="إعادة كشف",
        )
        .count()
    )

    return render(
        request,
        "accounts/my_appointments.html",
        {
            "appointments": appointments,
            "normal_appointments": normal_appointments,
            "follow_up_appointments": follow_up_appointments,

            "active_normal_appointments":
                active_normal_appointments,
            "past_normal_appointments":
                past_normal_appointments,

            "active_follow_up_appointments":
                active_follow_up_appointments,
            "past_follow_up_appointments":
                past_follow_up_appointments,

            "follow_up_notifications_count":
                follow_up_notifications_count,

            "week_days": week_days,
            "appointment_filter_days":
                appointment_filter_days,

            "today": today,
            "now": now,

            "next_appointment":
                next_appointment,

            "next_follow_up_appointment":
                next_follow_up_appointment,
        }
    )


@login_required
def doctor_appointments(request):
    if request.user.role != User.Role.DOCTOR:
        return redirect("dashboard")

    doctor = get_object_or_404(
        Doctor,
        user=request.user,
    )

    (
        today,
        week_start,
        week_end,
    ) = get_current_week_range()

    appointments = list(
        Appointment.objects
        .filter(doctor=doctor)
        .select_related(
            "patient",
            "doctor",
            "doctor__user",
        )
        .annotate(
            status_order=Case(
                When(
                    status=Appointment.Status.PENDING,
                    then=Value(0),
                ),
                When(
                    status=Appointment.Status.ACCEPTED,
                    then=Value(1),
                ),
                When(
                    status=Appointment.Status.REJECTED,
                    then=Value(2),
                ),
                When(
                    status=Appointment.Status.CANCELLED,
                    then=Value(3),
                ),
                default=Value(4),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "date",
            "time",
            "status_order",
            "id",
        )
    )

    now = timezone.localtime()
    current_tz = timezone.get_current_timezone()

    for appointment in appointments:
        appointment_datetime = timezone.make_aware(
            datetime.combine(
                appointment.date,
                appointment.time,
            ),
            current_tz,
        )

        appointment.can_mark_attendance = (
            appointment.status
            == Appointment.Status.ACCEPTED
            and now >= appointment_datetime
        )

        appointment.is_past_datetime = (
            appointment_datetime <= now
        )

    # =====================================================
    # NORMAL APPOINTMENTS
    # =====================================================

    normal_appointments = [
        appointment
        for appointment in appointments
        if not appointment.is_follow_up
    ]

    active_normal_appointments = [
        appointment
        for appointment in normal_appointments
        if (
            appointment.status
            in (
                Appointment.Status.PENDING,
                Appointment.Status.ACCEPTED,
            )
            and not appointment.is_past_datetime
        )
    ]

    past_normal_appointments = [
        appointment
        for appointment in normal_appointments
        if appointment.is_past_datetime
    ]

    active_normal_appointments.sort(
        key=lambda appointment: (
            appointment.date,
            appointment.time,
            appointment.id,
        )
    )

    past_normal_appointments.sort(
        key=lambda appointment: (
            appointment.date,
            appointment.time,
            appointment.id,
        ),
        reverse=True,
    )

    next_appointment = next(
        (
            appointment
            for appointment in active_normal_appointments
            if appointment.status == Appointment.Status.ACCEPTED
        ),
        None,
    )

    # =====================================================
    # FOLLOW-UP APPOINTMENTS
    # =====================================================

    follow_up_appointments = [
        appointment
        for appointment in appointments
        if appointment.is_follow_up
    ]

    active_follow_up_appointments = [
        appointment
        for appointment in follow_up_appointments
        if (
            appointment.status
            == Appointment.Status.ACCEPTED
            and not appointment.is_past_datetime
        )
    ]

    past_follow_up_appointments = [
        appointment
        for appointment in follow_up_appointments
        if appointment.is_past_datetime
    ]

    active_follow_up_appointments.sort(
        key=lambda appointment: (
            appointment.date,
            appointment.time,
            appointment.id,
        )
    )

    past_follow_up_appointments.sort(
        key=lambda appointment: (
            appointment.date,
            appointment.time,
            appointment.id,
        ),
        reverse=True,
    )

    next_follow_up_appointment = (
        active_follow_up_appointments[0]
        if active_follow_up_appointments
        else None
    )

    # =====================================================
    # WEEK APPOINTMENTS
    # =====================================================

    week_appointments = list(
        Appointment.objects
        .filter(
            doctor=doctor,
            date__range=[
                week_start,
                week_end,
            ],
            status__in=[
                Appointment.Status.PENDING,
                Appointment.Status.ACCEPTED,
            ],
            is_follow_up=False,
        )
        .select_related(
            "patient",
        )
        .order_by(
            "date",
            "time",
            "id",
        )
    )

    for appointment in week_appointments:
        appointment_datetime = timezone.make_aware(
            datetime.combine(
                appointment.date,
                appointment.time,
            ),
            current_tz,
        )

        appointment.can_mark_attendance = (
            appointment.status
            == Appointment.Status.ACCEPTED
            and now >= appointment_datetime
        )

        appointment.is_past_datetime = (
            appointment_datetime <= now
        )

    week_days = []

    arabic_weekdays = {
        0: "الاثنين",
        1: "الثلاثاء",
        2: "الأربعاء",
        3: "الخميس",
        4: "الجمعة",
        5: "السبت",
        6: "الأحد",
    }

    for index in range(7):
        current_date = (
            week_start
            + timedelta(days=index)
        )

        weekday = current_date.weekday()

        day_appointments = [
            appointment
            for appointment in week_appointments
            if appointment.date == current_date
        ]

        day_appointments.sort(
            key=lambda appointment: (
                appointment.date,
                appointment.time,
                appointment.id,
            )
        )

        week_days.append(
            {
                "date":
                    current_date,
                "weekday":
                    weekday,
                "weekday_name":
                    arabic_weekdays.get(
                        weekday,
                        current_date.strftime("%A"),
                    ),
                "appointments":
                    day_appointments,
            }
        )

    appointment_filter_days = [
        {
            "date": day["date"],
            "weekday_name": day["weekday_name"],
        }
        for day in week_days
    ]

    # =====================================================
    # FOLLOW-UP PICKER DAYS / SLOTS
    # =====================================================

    follow_up_days = []

    for index in range(7):
        current_date = (
            today +
            timedelta(days=index)
        )

        weekday = current_date.weekday()

        schedule = (
            DoctorSchedule.objects
            .filter(
                doctor=doctor,
                weekday=weekday,
                is_active=True,
            )
            .first()
        )

        slots = []

        if schedule:
            start_minutes = (
                schedule.start_time.hour * 60
                + schedule.start_time.minute
            )

            end_minutes = (
                schedule.end_time.hour * 60
                + schedule.end_time.minute
            )

            current_minutes = start_minutes

            while current_minutes < end_minutes:
                hour = current_minutes // 60
                minute = current_minutes % 60

                slot_time = datetime.strptime(
                    f"{hour:02d}:{minute:02d}",
                    "%H:%M",
                ).time()

                existing_appointment = (
                    Appointment.objects
                    .filter(
                        doctor=doctor,
                        date=current_date,
                        time=slot_time,
                        status__in=[
                            Appointment.Status.PENDING,
                            Appointment.Status.ACCEPTED,
                        ],
                    )
                    .select_related(
                        "patient",
                    )
                    .first()
                )

                existing_follow_up = (
                    FollowUpAppointment.objects
                    .filter(
                        doctor=doctor,
                        date=current_date,
                        time=slot_time,
                    )
                    .select_related(
                        "patient",
                    )
                    .first()
                )

                blocked = (
                    existing_appointment
                    or existing_follow_up
                )

                slot_data = {
                    "value":
                        slot_time.strftime("%H:%M"),
                    "label":
                        slot_time.strftime("%I:%M %p"),
                    "available":
                        not bool(blocked),
                    "reason":
                        "",
                    "patient_name":
                        "",
                    "appointment_notes":
                        "",
                }

                if blocked:
                    blocked_patient = (
                        blocked.patient.get_full_name()
                        or blocked.patient.username
                    )

                    slot_data["patient_name"] = (
                        blocked_patient
                    )

                    slot_data["appointment_notes"] = (
                        getattr(
                            blocked,
                            "notes",
                            "",
                        )
                        or ""
                    )

                    if (
                        existing_follow_up
                        or getattr(
                            blocked,
                            "is_follow_up",
                            False,
                        )
                    ):
                        slot_data["reason"] = (
                            "موعد إعادة كشف محجوز"
                        )
                    else:
                        slot_data["reason"] = (
                            "موعد كشف محجوز"
                        )

                slots.append(slot_data)

                current_minutes += (
                    schedule.appointment_duration
                )

        follow_up_days.append(
            {
                "date":
                    current_date,
                "weekday":
                    weekday,
                "weekday_name":
                    arabic_weekdays.get(
                        weekday,
                        current_date.strftime("%A"),
                    ),
                "available":
                    bool(schedule),
                "slots":
                    slots,
            }
        )

    pending_count = sum(
        1
        for appointment in appointments
        if (
            appointment.status
            == Appointment.Status.PENDING
            and not appointment.is_follow_up
        )
    )

    return render(
        request,
        "accounts/doctor_appointments.html",
        {
            "doctor":
                doctor,

            "appointments":
                appointments,

            "normal_appointments":
                normal_appointments,

            "active_normal_appointments":
                active_normal_appointments,

            "past_normal_appointments":
                past_normal_appointments,

            "follow_up_appointments":
                follow_up_appointments,

            "active_follow_up_appointments":
                active_follow_up_appointments,

            "past_follow_up_appointments":
                past_follow_up_appointments,

            "week_appointments":
                week_appointments,

            "week_days":
                week_days,

            "appointment_filter_days":
                appointment_filter_days,

            "week_start":
                week_start,

            "week_end":
                week_end,

            "today":
                today,

            "now":
                now,

            "follow_up_days":
                follow_up_days,

            "next_appointment":
                next_appointment,

            "next_follow_up_appointment":
                next_follow_up_appointment,

            "pending_count":
                pending_count,
        },
    )


@login_required
def update_appointment_status(
    request,
    appointment_id
):

    if request.user.role != User.Role.DOCTOR:
        return redirect("dashboard")

    appointment = get_object_or_404(
        Appointment.objects.select_related(
            "doctor",
            "doctor__user",
            "patient"
        ),
        id=appointment_id,
        doctor__user=request.user
    )

    if request.method != "POST":
        return redirect(
            "doctor_appointments"
        )

    new_status = request.POST.get(
        "status"
    )

    if (
        appointment.status
        != Appointment.Status.PENDING
    ):
        return redirect(
            "doctor_appointments"
        )

    doctor_name = (
        appointment.doctor.user.get_full_name()
        or
        appointment.doctor.user.username
    )

    if (
        new_status
        ==
        Appointment.Status.ACCEPTED
    ):

        appointment.status = (
            Appointment.Status.ACCEPTED
        )

        appointment.save(
            update_fields=["status"]
        )

        create_user_notification(
            user=appointment.patient,

            title="تم قبول الحجز ✅",

            message=(
                f"تم قبول موعدك مع الدكتور "
                f"{doctor_name} "
                f"يوم {appointment.date} "
                f"الساعة {appointment.time}."
            ),

            url=(
                reverse(
                    "my_appointments"
                )
                + "?tab=appointments&status=accepted"
            )
        )

    elif (
        new_status
        ==
        Appointment.Status.REJECTED
    ):

        appointment.status = (
            Appointment.Status.REJECTED
        )

        appointment.save(
            update_fields=["status"]
        )

        create_user_notification(
            user=appointment.patient,

            title="تم رفض الحجز ❌",

            message=(
                f"تم رفض موعدك مع الدكتور "
                f"{doctor_name} "
                f"يوم {appointment.date} "
                f"الساعة {appointment.time}."
            ),

            url=(
                reverse(
                    "my_appointments"
                )
                + "?tab=appointments&status=rejected"
            )
        )

    return redirect(
        "doctor_appointments"
    )


@login_required
def mark_attendance(
    request,
    appointment_id
):

    if request.user.role != User.Role.DOCTOR:
        return redirect("dashboard")

    appointment = get_object_or_404(
        Appointment.objects.select_related(
            "doctor",
            "patient"
        ),
        id=appointment_id,
        doctor__user=request.user
    )

    if request.method != "POST":
        return redirect(
            "doctor_appointments"
        )

    if (
        appointment.status
        != Appointment.Status.ACCEPTED
    ):
        return redirect(
            "doctor_appointments"
        )

    current_tz = (
        timezone.get_current_timezone()
    )

    appointment_datetime = (
        timezone.make_aware(
            datetime.combine(
                appointment.date,
                appointment.time,
            ),
            current_tz,
        )
    )

    if timezone.localtime() < appointment_datetime:

        messages.error(
            request,
            "لا يمكن تسجيل الحضور أو الغياب قبل موعد الكشف.",
        )

        return redirect(
            "doctor_appointments"
        )

    attendance = request.POST.get(
        "attendance"
    )

    if attendance not in [
        Appointment.Attendance.ATTENDED,
        Appointment.Attendance.ABSENT,
    ]:
        return redirect(
            "doctor_appointments"
        )

    appointment.attendance = attendance

    appointment.save(
        update_fields=["attendance"]
    )

    if (
        attendance
        ==
        Appointment.Attendance.ATTENDED
    ):

        create_user_notification(
            user=appointment.patient,

            title="تم تسجيل حضورك ✅",

            message=(
                "تم تسجيل حضورك في موعدك "
                "مع الدكتور. يمكنك الآن "
                "تقييم الدكتور."
            ),

            url=reverse(
                "my_appointments"
            )
        )

    else:

        create_user_notification(
            user=appointment.patient,

            title="تم تسجيل الغياب",

            message=(
                "تم تسجيل عدم حضورك "
                "للموعد المحدد."
            ),

            url=reverse(
                "my_appointments"
            )
        )

    return redirect(
        "doctor_appointments"
    )


@login_required
def rate_doctor(
    request,
    appointment_id
):

    if request.user.role != User.Role.PATIENT:
        return redirect("dashboard")

    appointment = get_object_or_404(
        Appointment.objects.select_related(
            "doctor",
            "doctor__user",
            "patient"
        ),
        id=appointment_id,
        patient=request.user
    )

    if not appointment.can_rate:
        return redirect(
            "my_appointments"
        )

    if request.method != "POST":
        return redirect(
            "my_appointments"
        )

    try:
        rating = int(
            request.POST.get(
                "rating",
                "0"
            )
        )
    except (
        ValueError,
        TypeError
    ):
        rating = 0

    comment = request.POST.get(
        "comment",
        ""
    ).strip()

    if rating < 1 or rating > 5:
        return redirect(
            "my_appointments"
        )

    if DoctorReview.objects.filter(
        appointment=appointment
    ).exists():
        return redirect(
            "my_appointments"
        )

    DoctorReview.objects.create(
        doctor=appointment.doctor,
        patient=request.user,
        appointment=appointment,
        rating=rating,
        comment=comment,
    )

    appointment.is_rated = True

    appointment.save(
        update_fields=["is_rated"]
    )

    return redirect(
        "my_appointments"
    )


@login_required
def create_follow_up(
    request,
    appointment_id
):

    if request.user.role != User.Role.DOCTOR:
        return redirect("dashboard")

    original_appointment = get_object_or_404(
        Appointment.objects.select_related(
            "doctor",
            "patient"
        ),
        id=appointment_id,
        doctor__user=request.user,
    )

    if request.method != "POST":
        return redirect(
            "doctor_appointments"
        )

    if (
        original_appointment.status
        != Appointment.Status.ACCEPTED
    ):

        messages.error(
            request,
            "الحجز الأصلي يجب أن يكون مقبولًا."
        )

        return redirect(
            "doctor_appointments"
        )

    if (
        original_appointment.attendance
        != Appointment.Attendance.ATTENDED
    ):

        messages.error(
            request,
            "يجب تسجيل حضور المريض في الكشف الأصلي أولًا."
        )

        return redirect(
            "doctor_appointments"
        )

    date_value = request.POST.get(
        "date",
        ""
    ).strip()

    time_value = request.POST.get(
        "time",
        ""
    ).strip()

    notes = request.POST.get(
        "notes",
        ""
    ).strip()

    if not date_value:

        messages.error(
            request,
            "لم يتم اختيار تاريخ إعادة الكشف."
        )

        return redirect(
            "doctor_appointments"
        )

    if not time_value:

        messages.error(
            request,
            "لم يتم اختيار ساعة إعادة الكشف."
        )

        return redirect(
            "doctor_appointments"
        )

    try:

        selected_date = datetime.strptime(
            date_value,
            "%Y-%m-%d"
        ).date()

        selected_time = datetime.strptime(
            time_value,
            "%H:%M"
        ).time()

    except ValueError:

        messages.error(
            request,
            "التاريخ أو الساعة غير صحيحة."
        )

        return redirect(
            "doctor_appointments"
        )

    now = timezone.localtime()

    current_tz = (
        timezone.get_current_timezone()
    )

    today = timezone.localdate()

    if selected_date < today:

        messages.error(
            request,
            "لا يمكن اختيار تاريخ قديم."
        )

        return redirect(
            "doctor_appointments"
        )

    selected_datetime = (
        timezone.make_aware(
            datetime.combine(
                selected_date,
                selected_time,
            ),
            current_tz,
        )
    )

    if selected_datetime <= now:

        messages.error(
            request,
            "لا يمكن اختيار موعد إعادة كشف في وقت مضى."
        )

        return redirect(
            "doctor_appointments"
        )

    doctor = (
        original_appointment.doctor
    )

    schedule = (
        DoctorSchedule.objects
        .filter(
            doctor=doctor,
            weekday=selected_date.weekday(),
            is_active=True,
        )
        .first()
    )

    if not schedule:

        messages.error(
            request,
            "الدكتور لا يعمل في اليوم الذي اخترته."
        )

        return redirect(
            "doctor_appointments"
        )

    if not (
        schedule.start_time
        <= selected_time
        <
        schedule.end_time
    ):

        messages.error(
            request,
            "الساعة المختارة خارج مواعيد عمل الدكتور."
        )

        return redirect(
            "doctor_appointments"
        )

    minutes_from_start = (
        (
            selected_time.hour * 60
            +
            selected_time.minute
        )
        -
        (
            schedule.start_time.hour * 60
            +
            schedule.start_time.minute
        )
    )

    if (
        minutes_from_start < 0
        or
        minutes_from_start
        %
        schedule.appointment_duration
        != 0
    ):

        messages.error(
            request,
            "الساعة المختارة ليست ضمن مواعيد الحجز المتاحة."
        )

        return redirect(
            "doctor_appointments"
        )

    already_booked = (
        Appointment.objects
        .filter(
            doctor=doctor,
            date=selected_date,
            time=selected_time,
            status__in=[
                Appointment.Status.PENDING,
                Appointment.Status.ACCEPTED,
            ],
        )
        .exists()
    )

    follow_up_already_booked = (
        FollowUpAppointment.objects
        .filter(
            doctor=doctor,
            date=selected_date,
            time=selected_time,
        )
        .exists()
    )

    if (
        already_booked
        or
        follow_up_already_booked
    ):

        messages.error(
            request,
            "هذا الموعد محجوز بالفعل، لا يمكن إنشاء إعادة كشف عليه.",
        )

        return redirect(
            "doctor_appointments"
        )

    try:

        with transaction.atomic():

            locked_conflict = (
                Appointment.objects
                .select_for_update()
                .filter(
                    doctor=doctor,
                    date=selected_date,
                    time=selected_time,
                    status__in=[
                        Appointment.Status.PENDING,
                        Appointment.Status.ACCEPTED,
                    ],
                )
                .exists()
            )

            locked_follow_up = (
                FollowUpAppointment.objects
                .select_for_update()
                .filter(
                    doctor=doctor,
                    date=selected_date,
                    time=selected_time,
                )
                .exists()
            )

            if (
                locked_conflict
                or
                locked_follow_up
            ):

                messages.error(
                    request,
                    "هذا الموعد تم حجزه للتو، اختر موعدًا آخر.",
                )

                return redirect(
                    "doctor_appointments"
                )

            appointment = (
                Appointment.objects.create(
                    patient=
                        original_appointment.patient,

                    doctor=doctor,

                    date=selected_date,

                    time=selected_time,

                    status=
                        Appointment.Status.ACCEPTED,

                    attendance=
                        Appointment.Attendance.NOT_MARKED,

                    is_rated=False,

                    notes=notes,

                    is_follow_up=True,

                    parent_appointment=
                        original_appointment,
                )
            )

            FollowUpAppointment.objects.create(
                original_appointment=
                    original_appointment,

                doctor=doctor,

                patient=
                    original_appointment.patient,

                date=selected_date,

                time=selected_time,

                notes=notes,
            )

    except Exception as error_object:

        print(
            "FOLLOW UP CREATION ERROR:",
            repr(error_object)
        )

        messages.error(
            request,
            "حدث خطأ أثناء إنشاء إعادة الكشف. راجع Terminal لمعرفة السبب.",
        )

        return redirect(
            "doctor_appointments"
        )

    doctor_name = (
        doctor.user.get_full_name()
        or doctor.user.username
    )

    notification_message = (
        f"حدد الدكتور {doctor_name} موعد إعادة كشف لك يوم "
        f"{appointment.date} الساعة {appointment.time}."
    )

    if notes:

        notification_message += (
            f" تفاصيل إعادة الكشف: {notes}"
        )

    try:

        create_user_notification(
            user=
                original_appointment.patient,

            title=
                "🔄 إعادة كشف جديدة",

            message=
                notification_message,

            url=
                reverse(
                    "my_appointments"
                )
                +
                "?tab=followup",
        )

    except Exception as error_object:

        print(
            "FOLLOW UP NOTIFICATION ERROR:",
            repr(error_object)
        )

    messages.success(
        request,
        "✅ تم إضافة إعادة الكشف بنجاح.",
    )

    return redirect(
        "doctor_appointments"
    )


@login_required
def cancel_appointment(
    request,
    appointment_id
):

    if request.user.role != User.Role.PATIENT:
        return redirect(
            "dashboard"
        )

    appointment = get_object_or_404(
        Appointment.objects.select_related(
            "doctor",
            "doctor__user",
            "patient"
        ),
        id=appointment_id,
        patient=request.user
    )

    if request.method == "POST":

        if (
            appointment.status
            ==
            Appointment.Status.PENDING
        ):

            appointment.status = (
                Appointment.Status.CANCELLED
            )

            appointment.save(
                update_fields=[
                    "status"
                ]
            )

            patient_name = (
                request.user.get_full_name()
                or
                request.user.username
            )

            create_user_notification(
                user=
                    appointment.doctor.user,

                title=
                    "تم إلغاء الحجز ❌",

                message=(
                    f"قام المريض {patient_name} "
                    f"بإلغاء موعد يوم "
                    f"{appointment.date} "
                    f"الساعة {appointment.time}."
                ),

                url=reverse(
                    "doctor_appointments"
                )
            )

    return redirect(
        "my_appointments"
    )


@login_required
def notifications(request):

    notifications_list = list(
        Notification.objects
        .filter(
            user=request.user
        )
        .order_by(
            "-created_at"
        )
    )

    unread_notifications = list(
        Notification.objects
        .filter(
            user=request.user,
            is_read=False
        )
        .order_by(
            "-created_at"
        )
    )

    message_notifications = []

    accepted_notifications = []

    rejected_notifications = []

    follow_up_notifications = []

    for notification in notifications_list:

        title = (
            notification.title
            or
            ""
        ).lower()

        if (
            "إعادة كشف" in title
            or
            "follow up" in title
            or
            "follow-up" in title
        ):

            follow_up_notifications.append(
                notification
            )

        elif (
            "رسالة" in title
            or
            "message" in title
        ):

            message_notifications.append(
                notification
            )

        elif (
            "رفض" in title
            or
            "مرفوض" in title
            or
            "rejected" in title
        ):

            rejected_notifications.append(
                notification
            )

        elif (
            "حجز" in title
            or
            "قبول" in title
            or
            "مقبول" in title
            or
            "appointment" in title
            or
            "تقييم" in title
        ):

            accepted_notifications.append(
                notification
            )

        else:

            accepted_notifications.append(
                notification
            )

    unread_count = len(
        unread_notifications
    )

    Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(
        is_read=True
    )

    return render(
        request,
        "accounts/notifications.html",
        {
            "notifications":
                notifications_list,

            "unread_notifications":
                unread_notifications,

            "message_notifications":
                message_notifications,

            "accepted_notifications":
                accepted_notifications,

            "rejected_notifications":
                rejected_notifications,

            "follow_up_notifications":
                follow_up_notifications,

            "unread_count":
                unread_count,
        }
    )


@login_required
def save_fcm_token(request):

    if request.method != "POST":

        return JsonResponse(
            {
                "success":
                    False,
                "error":
                    "POST request required."
            },
            status=405
        )

    token = request.POST.get(
        "token",
        ""
    ).strip()

    if not token:

        return JsonResponse(
            {
                "success":
                    False,
                "error":
                    "FCM token is missing."
            },
            status=400
        )

    FCMToken.objects.update_or_create(
        token=token,
        defaults={
            "user":
                request.user
        }
    )

    return JsonResponse(
        {
            "success":
                True
        }
    )


def firebase_messaging_sw(request):

    js = (
        'importScripts('
        '"https://www.gstatic.com/firebasejs/10.12.2/'
        'firebase-app-compat.js"'
        ');\n'

        'importScripts('
        '"https://www.gstatic.com/firebasejs/10.12.2/'
        'firebase-messaging-compat.js"'
        ');\n\n'

        'firebase.initializeApp({\n'

        '  apiKey: '
        '"AIzaSyD3SZ1Y5yIjPm4udN_sUJNRkEENpPJyGwQ",\n'

        '  authDomain: '
        '"my-doctor-1eb38.firebaseapp.com",\n'

        '  projectId: '
        '"my-doctor-1eb38",\n'

        '  storageBucket: '
        '"my-doctor-1eb38.firebasestorage.app",\n'

        '  messagingSenderId: '
        '"510392843241",\n'

        '  appId: '
        '"1:510392843241:web:fc70e07682089793a02978",\n'

        '  measurementId: '
        '"G-EW3G0PL121"\n'

        '});\n\n'

        'const messaging = firebase.messaging();\n\n'

        'messaging.onBackgroundMessage('
        'function(payload) {\n'

        '  const notification = '
        'payload.notification || {};\n'

        '  const title = '
        'notification.title || "MY DOCTOR";\n'

        '  const body = '
        'notification.body || "لديك إشعار جديد";\n'

        '  const options = {\n'

        '    body: body,\n'

        '    data: payload.data || {}\n'

        '  };\n'

        '  self.registration.showNotification('
        'title, options'
        ');\n'

        '});\n\n'

        'self.addEventListener('
        '"notificationclick", '
        'function(event) {\n'

        '  event.notification.close();\n'

        '  const data = '
        'event.notification.data || {};\n'

        '  const targetUrl = '
        'data.url || "/accounts/dashboard/";\n\n'

        '  event.waitUntil(\n'

        '    clients.matchAll({\n'

        '      type: "window",\n'

        '      includeUncontrolled: true\n'

        '    }).then(function(clientList) {\n'

        '      for (const client of clientList) {\n'

        '        if ("focus" in client) {\n'

        '          if ("navigate" in client) {\n'

        '            client.navigate(targetUrl);\n'

        '          }\n'

        '          return client.focus();\n'

        '        }\n'

        '      }\n\n'

        '      if (clients.openWindow) {\n'

        '        return clients.openWindow(targetUrl);\n'

        '      }\n'

        '    })\n'

        '  );\n'

        '});\n\n'

        'self.addEventListener('
        '"activate", '
        'function(event) {\n'

        '  event.waitUntil('
        'self.clients.claim()'
        ');\n'

        '});\n\n'

        'self.addEventListener('
        '"install", '
        'function() {\n'

        '  self.skipWaiting();\n'

        '});\n'
    )

    return HttpResponse(
        js,
        content_type="application/javascript"
    )