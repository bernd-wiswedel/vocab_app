"""
Fixtures shared by the browser tests: the real app on a real port with the
Google Sheets boundary faked out, and a headless Chromium.

Import the fixtures into a test module by name. Everything skips when
Playwright or Chrome is missing.
"""

import socket
import threading

import pytest

from google_sheet_io import VocabularyDatabase, VocabularyScore, VocabularyTerm

playwright_api = pytest.importorskip("playwright.sync_api",
                                     reason="playwright is not installed")

CATEGORY = "Latein: Lektion 1"
TERM_COUNT = 6


def _fake_database():
    """Six Latin terms in one lesson, all at Red-1 so all of them are testable."""
    database = VocabularyDatabase()
    for index in range(TERM_COUNT):
        database.add_vocabulary_item(
            VocabularyTerm(
                term=f"vocabulum{index}",
                translation=f"das Wort {index}",
                language="Latein",
                category=CATEGORY,
                comment=f"vocabuli{index} n.",
            ),
            VocabularyScore("Red-1", None),
        )
    return database


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    """The real app on a real port, with the Google Sheets boundary faked out."""
    from werkzeug.serving import make_server

    import app as app_module

    # Flask-Session bound its directory when app.py was imported, so the
    # session directory conftest set up is the one in use here too.
    app_module.app.config.update(SECRET_KEY="browser-test-secret")
    original_fetch = app_module.fetch_data
    app_module.fetch_data = lambda user_name: _fake_database()

    port = _free_port()
    httpd = make_server("127.0.0.1", port, app_module.app, threaded=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        app_module.fetch_data = original_fetch


@pytest.fixture(scope="module")
def browser():
    """
    Chromium, however this machine happens to have it.

    Locally that is usually the system Chrome; CI installs Playwright's own
    build. Trying the system one first keeps `playwright install` optional for
    developers who already have Chrome.
    """
    launch_args = ["--no-sandbox", "--disable-gpu"]
    with playwright_api.sync_playwright() as playwright:
        launched = None
        for attempt in ({"channel": "chrome"}, {}):
            try:
                launched = playwright.chromium.launch(args=launch_args, **attempt)
                break
            except Exception:
                continue
        if launched is None:
            pytest.skip("no usable Chromium for Playwright "
                        "(try: python -m playwright install chromium)")
        try:
            yield launched
        finally:
            launched.close()


def log_in(browser, server, guest=True):
    """A new page logged in as Alice, with the faked vocabulary loaded, on the index."""
    page = browser.new_context().new_page()
    page.goto(f"{server}/login")
    page.select_option("#user", "Alice")
    if guest:
        page.click("button[name='guest_login']")
    else:
        page.fill("input[name='password']", "alice_pw")
        page.click("button[type='submit']:not([name='guest_login'])")
    # the loading page fetches the vocabulary, then forwards to the index
    page.wait_for_url(f"{server}/", timeout=15000)
    return page
