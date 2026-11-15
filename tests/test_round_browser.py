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

import pytest

from tests.browser_support import (  # noqa: F401  (fixtures are used by name)
    CATEGORY, TERM_COUNT, browser, log_in, server)

pytestmark = pytest.mark.browser


def _open_round(browser, server, guest=True, category=CATEGORY):
    """Log in, load the faked vocabulary and land on /test with a round running."""
    page = log_in(browser, server, guest)
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
