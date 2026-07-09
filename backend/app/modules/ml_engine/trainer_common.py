from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight

from .config import ml_config
from .evaluator import evaluate_predictions, measure_latency_ms
from .feature_store import CATEGORICAL_FEATURES, MODEL_FEATURES, NUMERIC_FEATURES, split_features_target
from .preprocessing import build_preprocessor
from .model_registry import ArtifactInfo, next_version, save_model

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - optional dependency
    XGBClassifier = None

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - optional dependency
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


@dataclass
class TrainingArtifact:
    model_type: str
    version: str
    artifact_info: ArtifactInfo
    feature_names: list[str]
    selected_features: list[dict[str, Any]]
    model_kind: str


class FraudNet(nn.Module if nn is not None else object):
    def __init__(self, input_dim: int, hidden_dims: tuple[int, int, int] = (128, 64, 32), dropout: float = 0.25):
        if nn is None:
            raise RuntimeError("PyTorch is not available")
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.dropout = dropout
        layers: list[nn.Module] = []
        dims = (input_dim,) + hidden_dims
        for start, end in zip(dims[:-1], dims[1:]):
            layers.append(nn.Linear(start, end))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
        layers.append(nn.Linear(hidden_dims[-1], 1))
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x).squeeze(-1)

    def predict_proba(self, x):
        import torch
        self.eval()
        with torch.no_grad():
            logits = self.forward(torch.as_tensor(x, dtype=torch.float32))
            probs = torch.sigmoid(logits).cpu().numpy()
        return np.vstack([1.0 - probs, probs]).T


def _dense_array(x):
    if hasattr(x, "toarray"):
        return x.toarray()
    return np.asarray(x)


def _collapse_feature_name(transformed_name: str) -> str:
    if "__" in transformed_name:
        suffix = transformed_name.split("__", 1)[1]
    else:
        suffix = transformed_name
    for raw in NUMERIC_FEATURES + CATEGORICAL_FEATURES:
        if suffix == raw or suffix.startswith(raw + "_"):
            return raw
    return suffix


def _feature_importance_from_model(model, feature_names: list[str], X_sample, y_sample, model_type: str) -> list[dict[str, Any]]:
    if model_type == "logistic_regression" and hasattr(model, "coef_"):
        weights = np.abs(np.asarray(model.coef_)[0])
    elif hasattr(model, "feature_importances_"):
        weights = np.asarray(model.feature_importances_)
    elif model_type == "neural_network" and hasattr(model, "coefs_"):
        weights = np.abs(np.asarray(model.coefs_[0])).mean(axis=1)
    else:
        weights = np.zeros(len(feature_names), dtype=float)
    aggregated: dict[str, float] = {}
    for name, weight in zip(feature_names, weights):
        raw = _collapse_feature_name(name)
        aggregated[raw] = aggregated.get(raw, 0.0) + float(weight)
    order = sorted(aggregated.items(), key=lambda item: item[1], reverse=True)
    return [{"feature": name, "importance": float(weight)} for name, weight in order[:25]]


def _fit_torch_model(X_train, y_train, X_val, y_val, input_dim: int, pos_weight: float):
    if torch is None or nn is None:
        raise RuntimeError("PyTorch is not available")
    model = FraudNet(input_dim=input_dim)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], dtype=torch.float32))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    train_ds = TensorDataset(torch.as_tensor(X_train, dtype=torch.float32), torch.as_tensor(y_train, dtype=torch.float32))
    val_ds = TensorDataset(torch.as_tensor(X_val, dtype=torch.float32), torch.as_tensor(y_val, dtype=torch.float32))
    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=512, shuffle=False)

    best_state = None
    best_val_loss = float("inf")
    patience = 10
    patience_left = patience

    for _epoch in range(100):
        model.train()
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                logits = model(batch_x)
                loss = criterion(logits, batch_y)
                val_loss += float(loss.item()) * len(batch_x)
        val_loss /= max(1, len(val_ds))
        if val_loss < best_val_loss - 1e-4:
            best_val_loss = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_left = patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return model


def _predict_proba(model, X):
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    if hasattr(model, "decision_function"):
        scores = model.decision_function(X)
        return 1.0 / (1.0 + np.exp(-scores))
    if torch is not None and hasattr(model, "forward"):
        return model.predict_proba(X)[:, 1]
    raise RuntimeError("Model does not support probability prediction")


def _build_estimator(model_type: str, y_train: np.ndarray):
    pos = max(1, int((y_train == 1).sum()))
    neg = max(1, int((y_train == 0).sum()))
    imbalance = neg / pos
    if model_type == "logistic_regression":
        return LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs")
    if model_type == "random_forest":
        return RandomForestClassifier(n_estimators=300, max_depth=18, class_weight="balanced", random_state=ml_config.random_state, n_jobs=-1)
    if model_type == "xgboost":
        if XGBClassifier is not None:
            return XGBClassifier(
                n_estimators=350,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                reg_lambda=1.0,
                scale_pos_weight=imbalance,
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=ml_config.random_state,
                tree_method="hist",
            )
        return HistGradientBoostingClassifier(max_depth=8, learning_rate=0.05, max_iter=200, random_state=ml_config.random_state)
    if model_type == "neural_network":
        if torch is not None:
            return {"kind": "torch", "pos_weight": imbalance, "input_dim": None}
        from sklearn.neural_network import MLPClassifier
        return MLPClassifier(hidden_layer_sizes=(128, 64, 32), activation="relu", alpha=1e-4, max_iter=500, early_stopping=True, random_state=ml_config.random_state)
    raise ValueError(f"Unsupported model_type: {model_type}")


def train_single_model(df: pd.DataFrame, model_type: str, version: str | None = None) -> TrainingArtifact:
    if df.empty:
        raise ValueError("Training dataframe is empty")

    feature_frame, target = split_features_target(df)
    if target is None:
        raise ValueError("Training dataframe must include is_fraud")
    if target.nunique() < 2:
        raise ValueError("Training target needs at least two classes")

    version = version or next_version(model_type)
    class_counts = target.value_counts(dropna=False)
    if len(target) < 8 or class_counts.min() < 2:
        # Small demo datasets can be too tiny for a stratified holdout.
        x_train, x_test, y_train, y_test = feature_frame, feature_frame, target, target
    else:
        x_train, x_test, y_train, y_test = train_test_split(
            feature_frame,
            target,
            test_size=0.2,
            random_state=ml_config.random_state,
            stratify=target,
        )

    preprocessor = build_preprocessor(model_type)
    x_train_proc = preprocessor.fit_transform(x_train)
    x_test_proc = preprocessor.transform(x_test)
    feature_names = list(preprocessor.get_feature_names_out())
    model_spec = _build_estimator(model_type, np.asarray(y_train))

    start = time.perf_counter()
    model_kind = "sklearn"
    if model_type == "neural_network" and isinstance(model_spec, dict) and model_spec.get("kind") == "torch":
        model_kind = "torch"
        torch_model = _fit_torch_model(
            _dense_array(x_train_proc),
            np.asarray(y_train).astype(np.float32),
            _dense_array(x_test_proc),
            np.asarray(y_test).astype(np.float32),
            input_dim=_dense_array(x_train_proc).shape[1],
            pos_weight=float(model_spec["pos_weight"]),
        )
        model = torch_model
    else:
        model = model_spec
        if hasattr(model, "fit"):
            if model_type == "neural_network" and hasattr(model, "fit"):
                sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)
                try:
                    model.fit(_dense_array(x_train_proc), np.asarray(y_train), sample_weight=sample_weight)
                except TypeError:
                    model.fit(_dense_array(x_train_proc), np.asarray(y_train))
            else:
                model.fit(_dense_array(x_train_proc), np.asarray(y_train))
        else:
            raise RuntimeError("Model does not support fit()")
    training_time_seconds = time.perf_counter() - start

    y_prob = _predict_proba(model, _dense_array(x_test_proc))
    y_pred = (y_prob >= 0.5).astype(int)
    latency_ms = measure_latency_ms(model, _dense_array(x_test_proc[: min(128, len(x_test_proc))]))
    evaluation = evaluate_predictions(np.asarray(y_test), y_pred, y_prob, training_time_seconds, latency_ms)
    importance = _feature_importance_from_model(model, feature_names, _dense_array(x_test_proc), np.asarray(y_test), model_type)

    metrics = {
        "model_name": model_type,
        "model_type": model_type,
        "version": version,
        "accuracy": evaluation.accuracy,
        "precision": evaluation.precision,
        "recall": evaluation.recall,
        "f1": evaluation.f1,
        "roc_auc": evaluation.roc_auc,
        "pr_auc": evaluation.pr_auc,
        "false_positive_rate": evaluation.false_positive_rate,
        "false_negative_rate": evaluation.false_negative_rate,
        "training_time_seconds": evaluation.training_time_seconds,
        "prediction_latency_ms": evaluation.prediction_latency_ms,
        "confusion_matrix": evaluation.confusion_matrix,
    }

    metadata = {
        "model_name": model_type,
        "model_type": model_type,
        "version": version,
        "artifact_format": "torch" if model_kind == "torch" else "pkl",
        "model_kind": model_kind,
        "input_dim": int(_dense_array(x_train_proc).shape[1]),
        "feature_columns": list(feature_frame.columns),
        "preprocessor_features": feature_names,
        "numeric_columns": list(x_train.select_dtypes(include=["number"]).columns),
        "categorical_columns": [c for c in x_train.columns if c not in x_train.select_dtypes(include=["number"]).columns],
        "feature_importance": importance,
        "class_balance": {"negative": int((np.asarray(y_train) == 0).sum()), "positive": int((np.asarray(y_train) == 1).sum())},
        "metrics": metrics,
        "selected_threshold": ml_config.default_threshold,
        "created_at": time.time(),
    }
    if model_kind == "torch":
        metadata["model_config"] = {"input_dim": int(_dense_array(x_train_proc).shape[1]), "hidden_dims": (128, 64, 32), "dropout": 0.25}

    artifact_info = save_model(model, preprocessor, metadata, model_type=model_type, metrics=metrics)
    return TrainingArtifact(
        model_type=model_type,
        version=version,
        artifact_info=artifact_info,
        feature_names=feature_names,
        selected_features=importance,
        model_kind=model_kind,
    )


def select_best_model(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not results:
        return None
    return sorted(
        results,
        key=lambda row: (
            row.get("pr_auc", 0.0),
            row.get("f1", 0.0),
            -row.get("false_positive_rate", 1.0),
        ),
        reverse=True,
    )[0]
