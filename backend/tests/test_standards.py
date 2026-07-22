from app.services.standards import map_standard_status, map_standard_type


def test_map_standard_type_inland():
    assert map_standard_type("INLAND", "CN") == "domestic"


def test_map_standard_type_outland():
    assert map_standard_type("OUTLAND", "US") == "foreign"


def test_map_standard_status_active():
    assert map_standard_status("现行有效", "现行有效") == "active"


def test_map_standard_status_obsolete():
    assert map_standard_status("已废止", None) == "obsolete"
