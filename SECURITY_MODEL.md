# Security Model

This document outlines the security architecture and threat model for the SOC Dashboard. Because this application processes sensitive enterprise security logs, maintaining strong security boundaries is paramount.

---

## 🔐 Authentication & Session Handling (Phase 9A — Implemented)

- **Framework**: Handled entirely by Django's `contrib.auth` system via extended class-based views (`CustomLoginView`, `CustomLogoutView`, `RegistrationView`, `ProfileView`, `CustomPasswordChangeView`).
- **Passwords**: Hashed using Django's default PBKDF2 algorithm with SHA256. Password hashers are explicitly configured in `settings.py` (`PBKDF2`, `PBKDF2SHA1`, `Argon2`, `BCryptSHA256` in order of preference). Passwords are never stored or logged in plaintext.
- **Password Validation**: Four validators enforced on registration and password change:
  - `UserAttributeSimilarityValidator` — Prevents passwords similar to username/email.
  - `MinimumLengthValidator` — Enforces minimum 8 characters.
  - `CommonPasswordValidator` — Rejects common passwords.
  - `NumericPasswordValidator` — Rejects all-numeric passwords.
- **Sessions**:
  - Session IDs stored in HTTP-only cookies (`SESSION_COOKIE_HTTPONLY = True`).
  - Secure cookies in production (`SESSION_COOKIE_SECURE = not DEBUG`).
  - SameSite policy set to `Lax` for CSRF complement.
  - Default session age: 24 hours (`SESSION_COOKIE_AGE`), configurable via env var.
  - "Remember Me" checkbox: unchecked = browser session only; checked = full `SESSION_COOKIE_AGE`.
  - `SESSION_SAVE_EVERY_REQUEST = True` refreshes expiry on each request.
- **Idle Session Timeout**: `SessionSecurityMiddleware` tracks `_last_activity` timestamp per session. Sessions idle longer than `SESSION_IDLE_TIMEOUT` (default 30 minutes) are flushed and redirected to login.
- **Security Headers**: `SessionSecurityMiddleware` adds to all responses:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`
- **Audit Trail**: All LOGIN/LOGOUT events are recorded in the `AuditLog` model with user identity, IP address (via `X-Forwarded-For` or `REMOTE_ADDR`), and timestamp.
- **Registration**: Users self-register with the ANALYST role (default from `UserManager`). Username and email uniqueness are validated at the form level.
- **CSRF Protection**: All POST forms include `{% csrf_token %}`. `CSRF_COOKIE_SECURE = not DEBUG` enforces HTTPS-only CSRF cookies in production.

---

## 🛡️ Authorization & Role-Based Access Control (Phase 9B — Implemented)

Access to the system is strictly limited to authenticated personnel. Authorization is enforced using Django's built-in **Groups and Permissions** framework, decoupled from hardcoded checks to allow for enterprise extensibility.

Two primary groups are configured via the `setup_rbac` management command:

1. **Analyst (Standard User)**:
   - *Permissions*: `upload_evtx`, `view_own_uploads`, `view_own_incidents`, `edit_own_profile`.
   - *Data Isolation*: The `AnalystOwnerQuerysetMixin` and `OwnershipMixin` enforce strict data isolation. Analysts can only view `AnalysisJob`, `Anomaly`, and `AuditLog` records where they are the owner. Any attempt to access another user's records via URL manipulation results in a 403 Forbidden.
   - Cannot access the Django Admin panel.

2. **Super Administrator**:
   - *Permissions*: All Analyst permissions + `dashboard_full_access`, `view_all_logs`, `view_all_incidents`, `manage_users`, `disable_users`, `delete_users`, `promote_users`, `view_system_stats`, `manage_rag`, `manage_settings`.
   - *Data Isolation*: Admins bypass owner checks and can view all data system-wide.
   - *Admin Panel*: Access to `/admin/` is strictly gated by the `SessionSecurityMiddleware`, which requires the `dashboard_full_access` permission (providing defense-in-depth beyond Django's `is_staff` check).
   - Can manage users (promote, demote, disable) via custom admin actions.

**Group Syncronization**: The legacy `User.role` field is preserved for quick lookups, but group membership is what actually drives permissions. A `post_save` signal on the `User` model automatically syncs the `role` field to the correct Django Group to ensure integrity across all user creation paths (registration, createsuperuser, admin).

*Future Role Extensibility*: New roles (e.g., SOC Manager) can be added simply by creating a new Group in the Django admin panel and assigning existing custom permissions—no code changes required.

---

## 📥 Input Validation & Upload Security

The system accepts file uploads (`.evtx`), which is a common vector for attack.

- **File Type Validation**: Django validates that the MIME type and file extension strictly match `.evtx`.
- **Size Limits**: `DATA_UPLOAD_MAX_MEMORY_SIZE` and `FILE_UPLOAD_MAX_MEMORY_SIZE` will be strictly enforced in `settings.py` (e.g., max 100MB per file) to prevent Denial of Service (DoS) via disk/memory exhaustion.
- **Parsing Security**: The `python-evtx` library parses the binary files. If a malformed file causes an exception, the Flask API will catch it and return a standard `500` error without crashing the microservice.

---

## 🕸️ Network Security Boundaries

- **Internal API**: The Flask ML API is completely isolated from the internet. It does not accept requests from users. It only accepts requests originating from the Django backend.
- **CSRF Protection**: All POST requests made from the browser to Django (including the file upload form) require a valid Cross-Site Request Forgery (CSRF) token.

---

## 🎯 Threat Model Summary

| Threat | Mitigation |
|--------|------------|
| **Brute Force Login** | Django-axes (to be implemented) will lock accounts after 5 failed attempts. |
| **Malicious File Upload** | Extension/MIME checking; Flask processes files synchronously and handles parse failures gracefully. |
| **SQL Injection (SQLi)** | Django ORM is used exclusively. No raw SQL queries are permitted. |
| **Cross-Site Scripting (XSS)** | Django templates auto-escape all context variables. |
| **Data Exfiltration** | The ML engine has no outbound internet access. It cannot "call home." |
| **Unauthorized ML API Access** | Flask API will require a PSK (Pre-Shared Key) sent via headers by Django. |
