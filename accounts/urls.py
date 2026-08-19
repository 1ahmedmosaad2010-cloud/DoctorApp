from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [

    # =====================================================
    # HOME
    # =====================================================

    path(
        "",
        views.home,
        name="home",
    ),


    # =====================================================
    # AUTH
    # =====================================================

    path(
        "register/",
        views.register,
        name="register",
    ),

    path(
        "login/",
        views.login_view,
        name="login",
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(
            next_page="login",
        ),
        name="logout",
    ),


    # =====================================================
    # DASHBOARD
    # =====================================================

    path(
        "dashboard/",
        views.dashboard,
        name="dashboard",
    ),


    # =====================================================
    # DOCTORS
    # =====================================================

    path(
        "doctors/",
        views.doctors,
        name="doctors",
    ),

    path(
        "doctor/<int:doctor_id>/reviews/",
        views.doctor_reviews,
        name="doctor_reviews",
    ),


    # =====================================================
    # DOCTOR SCHEDULE
    # =====================================================

    path(
        "doctor/schedule/",
        views.doctor_schedule,
        name="doctor_schedule",
    ),


    # =====================================================
    # PATIENT MESSAGES
    # =====================================================

    path(
        "messages/",
        views.patient_messages,
        name="patient_messages",
    ),


    # =====================================================
    # PATIENT CHAT WITH DOCTOR
    # =====================================================

    path(
        "chat/<int:doctor_id>/",
        views.chat,
        name="chat",
    ),


    # =====================================================
    # DOCTOR MESSAGES
    # =====================================================

    path(
        "doctor/messages/",
        views.doctor_messages,
        name="doctor_messages",
    ),


    # =====================================================
    # DOCTOR CHAT WITH PATIENT
    # =====================================================

    path(
        "doctor/chat/<int:user_id>/",
        views.doctor_chat,
        name="doctor_chat",
    ),


    # =====================================================
    # BOOK APPOINTMENT
    # =====================================================

    path(
        "book/<int:doctor_id>/",
        views.book_appointment,
        name="book_appointment",
    ),


    # =====================================================
    # PATIENT APPOINTMENTS
    # =====================================================

    path(
        "appointments/",
        views.my_appointments,
        name="my_appointments",
    ),


    # =====================================================
    # DOCTOR APPOINTMENTS
    # =====================================================

    path(
        "doctor/appointments/",
        views.doctor_appointments,
        name="doctor_appointments",
    ),


    # =====================================================
    # ACCEPT / REJECT APPOINTMENT
    # =====================================================

    path(
        "appointment/<int:appointment_id>/status/",
        views.update_appointment_status,
        name="update_appointment_status",
    ),


    # =====================================================
    # ATTENDANCE
    # =====================================================

    path(
        "appointment/<int:appointment_id>/attendance/",
        views.mark_attendance,
        name="mark_attendance",
    ),


    # =====================================================
    # RATE DOCTOR
    # =====================================================

    path(
        "appointment/<int:appointment_id>/rate/",
        views.rate_doctor,
        name="rate_doctor",
    ),


    # =====================================================
    # FOLLOW UP APPOINTMENT
    # =====================================================

    path(
        "appointment/<int:appointment_id>/follow-up/",
        views.create_follow_up,
        name="create_follow_up",
    ),


    # =====================================================
    # CANCEL APPOINTMENT
    # =====================================================

    path(
        "appointment/<int:appointment_id>/cancel/",
        views.cancel_appointment,
        name="cancel_appointment",
    ),


    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    path(
        "notifications/",
        views.notifications,
        name="notifications",
    ),


    # =====================================================
    # SAVE FCM TOKEN
    # =====================================================

    path(
        "save-fcm-token/",
        views.save_fcm_token,
        name="save_fcm_token",
    ),


    # =====================================================
    # FIREBASE SERVICE WORKER
    # =====================================================

    path(
        "firebase-messaging-sw.js",
        views.firebase_messaging_sw,
        name="firebase_messaging_sw",
    ),
]