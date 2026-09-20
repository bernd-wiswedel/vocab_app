"""
Browser-level tests for the test round.

The round itself runs in the browser: `GET /test` ships every term of the round
as JSON and `templates/test.html` asks the questions, so none of the asking,
revealing, skipping, direction-switching or grading is reachable from the Flask
test client. These tests drive a real headless Chrome against a real server and
are the only coverage that logic has.

They skip themselves when Playwright or Chrome is missing, so a machine without
a browser still runs the rest of the suite. Vocabulary is faked at the
`fetch_data` boundary: no Google Sheets, no credentials, no network.
"""

import json
import socket
import threading

import pytest

from google_sheet_io import VocabularyDatabase, VocabularyScore, VocabularyTerm

playwright_api = pytest.importorskip("playwright.sync_api",
                                     reason="playwright is not installed")

pytestmark = pytest.mark.browser

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


def _open_round(browser, server, guest=True, category=CATEGORY):
    """Log in, load the faked vocabulary and land on /test with a round running."""
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

    # Wait for the index to go quiet before starting the round. Every request -
    # a stylesheet or a favicon included - reads the whole session and writes it
    # back, so a /start_test that overlaps with one of those still in flight has
    # its test_data overwritten by the older snapshot and the round never starts.
    page.wait_for_load_state("networkidle")

    page.request.post(
        f"{server}/start_test",
        form={"language": "Latein", "categories": category},
    )
    page.goto(f"{server}/test")
    assert page.url.endswith("/test"), (
        f"no round started; the app redirected to {page.url}")
    page.wait_for_selector("#question:not(:empty)")
    return page


def _round_data(page):
    return json.loads(page.inner_text("#round-data"))


def _grade_every_question(page, answer="Richtig"):
    """Reveal and grade until the page leaves /test."""
    for _ in range(TERM_COUNT):
        page.click("#reveal")
        page.click(f".grade[data-answer='{answer}']")


class TestRoundInTheBrowser:
    def test_whole_round_costs_exactly_one_request(self, browser, server):
        """The point of the refactor: N questions, one POST."""
        page = _open_round(browser, server)
        posts = []
        page.on("request", lambda r: posts.append(f"{r.method} {r.url}")
                if r.method != "GET" else None)

        _grade_every_question(page)
        page.wait_for_url(f"{server}/review", timeout=10000)

        assert posts == [f"POST {server}/finish_test"], posts
        page.close()

    def test_reveal_shows_the_translation(self, browser, server):
        page = _open_round(browser, server)
        items = _round_data(page)["items"]

        assert page.is_hidden("#answer")
        assert page.inner_text("#question") == items[0]["term"]

        page.click("#reveal")
        assert page.is_visible("#answer")
        assert page.inner_text("#answer-text") == items[0]["translation"]
        page.close()

    def test_switch_direction_flips_the_sides(self, browser, server):
        page = _open_round(browser, server)
        items = _round_data(page)["items"]

        assert page.inner_text("#question") == items[0]["term"]
        page.click("#switch")
        assert page.inner_text("#question") == items[0]["translation"]

        page.click("#reveal")
        assert page.inner_text("#answer-text") == items[0]["term"]
        page.close()

    def test_skip_moves_on_without_grading(self, browser, server):
        page = _open_round(browser, server)
        items = _round_data(page)["items"]

        page.click("#skip")
        assert page.inner_text("#question") == items[1]["term"]
        assert page.inner_text("#correct-count") == "0"
        assert page.inner_text("#wrong-count") == "0"
        page.close()

    def test_counters_track_grading_without_a_request(self, browser, server):
        page = _open_round(browser, server)
        requests = []
        page.on("request", lambda r: requests.append(r.url) if r.method != "GET" else None)

        page.click("#reveal")
        page.click(".grade[data-answer='Richtig']")
        page.click("#reveal")
        page.click(".grade[data-answer='Falsch']")

        assert page.inner_text("#correct-count") == "1"
        assert page.inner_text("#wrong-count") == "1"
        assert page.inner_text("#completed-terms") == "2"
        assert requests == [], requests
        page.close()

    def test_a_reload_resumes_the_round(self, browser, server):
        """The cursor lives in sessionStorage, so a reload must not restart."""
        page = _open_round(browser, server)
        items = _round_data(page)["items"]

        page.click("#reveal")
        page.click(".grade[data-answer='Richtig']")
        assert page.inner_text("#question") == items[1]["term"]

        page.reload()
        page.wait_for_selector("#question:not(:empty)")

        assert page.inner_text("#question") == items[1]["term"]
        assert page.inner_text("#correct-count") == "1"
        page.close()

    def test_answers_reach_the_server_and_land_on_review(self, browser, server):
        page = _open_round(browser, server)

        page.click("#reveal")
        page.click(".grade[data-answer='Falsch']")
        page.click("#finish")
        page.wait_for_url(f"{server}/review", timeout=10000)

        assert "1 Falsch" in page.inner_text("body")
        page.close()

    def test_guest_round_shows_no_status_information(self, browser, server):
        page = _open_round(browser, server, guest=True)
        assert page.locator(".status-info").count() == 0
        page.close()

    def test_password_round_shows_status_information(self, browser, server):
        page = _open_round(browser, server, guest=False)
        assert page.locator(".status-info").count() == TERM_COUNT
        assert page.locator(".status-info[data-position='0']").is_visible()
        page.close()
