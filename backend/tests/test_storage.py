from pathlib import Path

from app.health import check_storage


def test_check_storage_writable(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    logs = tmp_path / "logs"
    monkeypatch.setattr("app.health.settings.storage_path", str(storage))
    monkeypatch.setattr("app.health.settings.log_path", str(logs))

    result = check_storage()
    assert result["status"] == "ok"
    assert Path(result["paths"]["storage_path"]).exists()
    assert Path(result["paths"]["log_path"]).exists()
