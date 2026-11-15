from backend.context.categories import sanitize_application_name


def test_sanitize_application_name_removes_browser_window_titles() -> None:
    assert sanitize_application_name("YouTube - Google Chrome") == "Google Chrome"
    assert sanitize_application_name("Private page — Firefox") == "Firefox"
    assert sanitize_application_name("Google Chrome") == "Google Chrome"


def test_sanitize_application_name_preserves_non_browser_names() -> None:
    assert sanitize_application_name(" Visual Studio Code ") == "Visual Studio Code"
    assert sanitize_application_name("  ") == "Unknown"
