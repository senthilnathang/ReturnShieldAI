from .config import nlp_config
from .router import router

try:
    from .predictor import NLPredictor
except Exception:
    NLPredictor = None

__all__ = ["nlp_config", "NLPredictor", "router"]
