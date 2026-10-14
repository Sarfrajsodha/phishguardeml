"""
ML Predictor Service.
Loads trained ML models and runs phishing prediction.
"""

import os
import pickle
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MLPredictor:
    """Loads and manages multiple ML models for phishing detection."""

    MODEL_NAMES = ["logistic_regression", "random_forest", "naive_bayes"]

    def __init__(self, models_dir: str):
        self.models_dir = models_dir
        self.models: Dict[str, Any] = {}
        self.vectorizer = None
        self._load_models()

    def _load_models(self):
        """Load all available trained models and the TF-IDF vectorizer."""
        # Load vectorizer
        vec_path = os.path.join(self.models_dir, "tfidf_vectorizer.pkl")
        if os.path.exists(vec_path):
            with open(vec_path, "rb") as f:
                self.vectorizer = pickle.load(f)
            logger.info("[MLPredictor] TF-IDF vectorizer loaded.")
        else:
            logger.warning("[MLPredictor] Vectorizer not found. Run training first.")

        # Load each model
        for name in self.MODEL_NAMES:
            model_path = os.path.join(self.models_dir, f"{name}.pkl")
            if os.path.exists(model_path):
                with open(model_path, "rb") as f:
                    self.models[name] = pickle.load(f)
                logger.info(f"[MLPredictor] Loaded model: {name}")
            else:
                logger.warning(f"[MLPredictor] Model not found: {name}")

    def predict(self, processed_text: str, model_name: str = "ensemble") -> Dict[str, Any]:
        """
        Run prediction on preprocessed email text.
        Returns label, confidence, and per-model scores.
        """
        if not self.vectorizer:
            return self._fallback_result("No vectorizer loaded")

        if not self.models:
            return self._fallback_result("No models loaded")

        try:
            # Vectorize the input
            X = self.vectorizer.transform([processed_text])

            if model_name == "ensemble":
                return self._ensemble_predict(X)
            elif model_name in self.models:
                return self._single_model_predict(X, model_name)
            else:
                return self._ensemble_predict(X)

        except Exception as e:
            logger.error(f"[MLPredictor] Prediction error: {e}")
            return self._fallback_result(str(e))

    def _ensemble_predict(self, X) -> Dict[str, Any]:
        """Soft-voting ensemble across all available models."""
        phishing_probs = []
        model_results = {}

        for name, model in self.models.items():
            try:
                if hasattr(model, "predict_proba"):
                    prob = model.predict_proba(X)[0]
                    phish_prob = prob[1] if len(prob) > 1 else prob[0]
                else:
                    pred = model.predict(X)[0]
                    phish_prob = float(pred)

                phishing_probs.append(phish_prob)
                model_results[name] = {
                    "prediction": "phishing" if phish_prob >= 0.5 else "safe",
                    "confidence": round(phish_prob, 4),
                }
            except Exception as e:
                logger.warning(f"[MLPredictor] Model {name} failed: {e}")

        if not phishing_probs:
            return self._fallback_result("All models failed")

        avg_prob = sum(phishing_probs) / len(phishing_probs)
        label = "phishing" if avg_prob >= 0.5 else "safe"

        return {
            "prediction": label,
            "confidence": round(avg_prob, 4),
            "model_used": "ensemble",
            "model_breakdown": model_results,
            "error": None,
        }

    def _single_model_predict(self, X, model_name: str) -> Dict[str, Any]:
        """Predict using a single named model."""
        model = self.models[model_name]
        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(X)[0]
            phish_prob = prob[1] if len(prob) > 1 else prob[0]
        else:
            phish_prob = float(model.predict(X)[0])

        label = "phishing" if phish_prob >= 0.5 else "safe"
        return {
            "prediction": label,
            "confidence": round(phish_prob, 4),
            "model_used": model_name,
            "model_breakdown": {model_name: {"prediction": label, "confidence": round(phish_prob, 4)}},
            "error": None,
        }

    def _fallback_result(self, reason: str) -> Dict[str, Any]:
        """Return a safe fallback when no models are available."""
        logger.warning(f"[MLPredictor] Using fallback result: {reason}")
        return {
            "prediction": "unknown",
            "confidence": 0.0,
            "model_used": "none",
            "model_breakdown": {},
            "error": reason,
        }

    def is_ready(self) -> bool:
        """Check if models are loaded and ready."""
        return bool(self.vectorizer and self.models)

    def reload(self):
        """Reload all models from disk (after retraining)."""
        self.models = {}
        self.vectorizer = None
        self._load_models()
