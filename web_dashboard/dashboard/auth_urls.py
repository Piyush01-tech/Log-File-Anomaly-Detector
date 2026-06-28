"""
dashboard/auth_urls.py — Phase 9A
====================================
URL configuration for authentication routes.

URL PREFIX: /auth/ (configured in web_dashboard/urls.py)

ROUTES:
  /auth/login/            → CustomLoginView
  /auth/logout/           → CustomLogoutView
  /auth/register/         → RegistrationView
  /auth/profile/          → ProfileView
  /auth/password-change/  → CustomPasswordChangeView

NAMESPACE: 'auth'

DESIGN DECISIONS:
  - Separate URL module keeps auth routing decoupled from
    dashboard feature routes (dashboard/urls.py).
  - URL namespace 'auth' allows template references like
    {% url 'auth:login' %} without collision.
  - Matches LOGIN_URL = "/auth/login/" configured in settings.py.
"""

from django.urls import path

from . import auth_views

app_name = "auth"

urlpatterns = [
    # --- Authentication ---
    path(
        "login/",
        auth_views.CustomLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        auth_views.CustomLogoutView.as_view(),
        name="logout",
    ),
    path(
        "register/",
        auth_views.RegistrationView.as_view(),
        name="register",
    ),

    # --- Account Management ---
    path(
        "profile/",
        auth_views.ProfileView.as_view(),
        name="profile",
    ),
    path(
        "password-change/",
        auth_views.CustomPasswordChangeView.as_view(),
        name="password_change",
    ),
]
