"""
ml_engine/__init__.py
======================
Package initializer for the ML Engine microservice.

WHY THIS EXISTS (Critical Fix C1, C3):
  Previously, ml_engine/ had no __init__.py — every module used
  sys.path.insert() hacks to import siblings.  This broke:
    - Flask WSGI deployment (gunicorn cannot resolve bare imports)
    - Django integration (cannot do 'from ml_engine.predict import ...')
    - pytest discovery (path manipulation conflicts)

  Now that ml_engine is a proper Python package:
    - All internal imports use relative syntax (from .config import Config)
    - External consumers use absolute syntax (from ml_engine.predict import AnomalyPredictor)
    - Standalone scripts run via: python -m ml_engine.parser

USAGE:
  # From Django or external code:
  from ml_engine.predict import AnomalyPredictor
  from ml_engine.pipeline import AnalysisPipeline
  from ml_engine.config import Config
"""

# Intentionally minimal — heavy imports (sklearn, pandas) happen in
# submodules on demand.  This avoids loading the entire ML stack when
# only Config or logger is needed.
"""
ml_engine package exports are accessed via submodule imports:
  from ml_engine.config import Config
  from ml_engine.logger import get_logger
  from ml_engine.scaler import FeatureScaler
  from ml_engine.parser import EVTXFileParser, EVTXBatchParser
  from ml_engine.feature_engineering import EventFeatureBuilder, FeatureEngineeringPipeline
  from ml_engine.train import AnomalyModelTrainer
  from ml_engine.predict import AnomalyPredictor, PredictionResult
  from ml_engine.pipeline import AnalysisPipeline
"""
