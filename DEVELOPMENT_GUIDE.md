# Development Guide

This guide is for developers and AI assistants contributing to the Log File Anomaly Detector.

---

## 💻 Local Development Setup

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Virtual Environment
Always use a virtual environment to avoid dependency conflicts.
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
*(Note: Pin versions deliberately. Do not blindly `pip freeze > requirements.txt` without checking).*

### 4. Environment Variables
Create a `.env` file in the project root:
```bash
cp .env.example .env
```
Ensure `DEBUG=True` for local development.

---

## 🏃 Running the Application

Because of the decoupled architecture, you must run both services to test full functionality.

### Starting the Flask ML Engine
```bash
# Option 1: Flask CLI
set FLASK_APP=ml_engine/app.py       # Windows
export FLASK_APP=ml_engine/app.py    # Linux/Mac
flask run --port=5000

# Option 2: Direct execution
python -m ml_engine.app
```
The Flask API will be available at `http://127.0.0.1:5000/api/v1/`.

> [!NOTE]
> The model and scaler must be trained before the `/analyze` endpoint is functional. Run `python -m ml_engine.train` first. The `/health` endpoint will report `models_loaded: false` if training has not been completed.

### Starting the Django Dashboard
```bash
cd web_dashboard
python manage.py migrate
python manage.py runserver 8000
```
Access the dashboard at `http://127.0.0.1:8000`.

---

## 📁 Folder Responsibilities

Do not mix domain logic. Adhere strictly to these boundaries:

- `ml_engine/`: Data science domain. No HTML, no HTTP request parsing (except in `app.py`), no SQL. Pure Python, Pandas, and Scikit-Learn.
- `web_dashboard/dashboard/`: Presentation domain. No `pandas`, no `sklearn`. Deals only with HTTP, databases, and JSON responses from Flask.
- `data/`: Ephemeral data storage. Do not commit `.evtx` or `.csv` files to version control.
- `scripts/`: Standalone utilities that do not belong in the application runtime.

---

## 🧪 Testing (Future Implementation)

Currently, testing is manual. Future phases will introduce `pytest`.

- **Unit tests for ML**: Mock `python-evtx` and test feature engineering math.
- **Unit tests for Django**: Use Django's `TestCase` to mock the `FlaskAPIClient`.
- **Integration tests**: Spin up both Flask and Django to test end-to-end upload.

---

## 🌿 Git Workflow & Branching Strategy

1. **`main` branch**: Always deployable. Represents the current "Phase" completion.
2. **Feature branches**: Create branches for specific tasks (e.g., `feature/phase8-django-models`).
3. **Commit Messages**: Use descriptive, imperative language (e.g., "Add User model to Django").

---

## 🧹 Code Quality

- **Formatting**: Use `black` for Python code formatting.
- **Linting**: Use `flake8` to catch syntax errors and undefined names.
- **Type Hinting**: All new Python functions MUST include type hints (`def func(arg: int) -> str:`).
