"""
Contract tests against a real Google Sheet.

Everything else mocks the Sheets boundary, which means nothing checks the things
only Google can tell us: that the score tab is still called
``Scores <Sprache> (<Name>)``, that the vocabulary gids still point at the
Latein and Englisch tabs, that the A:C layout and ``values.batchUpdate`` still
behave, and that the service account still authenticates.

They run against a dedicated fixture spreadsheet holding invented vocabulary -
never a learner's sheet - and they put it back the way they found it. They are
NOT part of any automated run: they need a credential, they hit a rate-limited
API and they write shared state. Run them by hand when the sheet layer changes:

    pytest -m sheets

Without credentials they skip, so a checkout with no ``keys/`` still runs green.

The fixture sheet is titled "CI_Test Vokabeln" and is laid out so the
assertions below stay true indefinitely: every scored term carries a
deliberately old date, so it always expires back to Red-1 and nothing drifts
with the calendar.
"""

import glob
import os
from datetime import date

import pytest

import google_sheet_io
from google_sheet_io import (
    COL_NAME_TERM,
    UserSheet,
    _get_sheets_service,
    fetch_data,
    write_scores_to_sheet,
)

pytestmark = pytest.mark.sheets

# Not a secret: the sheet holds invented words and is published for CSV export.
# Reaching it still needs the service account to be shared on it.
FIXTURE_SPREADSHEET_ID = '1MkRfpJW627hSMeFX9wiP8DslgZhA0mPhZkG4NJbR78c'
LEARNER = 'Test'

EXPECTED_TERMS = 12
SCORED_TERM = 'fictivus'      # has a row in the score tab
UNSCORED_TERM = 'scribendum'  # deliberately has none, so writes append


def _has_credentials():
    return bool(os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
                or glob.glob('keys/vocab-app-*.json'))


@pytest.fixture(scope='module')
def learner():
    """Register the fixture spreadsheet as a learner for the duration."""
    if not _has_credentials():
        pytest.skip('no Google service account credentials; see CLAUDE.md')
    sheet = UserSheet(LEARNER, FIXTURE_SPREADSHEET_ID)
    google_sheet_io.USERS[LEARNER] = sheet
    try:
        yield sheet
    finally:
        google_sheet_io.USERS.pop(LEARNER, None)


@pytest.fixture(scope='module')
def score_rows(learner):
    """Read and write the Latein score tab directly, to check what the app wrote."""
    service = _get_sheets_service()
    tab = learner.scores_sheet_name('Latein')

    class Tab:
        def read(self):
            values = service.spreadsheets().values().get(
                spreadsheetId=learner.spreadsheet_id, range=f"'{tab}'!A:C"
            ).execute().get('values', [])
            return {row[0]: row[1:] for row in values[1:] if row}

        def row_count(self):
            values = service.spreadsheets().values().get(
                spreadsheetId=learner.spreadsheet_id, range=f"'{tab}'!A:C"
            ).execute().get('values', [])
            return len(values)

        def restore(self, term, status, updated):
            rows = service.spreadsheets().values().get(
                spreadsheetId=learner.spreadsheet_id, range=f"'{tab}'!A:C"
            ).execute().get('values', [])
            for index, row in enumerate(rows, start=1):
                if row and row[0] == term:
                    service.spreadsheets().values().update(
                        spreadsheetId=learner.spreadsheet_id,
                        range=f"'{tab}'!A{index}:C{index}",
                        valueInputOption='RAW',
                        body={'values': [[term, status, updated]]},
                    ).execute()
                    return

        def clear_row_of(self, term):
            rows = service.spreadsheets().values().get(
                spreadsheetId=learner.spreadsheet_id, range=f"'{tab}'!A:C"
            ).execute().get('values', [])
            for index, row in enumerate(rows, start=1):
                if row and row[0] == term:
                    service.spreadsheets().values().clear(
                        spreadsheetId=learner.spreadsheet_id,
                        range=f"'{tab}'!A{index}:C{index}", body={},
                    ).execute()
                    return

    return Tab()


class TestFetchContract:
    def test_fetch_data_reads_the_fixture_sheet(self, learner):
        database = fetch_data(LEARNER)

        assert len(database.data) == EXPECTED_TERMS, (
            'the fixture sheet has been edited; see this module docstring')

        placement = {term.term: (term.language, term.category) for term in database.data}
        assert placement['fictivus'] == ('Latein', 'CI: Lektion Alpha')
        assert placement['snarfle'] == ('Englisch', 'CI: Unit Two')

        # mockare's Kategorie cell is empty; it inherits the row above it
        assert placement['mockare'] == ('Latein', 'CI: Lektion Alpha')

    def test_a_stale_level_comes_back_as_red_1(self, learner):
        """Every scored row in the fixture is long past its max_days."""
        database = fetch_data(LEARNER)
        scores = {term.term: score for term, score in database.data.items()}

        assert scores['stubium'].status == 'Red-1'   # 'Green' on the sheet
        assert scores['stubium'].date == '2025-11-02'
        assert scores[UNSCORED_TERM].status == 'Red-1'
        assert scores[UNSCORED_TERM].date is None


class TestWriteContract:
    def test_writing_updates_the_row_a_term_already_has(self, learner, score_rows):
        before = score_rows.read()[SCORED_TERM]
        rows_before = score_rows.row_count()
        try:
            written = write_scores_to_sheet(
                [{COL_NAME_TERM: SCORED_TERM, 'score_status': 'Yellow-2'}], 'Latein', LEARNER)
            assert written == 1

            after = score_rows.read()
            assert after[SCORED_TERM] == ['Yellow-2', date.today().isoformat()]
            assert score_rows.row_count() == rows_before, 'the row was duplicated'
        finally:
            score_rows.restore(SCORED_TERM, before[0], before[1])

    def test_writing_appends_a_row_for_a_term_that_has_none(self, learner, score_rows):
        assert UNSCORED_TERM not in score_rows.read(), (
            f'{UNSCORED_TERM} is meant to start without a score row')
        try:
            written = write_scores_to_sheet(
                [{COL_NAME_TERM: UNSCORED_TERM, 'score_status': 'Red-3'}], 'Latein', LEARNER)
            assert written == 1

            assert score_rows.read()[UNSCORED_TERM] == ['Red-3', date.today().isoformat()]
        finally:
            score_rows.clear_row_of(UNSCORED_TERM)
