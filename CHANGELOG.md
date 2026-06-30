# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project loosely adheres to Semantic Versioning as it progresses through development phases.

---

## [0.10.1] - 2026-07-01 — RC Stabilization

### Fixed
- Navbar search bar is now fully functional and wired to the alerts search page.
- Notification bell is now functional, displaying a badge with the count of critical and high alerts.
- Notification bell dropdown now shows a summary of critical and high alerts with links to filter them.
- Fixed an issue where the analytics API fetch could fail if the dashboard was not mounted at the root URL (now uses `data-api-url` from the template).
- Added `navbar_alert_count`, `navbar_critical_count`, and `navbar_high_count` to global context processors.
- Added custom SOC branding (site header, title, index title) to the Django admin panel in `admin.py`.

## [0.10.0] - 2026-07-01 — Phase 12: Analytics & Visualization Framework

### Completed Phase
- **Phase 12**: Analytics & Visualization Framework

### Added
- `web_dashboard/dashboard/analytics.py`: New backend API module with `analytics_api` endpoint aggregating all chart data via Django ORM (severity distribution, anomaly trends, login trends, top event IDs, top targeted hosts, analysis status, recent activity, system health). Data is scoped by user role.
- `web_dashboard/dashboard/static/dashboard/js/theme.js`: New frontend module tracking the active CSS theme, extracting `--soc-*` CSS variables to a semantic palette for Chart.js. Uses `MutationObserver` to respond to theme toggles.
- `web_dashboard/dashboard/static/dashboard/js/charts.js`: New Chart.js factory encapsulating SOC-styled `createDoughnut`, `createLine`, and `createBar` methods with custom tooltip and legend configurations.
- `web_dashboard/dashboard/static/dashboard/js/dashboard.js`: Analytics page orchestrator. Fetches `/api/analytics/`, passes data to `SOCCharts`, manages skeleton loaders, handles empty states, and re-renders on theme changes.
- `web_dashboard/dashboard/templates/dashboard/includes/_chart_card.html`: Reusable chart container template with built-in loading skeletons and empty states.

### Modified
- `web_dashboard/dashboard/urls.py`: Added `/api/analytics/` route.
- `web_dashboard/dashboard/views.py`: Updated docstrings and exports.
- `web_dashboard/dashboard/templates/dashboard/home.html`: Replaced placeholder sections with actual Chart.js visualizations, system health summary cards, and a recent activity timeline. Added Chart.js CDN and custom JS modules.
- `web_dashboard/dashboard/templates/dashboard/base.html`: Bumped CSS cache version `?v=13`.
- `web_dashboard/dashboard/static/dashboard/css/main.css`: Added styles for chart cards, skeleton shimmer animations, inline empty states, system health metrics, and the activity timeline. Adjusted responsive behavior for mobile.

### Architecture Changes
- The visualization backend serves a single, aggregated JSON payload rather than requiring multiple HTTP round-trips for each chart.
- A decoupled, event-driven JS architecture was implemented. The chart factory (`charts.js`) relies on semantic colors provided by `theme.js`, ensuring charts perfectly match the existing CSS variable design system without hardcoding hex values.

### Database Changes
- None.

### Security Changes
- The `/api/analytics/` endpoint enforces the same user-isolation rules as standard dashboard views: analysts receive their own data only, while admins receive system-wide data.

### Documentation Updated
- `PROJECT_CONTEXT.md` — Version bump to v0.10.0, Phase 12 completed.
- `ROADMAP.md` — Phase 12 marked complete.
- `CHANGELOG.md` — This entry.

### Summary
The dashboard now features a comprehensive analytics layer. Eight dynamic visualizations provide insights into security trends, login failures, top event IDs, and targeted hosts. The implementation tightly integrates with the Phase 11C theming engine, ensuring dark/light mode transitions are seamless.

### Future Work
- Phase 13: RAG Knowledge Base Setup.

## [0.9.1] - 2026-06-29 — Phase 11C: UI/UX Redesign

### Completed Phase
- **Phase 11C**: UI/UX Redesign

### Modified
- `web_dashboard/dashboard/static/dashboard/css/main.css`: Completely overhauled with a premium CSS variable system for colors (dark/light themes) and 8px spacing utility classes.
- `web_dashboard/dashboard/static/dashboard/js/main.js`: Added JS interactivity for theme toggling via `localStorage` and responsive sidebar collapse/expand.
- `web_dashboard/dashboard/templates/dashboard/base.html`: Refactored layout shell to include a fixed top navbar (search, theme toggle, notifications) and fixed/offcanvas sidebar.
- `web_dashboard/dashboard/templates/dashboard/includes/_sidebar.html`: Made sidebar responsive, collapsible on desktop, offcanvas on mobile.
- Component refactoring: Upgraded `_stats_card.html`, `_status_badge.html`, `_severity_badge.html`, `_empty_state.html`, `_table_filter.html`, `_pagination.html` to align with the new design tokens.
- Page Template Redesign: Modernized `home.html`, `upload.html`, `alerts.html`, `analysis_detail.html`, `analysis_history.html`, `login.html`, `register.html`, `password_change.html`, and `profile.html` with `.border-0`, `.shadow-sm`, and custom layout components ensuring a professional cybersecurity layout.

### Architecture Changes
- Client-side theme switching logic implemented via `[data-theme="dark"]` attribute on `<html>`.

### Summary
The dashboard's frontend has been significantly upgraded. The layout is now highly responsive, visually appealing (Sentinel/Splunk inspired), and incorporates a robust design token system (CSS variables) to support advanced theming. All pre-existing business logic, backend URLs, permissions, and models remain completely intact.

---

## [0.9.0] - 2026-06-29 — Phase 11B: Dashboard Features

### Completed Phase
- **Phase 11B**: Dashboard Features

### Added
- `web_dashboard/dashboard/views.py`: Added `AlertsListView` (paginated anomaly list with search by computer name/filename, severity filter, user isolation via `job__user` relationship) and `AlertDetailView` (single anomaly incident detail with ownership check via parent job, prev/next navigation, audit logging).
- `web_dashboard/dashboard/templates/dashboard/alerts.html`: Alerts list page with severity summary cards, search/filter bar, responsive table, reusable badge includes, pagination, and empty states (filtered vs no-data).
- `web_dashboard/dashboard/templates/dashboard/alert_detail.html`: Incident detail page with severity-aware banner, metadata cards, full ML feature grid, parent job link, prev/next anomaly navigation, and RAG explanation placeholder.
- `web_dashboard/dashboard/templates/dashboard/includes/_pagination.html`: Reusable pagination component with query string preservation, page info text, first/prev/next/last navigation, and ellipsis for large page ranges.
- `web_dashboard/dashboard/templates/dashboard/includes/_status_badge.html`: Reusable status badge for `AnalysisJob.Status` values (COMPLETED, FAILED, RUNNING, PENDING). Replaces duplicated badge HTML across 4+ templates.
- `web_dashboard/dashboard/templates/dashboard/includes/_severity_badge.html`: Reusable severity badge for `Anomaly.Severity` values (CRITICAL, HIGH, MEDIUM, LOW) with appropriate icons.
- `web_dashboard/dashboard/templates/dashboard/includes/_table_filter.html`: Reusable search and filter bar component with text input, optional severity/status dropdowns, active filter tags, and clear button.
- `web_dashboard/dashboard/templatetags/__init__.py`: Template tags package initializer.
- `web_dashboard/dashboard/templatetags/dashboard_filters.py`: Custom `query_transform` template tag for preserving GET parameters during pagination with search/filter.
- `web_dashboard/dashboard/urls.py`: Added `/alerts/` and `/alerts/<int:pk>/` routes.

### Modified
- `web_dashboard/dashboard/views.py`: Enhanced `AnalysisHistoryView` with search by filename (`q` param) and status filter (`status` param) support. Enhanced `home` view with critical/high alert counts and recent alerts context for both Admin and Analyst dashboards.
- `web_dashboard/dashboard/templates/dashboard/home.html`: Added critical alert banner, recent critical alerts table, alerts link in quick actions. Replaced inline status badges with `_status_badge.html` include.
- `web_dashboard/dashboard/templates/dashboard/analysis_history.html`: Added search/filter bar via `_table_filter.html` include. Replaced inline status badges with `_status_badge.html` include. Replaced inline pagination with `_pagination.html` include. Added filtered empty state.
- `web_dashboard/dashboard/templates/dashboard/analysis_detail.html`: Replaced inline status/severity badges with reusable includes. Added "Details" link on each anomaly row to alert detail page. Added Alerts link in header navigation. Updated anomaly table to 6-column layout with action column.
- `web_dashboard/dashboard/templates/dashboard/includes/_sidebar.html`: Added Alerts navigation link (`bi-shield-exclamation` icon) between Upload and History in both desktop and mobile sidebars.
- `web_dashboard/dashboard/context_processors.py`: Added `/alerts/` to `nav_map` for sidebar active state tracking.
- `web_dashboard/dashboard/static/dashboard/css/main.css`: Added Phase 11B styles (filter bar, severity banners, feature highlights, spin animation, pagination info, text truncation). Fixed pre-existing CSS bug where `@media` closing brace was misplaced. Added responsive overrides for filter bars and mobile text truncation.

### Architecture Changes
- Introduced a template-tag based approach (`query_transform`) for query string preservation — cleaner than JavaScript URL manipulation.
- Established reusable badge component pattern: all status/severity badge rendering now flows through centralized includes, eliminating 4+ sources of duplicated badge HTML.
- Alerts system uses `job__user` relationship for user isolation rather than a direct `user` field on `Anomaly`, maintaining the existing data model without adding redundant foreign keys.

### Database Changes
- None. No new models, fields, or migrations. Phase 11B uses existing `Anomaly` and `AnalysisJob` models exclusively.

### API Changes
- New user-facing routes: `/alerts/` (alerts list) and `/alerts/<int:pk>/` (alert detail).
- No Flask API changes.

### Security Changes
- `AlertsListView` enforces user isolation: Analysts see only anomalies from their own jobs; Super Admins see all.
- `AlertDetailView` performs ownership verification via parent job's user field before displaying anomaly data.
- All alert views are behind `@login_required` (via `LoginRequiredMixin`).
- Alert detail views are audit-logged via `AuditLog.Action.VIEW`.

### Documentation Updated
- `PROJECT_CONTEXT.md` — Version bump to v0.9.0, Phase 11B completed, dashboard features documented.
- `ROADMAP.md` — Phase 11B marked complete with all tasks.
- `CHANGELOG.md` — This entry.

### Summary
The SOC operational dashboard is now feature-complete for Phase 11B. Analysts and Super Admins can browse, search, filter, and drill into security alerts with full user isolation. All badge rendering is centralized via reusable template includes. Pagination preserves query parameters across page navigation. The home page surfaces critical alerts proactively.

### Future Work
- Phase 12: Charts & Visualization (Chart.js integration for anomaly distribution over time).

---

## [0.8.0] - 2026-06-29 — Phase 11A: Dashboard Foundation

### Completed Phase
- **Phase 11A**: Dashboard Foundation

### Added
- `web_dashboard/dashboard/context_processors.py`: Added `dashboard_context` for navigation metadata injection across all templates.
- `web_dashboard/dashboard/templates/dashboard/includes/`: Added reusable template components (`_sidebar.html`, `_breadcrumbs.html`, `_stats_card.html`, `_empty_state.html`, `_loading_state.html`).
- `web_dashboard/dashboard/templates/dashboard/profile.html`: Dedicated dashboard profile page with activity stats.
- `web_dashboard/dashboard/views.py`: Added `profile_view` and enhanced `home` view with aggregate statistics and recent jobs data.
- `web_dashboard/dashboard/urls.py`: Registered `/profile/` route.

### Modified
- `web_dashboard/dashboard/templates/dashboard/base.html`: Complete overhaul to implement a two-column sidebar layout for authenticated users, responsive offcanvas mobile sidebar, and breadcrumbs block.
- `web_dashboard/dashboard/templates/dashboard/home.html`: Complete overhaul replacing placeholder stat cards with dynamic `_stats_card.html` includes, adding a welcome section, and tables for recent uploads and recent analyses with empty states.
- `web_dashboard/dashboard/static/dashboard/css/main.css`: Appended Phase 11A styles (sidebar layout, navigation active states, breadcrumb overrides, empty/loading states) just before media queries.
- `web_dashboard/dashboard/templates/dashboard/upload.html`: Added breadcrumbs block.
- `web_dashboard/dashboard/templates/dashboard/analysis_history.html`: Added breadcrumbs block.
- `web_dashboard/dashboard/templates/dashboard/analysis_detail.html`: Added breadcrumbs block.
- `web_dashboard/web_dashboard/settings.py`: Registered `dashboard.context_processors.dashboard_context` in `TEMPLATES`.

### Architecture Changes
- Switched to a robust template-include architecture for common UI components.
- Transitioned layout from single-container navbar to a full dashboard layout with persistent sidebar.

---

## [0.7.0] - 2026-06-29 — Phase 10: Upload & Analysis Workflow

### Completed Phase
- **Phase 10**: Upload & Analysis Workflow UI

### Added
- `web_dashboard/dashboard/services.py`: Implemented `FlaskAPIClient` as an Anti-Corruption Layer to interface with the ML Engine (`/health`, `/analyze`, `/stats`), handling timeouts and connection errors via `FlaskAPIError`.
- `web_dashboard/dashboard/forms.py`: Created `EVTXUploadForm` with client/server validation for `.evtx` extension, empty files, and a 50MB configurable file size limit.
- `web_dashboard/dashboard/views.py`: Added `upload_view` (orchestrates upload, API call, and persistence), `AnalysisDetailView` (shows job and anomalies), and `AnalysisHistoryView` (paginated user history).
- `web_dashboard/dashboard/urls.py`: Added routes for `/upload/`, `/analysis/<int:pk>/`, and `/history/`.
- `web_dashboard/dashboard/templates/dashboard/upload.html`: Drag-and-drop file upload UI with real-time validation and double-submit prevention.
- `web_dashboard/dashboard/templates/dashboard/analysis_detail.html`: Results UI with KPI summary, severity breakdown, and feature grid.
- `web_dashboard/dashboard/templates/dashboard/analysis_history.html`: Paginated historical list of analyses with user isolation.

### Modified
- `web_dashboard/dashboard/templates/dashboard/base.html`: Wired up Upload and History navigation links.
- `web_dashboard/dashboard/templates/dashboard/home.html`: Linked "Quick Actions" to the upload form and populated the completed job count placeholder.
- `web_dashboard/dashboard/static/dashboard/css/main.css`: Added styles for `upload-dropzone`, `severity-badge`, `analysis-table`, and `feature-grid`.
- `web_dashboard/web_dashboard/settings.py`: Added `EVTX_MAX_UPLOAD_SIZE` (default 50MB) and `FLASK_API_TIMEOUT` (default 120s).

---

## [0.6.0] - 2026-06-29 — Phase 9B: Django Role-Based Access Control

### Completed Phase
- **Phase 9B**: Django Role-Based Access Control (RBAC)

### Added
- `web_dashboard/dashboard/permissions.py`: Central permission constants (`DashboardPermissions`) and reusable authorization utilities (`user_has_permission`, `get_user_objects`).
- `web_dashboard/dashboard/rbac_mixins.py`: Reusable CBV mixins for Phase 10+ (`RBACPermissionRequiredMixin`, `SuperAdminRequiredMixin`, `OwnershipMixin`, `AnalystOwnerQuerysetMixin`).
- `web_dashboard/dashboard/rbac_decorators.py`: FBV decorators (`permission_required_with_audit`, `superadmin_required`, `owner_required`).
- `web_dashboard/dashboard/signals.py`: Auto-sync `User.role` changes to Django Groups via `post_save` signal.
- `web_dashboard/dashboard/management/commands/setup_rbac.py`: Idempotent management command to create groups, permissions, and sync existing users.
- `web_dashboard/dashboard/templates/dashboard/errors/403.html`: Custom 403 Forbidden page matching SOC dark theme.

### Modified
- `web_dashboard/dashboard/admin.py`: Added permission checks to `UserAdmin` and bulk actions (`promote_to_admin`, `demote_to_analyst`, `disable_users`, `enable_users`).
- `web_dashboard/dashboard/apps.py`: Registered signals in `ready()`.
- `web_dashboard/dashboard/views.py`: Added `@login_required` to `home` and injected role-aware context (admin stats vs analyst stats).
- `web_dashboard/dashboard/middleware.py`: Added strict `/admin/` path restriction based on the `ADMIN` role.
- `web_dashboard/dashboard/templates/dashboard/base.html`: Replaced `user.is_admin` with `perms.dashboard.dashboard_full_access` for admin panel link.
- `web_dashboard/dashboard/templates/dashboard/home.html`: Added permission-based rendering for system-wide vs personal statistics.

### Architecture Changes
- Django's built-in Groups and Permissions framework adopted for RBAC instead of hardcoded role checks, enabling enterprise role extensibility.
- 14 custom permissions defined covering all capabilities (e.g., `view_all_logs`, `manage_users`, `upload_evtx`).

### Database Changes
- No new models or schema changes. Permissions and group assignments live in Django's default `auth_*` tables.

### Security Changes
- Strict separation of Super Admin and Analyst privileges.
- Admin panel routes `/admin/` blocked via middleware for non-admin users, providing defense-in-depth beyond Django's `is_staff` check.
- `OwnershipMixin` and `AnalystOwnerQuerysetMixin` added for strict user data isolation (Analysts can only access their own uploads/incidents).

### Documentation Updated
- `PROJECT_CONTEXT.md` — Version bump to v0.6.0, Phase 9B completed, RBAC added to current implementations.
- `ROADMAP.md` — Phase 9B marked complete.
- `SECURITY_MODEL.md` — Authorization & RBAC section rewritten with detailed group/permission rules.
- `CHANGELOG.md` — This entry.

---

## [0.5.0] - 2026-06-29 — Phase 9A: Django Authentication

### Completed Phase
- **Phase 9A**: Django Authentication (Authentication ONLY — RBAC deferred to Phase 9B)

### Added
- `web_dashboard/dashboard/auth_views.py`: Production authentication views.
  - `CustomLoginView` — Extends Django's `LoginView` with AuditLog integration, "Remember Me" session control, and messaging.
  - `CustomLogoutView` — Extends Django's `LogoutView` with AuditLog integration (logs BEFORE session flush).
  - `RegistrationView` — User self-registration with auto-login, ANALYST role assignment, and AuditLog entry.
  - `ProfileView` — `LoginRequiredMixin` + `UpdateView` for profile management (first name, last name, email).
  - `CustomPasswordChangeView` — Extends Django's `PasswordChangeView` with success messaging and session hash update.
  - `_get_client_ip()` — Extracts client IP from `X-Forwarded-For` or `REMOTE_ADDR`.
  - `_create_audit_log()` — Convenience wrapper for AuditLog creation with error suppression.
- `web_dashboard/dashboard/auth_forms.py`: Authentication forms with Bootstrap 5 styling.
  - `CustomLoginForm` — Extends `AuthenticationForm` with "Remember Me" checkbox.
  - `UserRegistrationForm` — `ModelForm` with username, email, password1/password2, full Django password validation pipeline.
  - `UserProfileForm` — `ModelForm` for User (first_name, last_name, email) with uniqueness validation.
  - `CustomPasswordChangeForm` — Extends Django's `PasswordChangeForm` with Bootstrap-styled widgets.
- `web_dashboard/dashboard/auth_urls.py`: Authentication URL configuration under `/auth/` prefix with `auth` namespace.
  - Routes: `login/`, `logout/`, `register/`, `profile/`, `password-change/`.
- `web_dashboard/dashboard/middleware.py`: `SessionSecurityMiddleware`.
  - Idle session timeout with configurable `SESSION_IDLE_TIMEOUT` (default 30 minutes).
  - Security response headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`.
  - Public path exemptions for login, register, health, admin, static, and media.
- `web_dashboard/dashboard/templates/dashboard/auth/login.html`: Login page with dark SOC theme.
- `web_dashboard/dashboard/templates/dashboard/auth/register.html`: Registration page with password hints.
- `web_dashboard/dashboard/templates/dashboard/auth/profile.html`: Profile management with account info cards.
- `web_dashboard/dashboard/templates/dashboard/auth/password_change.html`: Password change form.
- `web_dashboard/dashboard/templates/dashboard/home.html`: Dashboard landing page (auth-aware, placeholder stats for Phase 10+).

### Files Modified
- `web_dashboard/dashboard/templates/dashboard/base.html` — Replaced placeholder with production template: Bootstrap 5.3, Google Fonts (Inter), auth-aware navigation, user dropdown menu, Django messages integration, auto-dismiss alerts.
- `web_dashboard/dashboard/static/dashboard/css/main.css` — Replaced placeholder with production SOC-themed stylesheet (350+ lines): CSS custom properties, dark navy/slate theme, auth card styling, form controls, buttons, alerts, responsive breakpoints.
- `web_dashboard/dashboard/views.py` — Replaced placeholder with `home()` view (auth-aware landing) and updated `health_check()`.
- `web_dashboard/dashboard/urls.py` — Added `home` route at `/`, updated comments.
- `web_dashboard/web_dashboard/urls.py` — Added `path("auth/", include("dashboard.auth_urls"))` route, updated docstring.
- `web_dashboard/web_dashboard/settings.py` — Added: `SessionSecurityMiddleware` to `MIDDLEWARE`, session security settings (`SESSION_COOKIE_AGE/HTTPONLY/SECURE/SAMESITE`, `SESSION_IDLE_TIMEOUT`, `SESSION_SAVE_EVERY_REQUEST`), `PASSWORD_HASHERS`, `MESSAGE_TAGS` for Bootstrap, `CSRF_COOKIE_HTTPONLY/SECURE`.

### Architecture Changes
- No architectural changes. Django authentication is the planned auth layer per `SECURITY_MODEL.md`.
- Authentication routes under `/auth/` namespace, separate from dashboard feature routes.
- Auth views are in a dedicated `auth_views.py` module (not in `views.py`) for clean separation.

### Database Changes
- **No new migrations.** All authentication uses existing `User` and `AuditLog` models from Phase 8.

### API Changes
- New user-facing routes: `/auth/login/`, `/auth/logout/`, `/auth/register/`, `/auth/profile/`, `/auth/password-change/`.
- Home page at `/` now renders the dashboard landing page.
- No Flask API changes.

### ML Changes
- None. Authentication is Django-only.

### Security Changes
- Session cookies: `HttpOnly`, `Secure` (production), `SameSite=Lax`.
- Idle session timeout: 30 minutes (configurable via `SESSION_IDLE_TIMEOUT`).
- Security headers on all responses: `nosniff`, `DENY` frame, strict referrer policy, permissions policy.
- Password hashers explicitly listed: PBKDF2-SHA256 (primary), PBKDF2-SHA1, Argon2, BCrypt.
- CSRF cookies: `Secure` in production.
- AuditLog records LOGIN/LOGOUT with IP addresses.
- All forms use `{% csrf_token %}`.

### Documentation Updated
- `PROJECT_CONTEXT.md` — Version bump to v0.5.0, Phase 9A moved to completed, auth pipeline documented.
- `ROADMAP.md` — Phase 9A milestones marked complete, Phase 9B (RBAC) separated.
- `SECURITY_MODEL.md` — Authentication section rewritten with full implementation details.
- `CHANGELOG.md` — This entry.

### Summary
The Django authentication system is now fully operational. Users can register, login, logout, manage their profile, and change their password. All auth events are audit-logged. Sessions are secured with idle timeout, HttpOnly cookies, and security headers. The system uses Django's built-in auth framework extended with custom views and forms. RBAC enforcement is deferred to Phase 9B.

### Known Issues
- No email backend configured. Password reset via email is architecturally ready but not functional until an email backend is added.
- No brute force protection. `django-axes` is planned for a future phase.
- SQLite is used for development. Production deployments require PostgreSQL migration.

### Future Work
- Phase 9B: Role-Based Access Control (permission enforcement on views).

---

## [0.4.0] - 2026-06-29 — Phase 8: Django Database Models

### Completed Phase
- **Phase 8**: Django Database Models Design & Implementation

### Added
- `web_dashboard/dashboard/models.py`: Full ORM implementation replacing the placeholder stub.
  - `User` — Custom user model extending `AbstractUser` with RBAC roles (ADMIN, ANALYST) and required email field.
  - `AnalysisJob` — Tracks `.evtx` file upload lifecycle (PENDING → RUNNING → COMPLETED → FAILED) with `FileField`, status transitions (`mark_running()`, `mark_completed()`, `mark_failed()`), and computed `anomaly_rate` property.
  - `Anomaly` — Stores anomalous time windows with `anomaly_score`, `severity` (CRITICAL/HIGH/MEDIUM/LOW), `feature_data` JSONField, and `rag_explanation` (reserved for Phase 14).
  - `AuditLog` — Append-only compliance log with user, job, action, IP address, and timestamp fields. Uses `SET_NULL` on deletion to preserve audit trail.
- `web_dashboard/dashboard/managers.py`: Custom `UserManager` extending `BaseUserManager`.
  - `create_user()` — Enforces role assignment, normalizes email, defaults to ANALYST.
  - `create_superuser()` — Forces ADMIN role, `is_staff=True`, `is_superuser=True`.
- `web_dashboard/dashboard/admin.py`: Full Django admin registrations for all 4 models.
  - `UserAdmin` — Extends Django's built-in `UserAdmin` with role field integration.
  - `AnalysisJobAdmin` — Status filtering, readonly timestamps, collapsible result fields.
  - `AnomalyAdmin` — Severity-based filtering, collapsible feature data and RAG explanation.
  - `AuditLogAdmin` — Read-only enforcement via `has_add/change/delete_permission = False`.
- `web_dashboard/dashboard/apps.py`: `DashboardConfig` with `BigAutoField` default and proper app label.
- `web_dashboard/dashboard/migrations/0001_initial.py`: Auto-generated initial migration creating all 4 tables and 5 composite indexes.

### Files Modified
- `web_dashboard/dashboard/models.py` — Replaced stub with full implementation (536 lines).
- `web_dashboard/dashboard/admin.py` — Replaced stub with full implementation (256 lines).
- `web_dashboard/web_dashboard/settings.py` — Added `AUTH_USER_MODEL`, `DashboardConfig`, `MEDIA_ROOT/MEDIA_URL`, crispy forms config, login redirects.

### Files Created
- `web_dashboard/dashboard/managers.py` — Custom UserManager (131 lines).
- `web_dashboard/dashboard/apps.py` — DashboardConfig (30 lines).
- `web_dashboard/dashboard/migrations/__init__.py` — Migration package init.
- `web_dashboard/dashboard/migrations/0001_initial.py` — Initial migration (124 lines).

### Architecture Changes
- No architectural changes. Django models are the planned persistence layer per `DATABASE_DESIGN.md`.
- `AUTH_USER_MODEL` set to `dashboard.User` — must remain set before any migrations are run.

### Database Changes
- **4 tables created**: `dashboard_user`, `dashboard_analysisjob`, `dashboard_anomaly`, `dashboard_auditlog`.
- **5 composite indexes**: `idx_job_status_uploaded`, `idx_anomaly_severity_score`, `idx_anomaly_job_severity`, `idx_audit_action_created`, `idx_audit_user_created`.
- SQLite migrations applied successfully.

### API Changes
- None. No new endpoints added in this phase.

### ML Changes
- None. Models store ML results received via HTTP from Flask.

### Security Changes
- Custom `UserManager` enforces role assignment on all user creation paths.
- `AuditLogAdmin` is fully read-only (no add, change, or delete).
- `AuditLog.user` uses `SET_NULL` to preserve logs after user deletion.

### Documentation Updated
- `PROJECT_CONTEXT.md` — Version bump to v0.4.0, Phase 8 moved to completed, Django pipeline status updated.
- `ROADMAP.md` — Phase 8 milestones marked complete, moved to "Completed — Awaiting Approval".
- `CHANGELOG.md` — This entry.

### Dependencies Added
- `django-crispy-forms` — Required by `INSTALLED_APPS` (already in `requirements.txt`).
- `crispy-bootstrap5` — Required by `INSTALLED_APPS` (already in `requirements.txt`).

### Summary
The Django persistence layer is now fully implemented. All four database models (`User`, `AnalysisJob`, `Anomaly`, `AuditLog`) are production-ready with proper indexes, relationships, lifecycle methods, and admin interface. The schema matches `DATABASE_DESIGN.md` exactly.

### Known Issues
- SQLite is used for development. Production deployments require PostgreSQL migration.
- `requirements.txt` pins older Django/crispy versions than those actually installed. Should be reconciled during a future dependency audit.

### Future Work
- Phase 9: Django Authentication & Role-Based Access Control (Login, Logout, RBAC enforcement).

---

## [0.3.0] - 2026-06-28 — Phase 7B: Flask REST API

### Completed Phase
- **Phase 7B**: Flask REST API Implementation

### Added
- `ml_engine/app.py`: Full Flask REST API replacing the 15-line placeholder stub.
  - Application factory pattern (`create_app()`) for WSGI deployment compatibility.
  - Blueprint `api_v1` under `/api/v1` prefix for API versioning.
  - `GET /api/v1/health` — Liveness probe with model load status and version.
  - `POST /api/v1/analyze` — Full ML pipeline integration (parse → features → predict) accepting `file_path` and optional `job_id`.
  - `GET /api/v1/stats` — Model metadata (hyperparameters, training timestamp, feature count).
  - `SafeJSONEncoder` — Recursive sanitizer for numpy int64/float64, NaN, Infinity, datetime, and Path objects.
  - Global error handlers (404, 405, 500) returning structured JSON — never HTML error pages.
  - Graceful startup — app starts even if model is not trained; `/health` reports `models_loaded: false`, `/analyze` returns `503`.

### Files Modified
- `ml_engine/app.py` — Replaced stub with full implementation.

### Architecture Changes
- No architectural changes. Flask REST API is the planned HTTP interface wrapping the existing `AnalysisPipeline` (Phase 7A).
- `AnalysisPipeline` initialized once at startup and reused across requests.

### Database Changes
- None.

### API Changes
- Three endpoints now operational: `/health`, `/analyze`, `/stats`.
- Error responses standardized with `{"status": "error", "message": "..."}` schema.
- New status code: `503 Service Unavailable` when model is not loaded.

### ML Changes
- None. The Flask API wraps the existing pipeline without modifications.

### Security Changes
- None. Internal network deployment model unchanged. PSK auth remains a future enhancement.

### Documentation Updated
- `API_SPECIFICATION.md` — Complete rewrite with field tables, all status codes, startup instructions.
- `PROJECT_CONTEXT.md` — Version bump to v0.3.0, Phase 7B moved to completed, Flask pipeline status updated.
- `ROADMAP.md` — Phase 7B milestones marked complete.
- `DEVELOPMENT_GUIDE.md` — Updated Flask startup instructions (removed "stubbed" note).
- `CHANGELOG.md` — This entry.

### Summary
The Flask ML Inference microservice is now fully operational. Django can invoke the ML pipeline via HTTP REST calls to analyze `.evtx` files, check model health, and query model statistics.

### Known Issues
- Synchronous processing: Large `.evtx` files may cause HTTP timeouts. Future mitigation via Celery async queue.
- No authentication on the Flask API (designed for internal network only).

### Future Work
- Phase 8: Django Database Models (User, AnalysisJob, Anomaly, AuditLog).

---

## [0.2.0] - Post-Phase 7A Refactoring

### Added
- `ml_engine/__init__.py`: Converted the ML engine into a proper Python package.
- `ml_engine/scaler.py`: Extracted `FeatureScaler` to decouple training from prediction.
- `ml_engine/pipeline.py`: Added `AnalysisPipeline` to orchestrate end-to-end single-file analysis in memory.
- Comprehensive Engineering Documentation Suite (README, Architecture, Roadmap, etc.).

### Changed
- Refactored all `ml_engine` modules to use relative imports instead of `sys.path` hacks.
- Updated module usage docstrings to reflect standard `python -m` invocation.

### Removed
- `FeatureScaler` class declaration removed from `train.py`.

---

## [0.1.0] - Phase 6 Completion

### Added
- Core Data Science Pipeline completed.
- `parser.py`: Implementation of `EVTXFileParser` and `EVTXBatchParser`.
- `feature_engineering.py`: Implementation of `EventFeatureBuilder` (15 MITRE-aligned features).
- `train.py`: Implementation of `AnomalyModelTrainer` using Isolation Forest.
- `predict.py`: Implementation of `AnomalyPredictor`.
- `web_dashboard`: Scaffolded Django application with stubbed models and views.
- `scripts/`: Utilities for dataset downloading and validation.

### Changed
- Project configuration unified into `ml_engine/config.py` driven by `.env`.

### Initial Release
- Setup of virtual environment, dependencies (`requirements.txt`), and `.gitignore`.
