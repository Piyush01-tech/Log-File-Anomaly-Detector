# API Specification

This document details the Flask REST API contract (Phase 7B implementation). The Django application communicates with the ML engine strictly through these endpoints.

---

## 🌐 Base URL
`http://localhost:5000/api/v1`

---

## 1. Health Check
Liveness probe to verify the ML engine is operational and models are loaded.

**Endpoint**: `GET /health`

**Response**: `200 OK`
```json
{
  "status": "up",
  "version": "0.2.0",
  "models_loaded": true
}
```

---

## 2. Analyze EVTX File
Orchestrates the entire ML pipeline (parse -> extract -> predict) on a provided file.

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
      "timestamp": "2025-01-01T15:00:00Z",
      "computer": "HOST01",
      "anomaly_score": -0.121264,
      "severity": "HIGH",
      "features": {
        "failed_logins": 45,
        "process_creation_events": 120,
        "admin_ratio": 0.8
        // ... (all 15 features)
      }
    }
  ]
}
```

**Error Responses**:
- `400 Bad Request`: File not found or invalid format.
- `500 Internal Server Error`: Parsing failed or model execution error.

```json
{
  "status": "error",
  "message": "EVTX file not found at provided path."
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

---

## 🔒 Authentication Strategy

Currently, the ML microservice is designed to run behind a firewall on an internal Docker network, accessible only by the Django application. 

**Future Security Enhancements**:
When deployed in a zero-trust environment, the API will be secured using a static Pre-Shared Key (PSK). 

Django will send requests with:
`Authorization: Bearer <ML_API_SECRET_KEY>`

Flask will reject any request missing the correct token with `401 Unauthorized`.
