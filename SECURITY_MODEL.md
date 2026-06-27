# Security Model

This document outlines the security architecture and threat model for the SOC Dashboard. Because this application processes sensitive enterprise security logs, maintaining strong security boundaries is paramount.

---

## 🔐 Authentication & Session Handling

- **Framework**: Handled entirely by Django's `contrib.auth` system.
- **Passwords**: Hashed using Django's default PBKDF2 algorithm with a SHA256 hash. Passwords are never stored or logged in plaintext.
- **Sessions**: Session IDs are stored in HTTP-only, secure cookies. Session hijacking is mitigated by expiring idle sessions and regenerating session keys on login/logout.

---

## 🛡️ Authorization & Role-Based Access Control (RBAC)

Access to the system is strictly limited to authenticated personnel. Two primary roles are defined:

1. **Analyst (Standard User)**:
   - Can upload `.evtx` files.
   - Can view the dashboard, alerts, and incident history.
   - Cannot delete historical records or access system settings.
2. **Super Administrator**:
   - Has all Analyst permissions.
   - Has access to the Django Admin panel.
   - Can manage (create/suspend) user accounts.
   - Can purge old data manually.

*Future Role*: **SOC Manager** (Read-only aggregate metrics, cannot view raw log contents).

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
