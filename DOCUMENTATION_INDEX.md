# Documentation Index

Welcome to the Log File Anomaly Detector documentation suite. This project maintains a strict, comprehensive documentation standard to ensure that human developers and AI assistants can reliably understand, navigate, and contribute to the system without accumulating technical debt.

---

## 🧭 How to Use This Documentation

If you are new to the project or an AI assistant joining the repository for the first time, read the documents in the following order:

1. **[README.md](README.md)**: The high-level overview. Start here to understand what the project does and how to run it.
2. **[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)**: The single source of truth. Read this to understand the current state of the project, completed phases, and fundamental development rules. **(Critical for AI Assistants)**.
3. **[ARCHITECTURE.md](ARCHITECTURE.md)**: Read this to understand the physical and logical boundaries of the application, how Django and Flask communicate, and the request lifecycle.
4. **[DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)**: Read this before writing your first line of code to understand local setup, boundaries, and git workflow.

---

## 📚 Document Directory

### Core Architecture & Strategy
- **[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)**: The definitive guide to the project's state, rules, and vision.
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Diagrams and explanations of the decoupled microservice layers.
- **[ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)**: A historical log of *why* specific engineering choices were made (e.g., SQLite vs PostgreSQL, Flask vs FastAPI).
- **[ROADMAP.md](ROADMAP.md)**: The phase-by-phase plan from inception to future enterprise deployments.

### Technical Specifications
- **[ML_PIPELINE.md](ML_PIPELINE.md)**: Deep dive into the data science workflow: parsing, feature engineering, Isolation Forest training, and prediction.
- **[DATABASE_DESIGN.md](DATABASE_DESIGN.md)**: Entity Relationship (ER) diagrams and schema rules for the Django web dashboard.
- **[API_SPECIFICATION.md](API_SPECIFICATION.md)**: The exact JSON REST contract between the Django frontend and the Flask ML backend.
- **[SECURITY_MODEL.md](SECURITY_MODEL.md)**: Threat models, RBAC, input validation, and boundaries.
- **[RAG_DESIGN.md](RAG_DESIGN.md)**: Future architecture for the Retrieval-Augmented Generation incident explanation layer.

### Process & Governance
- **[DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)**: Setup instructions and local development practices.
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Rules for Pull Requests, commit messages, and documentation updates.
- **[CHANGELOG.md](CHANGELOG.md)**: Version history and feature release tracking.
