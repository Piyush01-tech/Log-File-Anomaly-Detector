# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project loosely adheres to Semantic Versioning as it progresses through development phases.

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
