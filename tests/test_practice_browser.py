"""
Browser-level tests for the cover on the practice page.

The cover (`📄 Abdecken`) blurs every row below the current one, so a learner
can go through the page row by row instead of holding a hand over the screen.
It lives entirely in the script of `templates/practice.html`, so only a real
browser reaches it.
"""

import pytest

from tests.browser_support import (  # noqa: F401  (fixtures are used by name)
    CATEGORY, TERM_COUNT, browser, log_in, server)

pytestmark = pytest.mark.browser

ROWS = ".item-row"


def _open_practice(browser, server, guest=True):
    """Log in and land on the practice page of the faked lesson."""
    page = log_in(browser, server, guest)
    # /practice is a POST; submit it the way the index page's form does
    page.evaluate(
        """([language, categories]) => {
            const form = document.createElement('form');
            form.method = 'post';
            form.action = '/practice';
            for (const [name, value] of [['language', language], ['categories', categories]]) {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = name;
                input.value = value;
                form.appendChild(input);
            }
            document.body.appendChild(form);
            form.submit();
        }""",
        ["Latein", CATEGORY],
    )
    page.wait_for_url(f"{server}/practice")
    assert page.locator(ROWS).count() == TERM_COUNT
    return page


def _covered(page):
    """Which rows are covered, as a list of booleans in page order."""
    return page.eval_on_selector_all(
        ROWS, "rows => rows.map(row => row.classList.contains('covered'))")


def _uncovered_up_to(position):
    return [index > position for index in range(TERM_COUNT)]


class TestPracticeCover:
    def test_page_starts_uncovered(self, browser, server):
        page = _open_practice(browser, server)

        assert _covered(page) == [False] * TERM_COUNT
        assert page.is_hidden("#cover-controls")
        page.close()

    def test_cover_leaves_only_the_first_row_visible(self, browser, server):
        page = _open_practice(browser, server)

        page.click("#cover-btn")

        assert _covered(page) == _uncovered_up_to(0)
        assert page.inner_text("#cover-progress") == f"1 / {TERM_COUNT}"
        assert page.is_disabled("#cover-back")
        page.close()

    def test_weiter_and_back_move_the_cover_one_row(self, browser, server):
        page = _open_practice(browser, server)
        page.click("#cover-btn")

        page.click("#cover-next")
        page.click("#cover-next")
        assert _covered(page) == _uncovered_up_to(2)

        page.click("#cover-back")
        assert _covered(page) == _uncovered_up_to(1)
        assert page.inner_text("#cover-progress") == f"2 / {TERM_COUNT}"
        page.close()

    def test_weiter_stops_at_the_last_row(self, browser, server):
        page = _open_practice(browser, server)
        page.click("#cover-btn")

        for _ in range(TERM_COUNT - 1):
            page.click("#cover-next")

        assert _covered(page) == [False] * TERM_COUNT
        assert page.is_disabled("#cover-next")
        page.close()

    def test_tapping_a_covered_row_uncovers_the_next_without_selecting(self, browser, server):
        page = _open_practice(browser, server)
        page.click("#cover-btn")

        # even a tap right on a covered row's checkbox only moves the cover
        page.click(f"{ROWS}.covered >> nth=3 >> input[type='checkbox']")

        assert _covered(page) == _uncovered_up_to(1)
        assert page.locator("input[name='item-checkbox']:checked").count() == 0
        assert page.is_disabled("#test-selected-button")
        page.close()

    def test_visible_rows_can_still_be_selected(self, browser, server):
        page = _open_practice(browser, server)
        page.click("#cover-btn")

        page.click(f"{ROWS} >> nth=0 >> input[type='checkbox']")

        assert page.is_checked(f"{ROWS} >> nth=0 >> input[type='checkbox']")
        # the page enables the button on the next animation frame
        page.wait_for_selector("#test-selected-button:enabled", timeout=2000)
        assert _covered(page) == _uncovered_up_to(0)
        page.close()

    def test_keys_move_the_cover(self, browser, server):
        page = _open_practice(browser, server)
        page.click("#cover-btn")
        page.click("h1")  # focus away from the toggle button

        page.keyboard.press("Space")
        page.keyboard.press("ArrowDown")
        page.keyboard.press("ArrowDown")
        page.keyboard.press("ArrowUp")

        assert _covered(page) == _uncovered_up_to(2)
        page.close()

    def test_toggling_off_uncovers_everything(self, browser, server):
        page = _open_practice(browser, server)
        page.click("#cover-btn")
        page.click("#cover-next")

        page.click("#cover-btn")

        assert _covered(page) == [False] * TERM_COUNT
        assert page.is_hidden("#cover-controls")
        page.close()

    def test_a_reload_keeps_the_position(self, browser, server):
        page = _open_practice(browser, server)
        page.click("#cover-btn")
        page.click("#cover-next")
        page.click("#cover-next")

        # a reload of a POST page would resubmit; the app re-renders the same page
        page.reload()
        page.wait_for_selector(ROWS)

        assert _covered(page) == _uncovered_up_to(2)
        assert page.is_visible("#cover-controls")
        page.close()
