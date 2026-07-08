from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib


MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


class ModelRegistry:
    def __init__(self, base_dir: str | Path = MODELS_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _model_dir(self, category: str) -> Path:
        path = self.base_dir / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, category: str, model: Any, metadata: dict[str, Any]) -> str:
        model_dir = self._model_dir(category)
        version = metadata.get("version", f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
        model_path = model_dir / f"{version}.joblib"
        joblib.dump(model, model_path)
        meta_path = model_dir / f"{version}_meta.json"
        metadata["saved_at"] = datetime.utcnow().isoformat()
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        latest_symlink = model_dir / "latest.joblib"
        if latest_symlink.exists():
            latest_symlink.unlink()
        os.symlink(model_path.name, latest_symlink)
        return version

    def load(self, category: str, version: str | None = None) -> tuple[Any, dict[str, Any]] | None:
        model_dir = self._model_dir(category)
        if version:
            model_path = model_dir / f"{version}.joblib"
            meta_path = model_dir / f"{version}_meta.json"
        else:
            latest = model_dir / "latest.joblib"
            if not latest.exists():
                return None
            model_path = latest.resolve()
            meta_path = model_dir / f"{model_path.stem}_meta.json"
        if not model_path.exists():
            return None
        model = joblib.load(model_path)
        metadata = {}
        if meta_path.exists():
            with open(meta_path) as f:
                metadata = json.load(f)
        return model, metadata

    def list_versions(self, category: str) -> list[dict[str, Any]]:
        model_dir = self._model_dir(category)
        versions = []
        for f in sorted(model_dir.glob("*_meta.json"), reverse=True):
            try:
                with open(f) as mf:
                    meta = json.load(mf)
                meta["version"] = f.stem.replace("_meta", "")
                meta["model_file"] = str(f.with_suffix("").with_suffix(".joblib"))
                versions.append(meta)
            except Exception:
                pass
        return versions

    def get_current_version(self, category: str) -> str | None:
        latest = self._model_dir(category) / "latest.joblib"
        if latest.exists():
            try:
                return latest.resolve().stem
            except Exception:
                pass
        return None

    def rollback(self, category: str, version: str) -> bool:
        model_dir = self._model_dir(category)
        target = model_dir / f"{version}.joblib"
        if not target.exists():
            return False
        latest = model_dir / "latest.joblib"
        if latest.exists():
            latest.unlink()
        os.symlink(target.name, latest)
        return True

    def delete(self, category: str, version: str) -> bool:
        model_dir = self._model_dir(category)
        model_path = model_dir / f"{version}.joblib"
        meta_path = model_dir / f"{version}_meta.json"
        deleted = False
        if model_path.exists():
            model_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
        return deleted
