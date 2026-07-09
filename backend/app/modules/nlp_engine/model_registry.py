from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib

from .config import nlp_config


@dataclass
class NLPArtifactInfo:
    model_type: str
    version: str
    artifact_dir: str
    artifact_path: str
    metadata_path: str
    metadata: dict[str, Any]


class NLPModelRegistry:
    def __init__(self):
        self.root = nlp_config.artifact_root
        self.root.mkdir(parents=True, exist_ok=True)

    def _next_version(self) -> str:
        prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
        existing = sorted(
            p.name for p in self.root.iterdir()
            if p.is_dir() and p.name.startswith(prefix)
        )
        return f"{prefix}-{len(existing) + 1:03d}"

    def save_classifier(
        self,
        model: Any,
        metadata: dict[str, Any],
        model_type: str = "nlp_classifier",
    ) -> NLPArtifactInfo:
        version = self._next_version()
        version_dir = self.root / f"{model_type}_{version}"
        version_dir.mkdir(parents=True, exist_ok=True)
        metadata.update({
            "version": version,
            "model_type": model_type,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        })
        artifact_path = version_dir / "model.pkl"
        joblib.dump(model, artifact_path)
        meta_path = version_dir / "metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2, default=str))
        self._update_latest(model_type, artifact_path, meta_path, metadata)
        return NLPArtifactInfo(
            model_type=model_type,
            version=version,
            artifact_dir=str(version_dir),
            artifact_path=str(artifact_path),
            metadata_path=str(meta_path),
            metadata=metadata,
        )

    def _update_latest(
        self, model_type: str, artifact_path: Path, meta_path: Path, metadata: dict[str, Any]
    ):
        latest_model = self.root / f"{model_type}_latest.pkl"
        latest_meta = self.root / f"{model_type}_latest.json"
        if artifact_path.exists():
            import shutil
            shutil.copy2(str(artifact_path), str(latest_model))
        metadata["is_latest"] = True
        latest_meta.write_text(json.dumps(metadata, indent=2, default=str))

    def load_classifier(self, version: Optional[str] = None) -> dict[str, Any]:
        if version:
            for d in sorted(self.root.iterdir(), reverse=True):
                if d.is_dir() and version in d.name:
                    model = joblib.load(d / "model.pkl")
                    meta = json.loads((d / "metadata.json").read_text())
                    return {"model": model, "metadata": meta}
        latest = self.root / "nlp_classifier_latest.pkl"
        latest_meta = self.root / "nlp_classifier_latest.json"
        if latest.exists():
            model = joblib.load(latest)
            meta = json.loads(latest_meta.read_text()) if latest_meta.exists() else {}
            return {"model": model, "metadata": meta}
        raise FileNotFoundError("No NLP classifier found")

    def list_versions(self) -> list[dict[str, Any]]:
        versions = []
        for d in sorted(self.root.iterdir(), reverse=True):
            if not d.is_dir() or "nlp_classifier" not in d.name:
                continue
            meta_path = d / "metadata.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                versions.append(meta)
        return versions

    def save_embeddings_index(self, embeddings: list[list[float]], metadata: list[dict[str, Any]]):
        path = self.root / "embeddings_index.pkl"
        joblib.dump({"embeddings": embeddings, "metadata": metadata}, path)

    def load_embeddings_index(self) -> dict[str, Any]:
        path = self.root / "embeddings_index.pkl"
        if path.exists():
            return joblib.load(path)
        return {"embeddings": [], "metadata": []}
