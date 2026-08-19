from pathlib import Path

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.views.static import serve


BASE_DIR = Path(__file__).resolve().parent.parent


urlpatterns = [
    path(
        "",
        RedirectView.as_view(
            url="/accounts/",
            permanent=False,
        ),
        name="root",
    ),

    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "accounts/",
        include("accounts.urls"),
    ),

    path(
        "firebase-messaging-sw.js",
        serve,
        {
            "document_root": BASE_DIR,
            "path": "firebase-messaging-sw.js",
        },
    ),
]