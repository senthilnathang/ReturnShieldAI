from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer

from .config import nlp_config
from .embeddings import NLPEmbeddingProvider
from .model_registry import NLPModelRegistry

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
except ImportError:
    torch = None
    nn = None

try:
    import xgboost as xgb
except ImportError:
    xgb = None


def train_intent_classifier(
    texts: list[str],
    labels: list[list[str]],
    model_type: str = "logistic_regression",
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    logger.info("Training intent classifier with %d samples", len(texts))
    mlb = MultiLabelBinarizer()
    y = mlb.fit_transform(labels)
    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english", ngram_range=(1, 3))
    X = vectorizer.fit_transform(texts)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    if model_type == "xgboost" and xgb is not None:
        model = xgb.XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            objective="binary:logistic", random_state=random_state,
            use_label_encoder=False, eval_metric="logloss",
        )
    else:
        model = LogisticRegression(
            C=1.0, max_iter=1000, random_state=random_state,
            multi_class="ovr", solver="liblinear",
        )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, average="micro", zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, average="micro", zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, average="micro", zero_division=0), 4),
    }
    if hasattr(model, "predict_proba"):
        try:
            y_prob = model.predict_proba(X_test)
            if isinstance(y_prob, list):
                y_prob_flat = np.column_stack([p[:, 1] if p.shape[1] > 1 else p[:, 0] for p in y_prob])
            else:
                y_prob_flat = y_prob[:, 1] if y_prob.shape[1] > 1 else y_prob[:, 0]
            metrics["roc_auc"] = round(roc_auc_score(y_test, y_prob_flat, multi_class="ovr"), 4)
        except Exception:
            metrics["roc_auc"] = 0.0

    artifact = {
        "model": model,
        "vectorizer": vectorizer,
        "label_encoder": mlb,
        "classes": mlb.classes_.tolist(),
    }
    artifact_path = Path(nlp_config.artifact_root) / "intent_classifier.pkl"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, artifact_path)

    logger.info("Intent classifier trained. Metrics: %s", metrics)
    return {
        "artifact_path": str(artifact_path),
        "metrics": metrics,
        "model_type": model_type,
        "num_classes": len(mlb.classes_),
    }


def train_fraud_classifier(
    embeddings: list[list[float]],
    labels: list[int],
    model_type: str = "logistic_regression",
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    logger.info("Training NLP fraud classifier with %d samples", len(embeddings))
    X = np.array(embeddings, dtype=np.float32)
    y = np.array(labels, dtype=np.float32)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    if model_type == "xgboost" and xgb is not None:
        model = xgb.XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            objective="binary:logistic", random_state=random_state,
            use_label_encoder=False, eval_metric="logloss",
        )
    elif model_type == "neural" and torch is not None:
        model = _train_torch_classifier(X_train, y_train, X_test, y_test)
    else:
        model = LogisticRegression(C=1.0, max_iter=1000, random_state=random_state)
        model.fit(X_train, y_train)

    if model_type != "neural":
        model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else y_pred
    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_prob), 4) if len(np.unique(y_test)) > 1 else 0.0,
    }

    registry = NLPModelRegistry()
    info = registry.save_classifier(
        model=model,
        metadata={
            "model_type": model_type,
            "metrics": metrics,
            "feature_dim": X.shape[1],
            "embedding_model": nlp_config.embedding_model,
        },
    )

    logger.info("Fraud classifier trained. Metrics: %s", metrics)
    return {
        "artifact_path": info.artifact_path,
        "metrics": metrics,
        "model_type": model_type,
        "version": info.version,
    }


def _train_torch_classifier(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 0.001,
):
    from .fraud_classifier import FraudNet

    input_dim = X_train.shape[1]
    model = FraudNet(input_dim)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    X_train_t = torch.from_numpy(X_train)
    y_train_t = torch.from_numpy(y_train).float().view(-1, 1)
    X_test_t = torch.from_numpy(X_test)
    y_test_t = torch.from_numpy(y_test).float().view(-1, 1)

    dataset = torch.utils.data.TensorDataset(X_train_t, y_train_t)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    for epoch in range(epochs):
        model.train()
        for batch_X, batch_y in loader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
        if (epoch + 1) % 10 == 0:
            model.eval()
            with torch.no_grad():
                test_outputs = model(X_test_t)
                test_loss = criterion(test_outputs, y_test_t)
                logger.debug("Epoch %d/%d, Test Loss: %.4f", epoch + 1, epochs, test_loss)

    model.eval()
    with torch.no_grad():
        y_pred = (model(X_test_t).numpy() > 0.5).astype(int).flatten()
        y_prob = model(X_test_t).numpy().flatten()

    class TorchWrapper:
        def __init__(self, model):
            self.model = model
            self.classes_ = np.array([0, 1])

        def predict(self, X):
            self.model.eval()
            with torch.no_grad():
                preds = (model(torch.from_numpy(X)).numpy() > 0.5).astype(int).flatten()
            return preds

        def predict_proba(self, X):
            self.model.eval()
            with torch.no_grad():
                probs = model(torch.from_numpy(X)).numpy().flatten()
            return np.column_stack([1 - probs, probs])

    return TorchWrapper(model)
