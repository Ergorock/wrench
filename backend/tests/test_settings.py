from wrench.core.settings import SettingsStore, default_settings, detect_system_language


def test_missing_file_gives_defaults_and_creates_it(tmp_path):
    store = SettingsStore(tmp_path / "settings.json", system_language="fr")
    result = store.load()
    assert result.settings.language == "fr" and result.recovered is False
    assert (tmp_path / "settings.json").is_file()


def test_default_language_en_when_not_french():
    assert default_settings("de").language == "en"


def test_roundtrip(tmp_path):
    store = SettingsStore(tmp_path / "s.json", "en")
    s = store.load().settings.model_copy(update={"theme": "dark"})
    store.save(s)
    assert store.load().settings.theme == "dark"


def test_invalid_json_is_backed_up_and_reset(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{oops", encoding="utf-8")
    result = SettingsStore(p, "en").load()
    assert result.recovered is True and result.settings == default_settings("en")
    assert len(list(tmp_path.glob("settings.bak-*.json"))) == 1


def test_wrong_type_is_treated_as_corrupt(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text('{"theme": 42}', encoding="utf-8")
    assert SettingsStore(p, "en").load().recovered is True


def test_non_object_root_is_treated_as_corrupt(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("[]", encoding="utf-8")
    assert SettingsStore(p, "en").load().recovered is True


def test_missing_and_extra_fields_are_tolerated(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text('{"language": "fr", "future_field": 1}', encoding="utf-8")
    r = SettingsStore(p, "en").load()
    assert r.recovered is False and r.settings.language == "fr" and r.settings.theme == "system"


def test_missing_language_uses_system_language(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{}", encoding="utf-8")
    r = SettingsStore(p, "fr").load()
    assert r.recovered is False and r.settings.language == "fr"


def test_utf8_bom_is_accepted(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text('{"theme": "dark"}', encoding="utf-8-sig")
    assert p.read_bytes().startswith(b"\xef\xbb\xbf")
    r = SettingsStore(p, "en").load()
    assert r.recovered is False and r.settings.theme == "dark"


def test_save_is_atomic_no_tmp_left(tmp_path):
    store = SettingsStore(tmp_path / "s.json", "en")
    store.save(default_settings("en"))
    assert [f.name for f in tmp_path.iterdir()] == ["s.json"]


def test_detect_system_language_never_raises():
    assert detect_system_language() in {"en", "fr"} or len(detect_system_language()) == 2
