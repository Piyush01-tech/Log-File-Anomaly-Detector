# Architectural Decisions

This document records the major engineering decisions made during the design and implementation of the Log File Anomaly Detector. Recording these decisions provides context for future contributors and prevents revisiting resolved debates.

---

## 1. Decoupling Web and ML Layers (Django + Flask)

**Decision**: Split the application into two separate microservices: a Django application for the web dashboard and a Flask application for the ML inference engine.

**Why**:
- **Dependency Isolation**: Machine Learning libraries (Pandas, Scikit-Learn, NumPy) are heavy and often have strict version requirements. Keeping them out of the Django environment prevents dependency conflicts with web-focused packages.
- **Independent Scaling**: In a production environment, ML inference is highly CPU/Memory intensive, while web serving is I/O intensive. A decoupled architecture allows the ML containers to be scaled independently of the web dashboard.
- **Separation of Concerns**: Python developers specializing in data science can work on the `ml_engine` without needing to understand Django's ORM or request lifecycle.

**Alternatives Considered**:
- *FastAPI for everything*: Rejected because Django provides a robust, battle-tested out-of-the-box admin panel, authentication system, and ORM that accelerates building enterprise dashboards.
- *Django for everything*: Rejected because Django is too heavy for a simple ML inference endpoint, and tightly couples data science code to web code.

---

## 2. Choosing Flask over FastAPI for the ML Service

**Decision**: Use Flask for the ML microservice.

**Why**:
- The API contract between Django and the ML engine is extremely simple (primarily a single `/analyze` endpoint passing a file path).
- Flask is lightweight, synchronous by default, and highly compatible with standard synchronous ML workloads (`scikit-learn` prediction is CPU-bound and synchronous).

**Alternatives Considered**:
- *FastAPI*: While offering asynchronous capabilities and auto-documentation, the core ML workload is synchronous. Using `async def` with blocking Pandas/Sklearn operations would require careful threadpool management, complicating a simple microservice.

---

## 3. Machine Learning: Isolation Forest

**Decision**: Use `scikit-learn`'s `IsolationForest` for anomaly detection.

**Why**:
- **Unsupervised Learning**: True malicious activity is rare and constantly evolving, making labeled training data practically impossible to obtain for all attack vectors. Isolation Forest does not require labeled data; it isolates outliers based on feature distribution.
- **Performance**: It scales well with high-dimensional data and large log volumes.
- **Explainability**: Unlike Deep Learning auto-encoders, tree-based models offer slightly better interpretability and faster execution times on standard hardware.

---

## 4. Artifact Persistence: Joblib over Pickle

**Decision**: Use `joblib` to save and load the trained models and scalers.

**Why**:
- `joblib` is heavily optimized for large NumPy arrays (which back `scikit-learn` models and Pandas DataFrames), making it significantly faster and more memory-efficient than Python's standard `pickle` module for ML artifacts.

---

## 5. Database: SQLite (Initial) to PostgreSQL (Future)

**Decision**: Start with SQLite, but design Django models for strict compatibility with PostgreSQL.

**Why**:
- SQLite requires zero configuration, allowing rapid development, testing, and easy onboarding for new contributors.
- Designing with standard Django fields (avoiding SQLite-specific hacks) ensures that changing the `DATABASES` configuration to PostgreSQL in production will require only a single `manage.py migrate` command.

---

## 6. Upload Workflow vs. Live Ingestion

**Decision**: The initial MVP focuses exclusively on manual `.evtx` file uploads.

**Why**:
- Live log ingestion (e.g., via Syslog, WEF, or Kafka) introduces massive complexity in data buffering, streaming window aggregation, and state management.
- The upload workflow allows the team to prove the ML model's efficacy and build the core UI without getting bogged down in data engineering infrastructure.

**Future Migration Strategy**:
- The `AnalysisPipeline` was specifically designed with an `analyze_dataframe()` method. When live ingestion is added, the new data pipeline will bypass the file parser, format incoming JSON into a DataFrame, and pass it directly to the existing feature engineering pipeline.

---

## 7. Isolating RAG Architecture

**Decision**: The Retrieval-Augmented Generation (RAG) feature will be built as an isolated layer invoked *after* anomaly detection, rather than integrated into the detection pipeline itself.

**Why**:
- **Latency**: LLM generation is slow (seconds to tens of seconds). If placed in the critical path of the detection pipeline, it would paralyze log processing throughput.
- **Cost**: Querying LLMs for every log event is cost-prohibitive. RAG will only be invoked on-demand or automatically for anomalies flagged as `HIGH` or `CRITICAL` severity by the Isolation Forest model.
