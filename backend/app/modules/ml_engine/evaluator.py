from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    f1_score,
    precision_score,
    precision_recall_curve,
    recall_score,
    roc_auc_score,
)


@dataclass
class EvaluationResult:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    false_positive_rate: float
    false_negative_rate: float
    training_time_seconds: float
    prediction_latency_ms: float
    confusion_matrix: list[list[int]]


def evaluate_predictions(y_true, y_pred, y_prob, training_time_seconds: float, latency_ms: float) -> EvaluationResult:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    y_prob = np.asarray(y_prob)
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    pr_auc = auc(recall, precision)
    return EvaluationResult(
        accuracy=float(accuracy_score(y_true, y_pred)),
        precision=float(precision_score(y_true, y_pred, zero_division=0)),
        recall=float(recall_score(y_true, y_pred, zero_division=0)),
        f1=float(f1_score(y_true, y_pred, zero_division=0)),
        roc_auc=float(roc_auc_score(y_true, y_prob)) if len(set(y_true.tolist())) > 1 else 0.0,
        pr_auc=float(pr_auc),
        false_positive_rate=float(fp / (fp + tn)) if (fp + tn) else 0.0,
        false_negative_rate=float(fn / (fn + tp)) if (fn + tp) else 0.0,
        training_time_seconds=float(training_time_seconds),
        prediction_latency_ms=float(latency_ms),
        confusion_matrix=cm.tolist(),
    )


def measure_latency_ms(model, X_sample) -> float:
    if X_sample is None or len(X_sample) == 0:
        return 0.0
    start = time.perf_counter()
    if hasattr(model, "predict_proba"):
        model.predict_proba(X_sample)
    else:
        model.predict(X_sample)
    return (time.perf_counter() - start) * 1000.0
