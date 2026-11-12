from wrench.core import paths


def test_app_data_dir_uses_override(tmp_path, monkeypatch):
    monkeypatch.setenv("WRENCH_DATA_DIR", str(tmp_path / "data"))
    assert paths.app_data_dir() == tmp_path / "data"
    assert (tmp_path / "data").is_dir()
    assert paths.settings_file() == tmp_path / "data" / "settings.json"
    assert paths.tools_data_dir() == tmp_path / "data" / "tools"
    assert paths.logs_dir().is_dir()


def test_resource_dir_is_repo_root_in_dev():
    assert (paths.resource_dir() / "backend" / "pyproject.toml").is_file()
