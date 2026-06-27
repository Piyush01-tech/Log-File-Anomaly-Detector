# Contributing Guidelines

Thank you for your interest in contributing to the Log File Anomaly Detector! This project is intended to be a production-quality enterprise tool. Please adhere to the following guidelines.

---

## 🤝 How to Contribute

1. **Check the Roadmap**: Ensure your contribution aligns with the current phase or addresses technical debt documented in the `ROADMAP.md` or `PROJECT_CONTEXT.md`.
2. **Create an Issue**: Before writing significant code, open an issue to discuss your proposed changes.
3. **Fork and Branch**: Create a feature branch from `main`.

---

## 🌿 Branch Naming Conventions

Use descriptive branch names:
- `feature/short-description` (e.g., `feature/django-models`)
- `fix/short-description` (e.g., `fix/parser-memory-leak`)
- `docs/short-description` (e.g., `docs/api-spec-update`)
- `refactor/short-description` (e.g., `refactor/ml-imports`)

---

## 📝 Commit Message Standards

Write clear, imperative commit messages:
- **Good**: `Add User model to Django dashboard`
- **Bad**: `Added user stuff` or `Fixed it`

---

## 💻 Coding Standards

- **Python**: Follow PEP 8 guidelines.
- **Type Hints**: All new Python code MUST include type annotations for arguments and return types.
- **Docstrings**: Provide Google-style docstrings for all classes and public methods. Explain *why* the code exists, not just *what* it does.
- **Architecture**: Respect the boundaries defined in `PROJECT_CONTEXT.md`. Never import Django code into Flask or vice versa.

---

## 📖 Documentation Rules

If your code changes system behavior or architecture:
1. You MUST update `PROJECT_CONTEXT.md` if the vision or folder structure changes.
2. You MUST update `ARCHITECTURE.md` if data flows change.
3. You MUST update `CHANGELOG.md` with your additions.
**Code without accompanying documentation updates will be rejected.**

---

## 🔄 Pull Request Workflow

1. Push your branch to your fork.
2. Open a Pull Request against the `main` branch.
3. Ensure the PR description details exactly what was changed and why.
4. Request a review from the repository maintainers (or AI reviewers).
5. Address review feedback promptly.

---

## 🐛 Issue Reporting

If you find a bug, please create an issue including:
1. Steps to reproduce.
2. Expected behavior vs. actual behavior.
3. Python version, OS, and any relevant logs.
