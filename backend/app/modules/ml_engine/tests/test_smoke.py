from backend.app.modules.ml_engine import ml_config


def test_ml_config_paths_exist():
    assert ml_config.artifact_root.name == "models"
