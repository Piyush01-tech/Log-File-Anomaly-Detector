# API Specification

This document details the Flask REST API contract implemented in Phase 7B. The Django application communicates with the ML engine strictly through these endpoints.

---

## 🌐 Base URL
`http://localhost:5000/api/v1`

---

## 📐 Common Response Schema

All responses follow a consistent JSON schema:

**Success responses** include `"status": "success"` plus endpoint-specific fields.

**Error responses** always include:
```json
{
  "status": "error",
  "message": "Human-readable description of the error."
}
```

---

## 1. Health Check
Liveness probe to verify the ML engine is operational and models are loaded.

**Endpoint**: `GET /health`

**Response**: `200 OK`
```json
{
  "status": "up",
  "version": "0.3.0",
  "models_loaded": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always `"up"` if the service is reachable. |
| `version` | string | Current ML engine version. |
| `models_loaded` | boolean | `true` if the Isolation Forest model and scaler were loaded at startup. `false` if training has not been run. |

---

## 2. Analyze EVTX File
Orchestrates the entire ML pipeline (parse → extract → predict) on a provided file.

**Endpoint**: `POST /analyze`

> [!NOTE]
> Currently, the API expects a local file path because both Flask and Django share the same local filesystem during development. In a Dockerized production environment with separate file systems, this endpoint will need to accept multipart form-data (the actual file bytes) or a shared network mount path.

**Request Body** (`application/json`):
```json
{
  "file_path": "/absolute/path/to/media/uploads/suspicious.evtx",
  "job_id": 123
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | string | **Yes** | Absolute path to the `.evtx` file on the shared filesystem. |
| `job_id` | integer | No | Optional identifier echoed back for Django correlation. |

**Response**: `200 OK`
```json
{
  "status": "success",
  "job_id": 123,
  "summary": {
    "total_samples": 360,
    "total_anomalies": 18,
    "anomaly_rate": 0.05
  },
  "anomalies": [
    {
      "timestamp": "2025-01-01T15:00:00",
      "computer": "HOST01",
      "anomaly_score": -0.121264,
      "severity": "HIGH",
      "features": {
        "total_events": 500,
        "failed_logins": 45,
        "successful_logins": 12,
        "admin_events": 30,
        "process_creation_events": 120,
        "new_user_events": 2,
        "service_install_events": 5,
        "group_membership_changes": 3,
        "audit_log_clears": 0,
        "unique_users": 8,
        "unique_processes": 15,
        "unique_ips": 4,
        "failure_rate": 0.789,
        "admin_ratio": 0.06,
        "process_ratio": 0.24
      }
    }
  ]
}
```

> [!IMPORTANT]
> The `anomalies` array contains only rows flagged as anomalous (`is_anomaly=true`). Normal rows are excluded from the response to minimize payload size. The `summary` object provides aggregate counts for all rows.

**Error Responses**:

| Status | Condition |
|--------|-----------|
| `400 Bad Request` | Missing `file_path`, file not found on disk, invalid extension, or empty/unparseable file. |
| `503 Service Unavailable` | Model not loaded (training has not been run). |
| `500 Internal Server Error` | Unexpected pipeline error. Details logged server-side. |

```json
{
  "status": "error",
  "message": "EVTX file not found at provided path: /path/to/missing.evtx"
}
```

---

## 3. Model Statistics
Returns metadata about the currently loaded Isolation Forest model.

**Endpoint**: `GET /stats`

**Response**: `200 OK`
```json
{
  "model_type": "IsolationForest",
  "n_estimators": 200,
  "contamination": 0.05,
  "trained_at": "2026-06-24T18:36:25Z",
  "features_monitored": 15
}
```

| Field | Type | Description |
|-------|------|-------------|
| `model_type` | string | Algorithm name. |
| `n_estimators` | integer | Number of trees in the ensemble. |
| `contamination` | float | Expected anomaly proportion. |
| `trained_at` | string | ISO 8601 timestamp of training (from metadata file). |
| `features_monitored` | integer | Number of input features. |

**Error Response**: `503 Service Unavailable` if model is not loaded.

---

## 🔒 Authentication Strategy

Currently, the ML microservice is designed to run behind a firewall on an internal Docker network, accessible only by the Django application. No authentication is enforced in this phase.

**Future Security Enhancements**:
When deployed in a zero-trust environment, the API will be secured using a static Pre-Shared Key (PSK). 

Django will send requests with:
`Authorization: Bearer <ML_API_SECRET_KEY>`

Flask will reject any request missing the correct token with `401 Unauthorized`.

---

## 🚀 Startup & Deployment

### Development
```bash
# Option 1: Flask CLI
set FLASK_APP=ml_engine/app.py
flask run --port=5000

# Option 2: Direct execution
python -m ml_engine.app
```

### Production (Future)
```bash
gunicorn "ml_engine.app:create_app()" --bind 0.0.0.0:5000 --workers 4
```
