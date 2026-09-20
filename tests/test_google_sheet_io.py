"""Unit tests for google_sheet_io.py - Data layer and Google Sheets integration."""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from google_sheet_io import (
    VocabularyTerm, VocabularyScore, VocabularyDatabase,
    COL_NAME_TERM, COL_NAME_TRANSLATION, COL_NAME_LANGUAGE,
    COL_NAME_CATEGORY, COL_NAME_COMMENT,
    _fetch_data_from_google_sheet, fetch_data, write_scores_to_sheet,
    USERS, UserSheet, get_user_sheet
)
from level import LevelSystem, RED_1_LOW_URGENCY


class TestVocabularyTerm:
    """Test the VocabularyTerm class."""
    
    def test_vocabulary_term_creation(self):
        """Test creating a VocabularyTerm."""
        term = VocabularyTerm(
            term="domus",
            translation="das Haus",
            language="Latein",
            category="Lektion 1",
            comment="domus, domūs f."
        )
        
        assert term.term == "domus"
        assert term.translation == "das Haus"
        assert term.language == "Latein"
        assert term.category == "Lektion 1"
        assert term.comment == "domus, domūs f."
    
    def test_vocabulary_term_default_comment(self):
        """Test that comment defaults to empty string."""
        term = VocabularyTerm(
            term="house",
            translation="das Haus",
            language="Englisch",
            category="Unit 1"
        )
        
        assert term.comment == ""
    
    def test_vocabulary_term_str(self):
        """Test string representation."""
        term = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        assert "domus" in str(term)
        assert "das Haus" in str(term)
    
    def test_vocabulary_term_equality(self):
        """Test equality comparison."""
        term1 = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1", "comment")
        term2 = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1", "comment")
        term3 = VocabularyTerm("templum", "der Tempel", "Latein", "Lektion 1", "comment")
        
        assert term1 == term2
        assert term1 != term3
        assert term1 != "not a term"
    
    def test_vocabulary_term_hashable(self):
        """Test that VocabularyTerm can be used as dict key."""
        term1 = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        term2 = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        
        # Same terms should have same hash
        assert hash(term1) == hash(term2)
        
        # Can be used as dict keys
        test_dict = {term1: "value1"}
        test_dict[term2] = "value2"
        
        # Should overwrite since they're equal
        assert len(test_dict) == 1
        assert test_dict[term1] == "value2"


class TestVocabularyScore:
    """Test the VocabularyScore class."""
    
    def test_vocabulary_score_creation(self):
        """Test creating a VocabularyScore."""
        today = date.today().isoformat()
        score = VocabularyScore(status='Red-2', date=today)
        
        assert score.status == 'Red-2'
        assert score.date == today
        assert score.urgency is not None
    
    def test_vocabulary_score_defaults(self):
        """Test default values."""
        score = VocabularyScore()
        
        assert score.status == 'Red-1'
        assert score.date is None
        assert score.urgency == RED_1_LOW_URGENCY
    
    def test_vocabulary_score_update(self):
        """Test updating a score."""
        score = VocabularyScore('Red-1', None)
        today = date.today().isoformat()
        
        score.update_score('Red-2', today)
        
        assert score.status == 'Red-2'
        assert score.date == today
        # Urgency should be recalculated
        assert score.urgency != RED_1_LOW_URGENCY


class TestVocabularyDatabase:
    """Test the VocabularyDatabase class."""
    
    def test_database_creation(self):
        """Test creating an empty database."""
        db = VocabularyDatabase()
        assert len(db.data) == 0
        assert isinstance(db.data, dict)
    
    def test_add_vocabulary_item(self):
        """Test adding vocabulary items."""
        db = VocabularyDatabase()
        term = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        score = VocabularyScore('Red-1', None)
        
        db.add_vocabulary_item(term, score)
        
        assert len(db.data) == 1
        assert db.get_score(term) == score
    
    def test_add_vocabulary_item_default_score(self):
        """Test adding item with default score."""
        db = VocabularyDatabase()
        term = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        
        db.add_vocabulary_item(term)
        
        score = db.get_score(term)
        assert score is not None
        assert score.status == 'Red-1'
    
    def test_get_by_language(self):
        """Test filtering by language."""
        db = VocabularyDatabase()
        
        latin_term = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        english_term = VocabularyTerm("house", "das Haus", "Englisch", "Unit 1")
        
        db.add_vocabulary_item(latin_term)
        db.add_vocabulary_item(english_term)
        
        latin_items = db.get_by_language("Latein")
        english_items = db.get_by_language("Englisch")
        
        assert len(latin_items) == 1
        assert len(english_items) == 1
        assert latin_items[0][0] == latin_term
        assert english_items[0][0] == english_term
    
    def test_get_by_category(self):
        """Test filtering by language and category."""
        db = VocabularyDatabase()
        
        term1 = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        term2 = VocabularyTerm("templum", "der Tempel", "Latein", "Lektion 1")
        term3 = VocabularyTerm("puella", "das Mädchen", "Latein", "Lektion 2")
        
        db.add_vocabulary_item(term1)
        db.add_vocabulary_item(term2)
        db.add_vocabulary_item(term3)
        
        lektion1_items = db.get_by_category("Latein", "Lektion 1")
        lektion2_items = db.get_by_category("Latein", "Lektion 2")
        
        assert len(lektion1_items) == 2
        assert len(lektion2_items) == 1
    
    def test_get_testable_terms_guest_mode(self):
        """Test get_testable_terms in guest mode returns all terms."""
        db = VocabularyDatabase()
        
        # Add terms with various readiness states
        term1 = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        term2 = VocabularyTerm("templum", "der Tempel", "Latein", "Lektion 1")
        
        db.add_vocabulary_item(term1, VocabularyScore('Red-1', None))
        db.add_vocabulary_item(term2, VocabularyScore('Red-2', date.today().isoformat()))
        
        # In guest mode, should return all terms
        testable = db.get_testable_terms(guest_mode=True)
        assert len(testable) == 2
    
    def test_get_testable_terms_filters_not_ready(self):
        """Test that non-guest mode filters out not-ready terms."""
        db = VocabularyDatabase()
        
        term1 = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        term2 = VocabularyTerm("templum", "der Tempel", "Latein", "Lektion 1")
        
        # term1: Red-1 (testable)
        db.add_vocabulary_item(term1, VocabularyScore('Red-1', None))
        
        # term2: Red-2 tested today (not ready yet, min_days=1)
        db.add_vocabulary_item(term2, VocabularyScore('Red-2', date.today().isoformat()))
        
        testable = db.get_testable_terms(guest_mode=False)
        
        # Should only include term1 (Red-1)
        assert len(testable) == 1
        assert testable[0][0] == term1
    
    def test_get_testable_terms_sorts_by_urgency(self):
        """Test that testable terms are sorted by urgency."""
        db = VocabularyDatabase()
        
        # Create terms with different urgency levels
        term1 = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        term2 = VocabularyTerm("templum", "der Tempel", "Latein", "Lektion 1")
        term3 = VocabularyTerm("puella", "das Mädchen", "Latein", "Lektion 1")
        
        # term1: Red-2, 6 days ago (expires in 1 day) - most urgent
        db.add_vocabulary_item(
            term1, 
            VocabularyScore('Red-2', (date.today() - timedelta(days=6)).isoformat())
        )
        
        # term2: Red-2, 2 days ago (expires in 5 days) - less urgent
        db.add_vocabulary_item(
            term2,
            VocabularyScore('Red-2', (date.today() - timedelta(days=2)).isoformat())
        )
        
        # term3: Red-1 (low urgency)
        db.add_vocabulary_item(term3, VocabularyScore('Red-1', None))
        
        testable = db.get_testable_terms(guest_mode=False)
        
        # Should be sorted: term1 (urgent), term2 (less urgent), term3 (Red-1)
        assert testable[0][0] == term1
        assert testable[1][0] == term2
        assert testable[2][0] == term3
    
    def test_get_testable_terms_limit(self):
        """Test that limit parameter works."""
        db = VocabularyDatabase()
        
        for i in range(10):
            term = VocabularyTerm(f"term{i}", f"translation{i}", "Latein", "Lektion 1")
            db.add_vocabulary_item(term, VocabularyScore('Red-1', None))
        
        testable = db.get_testable_terms(limit=5, guest_mode=True)
        assert len(testable) == 5
    
    def test_update_score(self):
        """Test updating a score for an existing term."""
        db = VocabularyDatabase()
        term = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1")
        
        db.add_vocabulary_item(term, VocabularyScore('Red-1', None))
        
        today = date.today().isoformat()
        db.update_score(term, 'Red-2', today)
        
        score = db.get_score(term)
        assert score.status == 'Red-2'
        assert score.date == today
    
    def test_preserves_insertion_order(self):
        """Test that database preserves insertion order (Google Sheets order)."""
        db = VocabularyDatabase()
        
        terms = [
            VocabularyTerm(f"term{i}", f"trans{i}", "Latein", "Lektion 1")
            for i in range(5)
        ]
        
        for term in terms:
            db.add_vocabulary_item(term)
        
        # Check that order is preserved
        retrieved_terms = [term for term, score in db.data.items()]
        assert retrieved_terms == terms


class TestFetchDataFromGoogleSheet:
    """Test the _fetch_data_from_google_sheet function."""
    
    @patch('google_sheet_io.pd.read_csv')
    def test_fetch_data_basic(self, mock_read_csv):
        """Test basic data fetching from CSV."""
        # Mock CSV data
        mock_df = pd.DataFrame({
            'Fremdsprache': ['Header', 'domus', 'templum'],
            'Deutsch': ['Header', 'das Haus', 'der Tempel'],
            'Kategorie': ['Header', 'Lektion 1', ''],
            'Zusatz': ['Header', 'domus, domūs f.', 'templī n.']
        })
        mock_read_csv.return_value = mock_df
        
        result = _fetch_data_from_google_sheet('http://fake-url', 'Latein')
        
        # Should skip first row (header) and auto-fill category
        assert len(result) == 2
        assert result[0]['Fremdsprache'] == 'domus'
        assert result[0]['Kategorie'] == 'Lektion 1'
        assert result[0]['Sprache'] == 'Latein'
        
        # Second row should inherit category
        assert result[1]['Fremdsprache'] == 'templum'
        assert result[1]['Kategorie'] == 'Lektion 1'  # Auto-filled
    
    @patch('google_sheet_io.pd.read_csv')
    def test_fetch_data_skips_blank_terms(self, mock_read_csv):
        """Test that rows with blank Fremdsprache are skipped."""
        mock_df = pd.DataFrame({
            'Fremdsprache': ['Header', 'domus', '', 'templum'],
            'Deutsch': ['Header', 'das Haus', 'should skip', 'der Tempel'],
            'Kategorie': ['Header', 'Lektion 1', 'Lektion 1', 'Lektion 1'],
            'Zusatz': ['Header', 'comment1', 'comment2', 'comment3']
        })
        mock_read_csv.return_value = mock_df
        
        result = _fetch_data_from_google_sheet('http://fake-url', 'Latein')
        
        # Should skip the blank term row
        assert len(result) == 2
        assert result[0]['Fremdsprache'] == 'domus'
        assert result[1]['Fremdsprache'] == 'templum'
    
    @patch('google_sheet_io.pd.read_csv')
    def test_fetch_data_handles_nan(self, mock_read_csv):
        """Test that NaN values are converted to empty strings."""
        mock_df = pd.DataFrame({
            'Fremdsprache': ['Header', 'domus', 'templum'],
            'Deutsch': ['Header', 'das Haus', 'der Tempel'],
            'Kategorie': ['Header', 'Lektion 1', pd.NA],
            'Zusatz': ['Header', pd.NA, 'comment']
        })
        mock_read_csv.return_value = mock_df
        
        result = _fetch_data_from_google_sheet('http://fake-url', 'Latein')
        
        # NaN should become empty string
        assert result[0]['Zusatz'] == ''
        # Category should auto-fill from previous
        assert result[1]['Kategorie'] == 'Lektion 1'


class TestWriteScoresToSheet:
    """Test the write_scores_to_sheet function."""
    
    @patch('google_sheet_io._get_sheets_service')
    def test_write_scores_basic(self, mock_get_service):
        """Test basic score writing functionality."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        
        # Mock existing data
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': [['Fremdsprache', 'Status', 'Date']]
        }
        mock_service.spreadsheets().values().batchUpdate().execute.return_value = {}
        
        vocab_items = [{'Fremdsprache': 'domus', 'score_status': 'Red-2'}]
        rows_written = write_scores_to_sheet(vocab_items, 'Englisch', 'Alice')
        
        assert rows_written == 1
        assert mock_service.spreadsheets().values().batchUpdate.called
    
    def test_write_scores_invalid_language(self):
        """Test that invalid language raises error."""
        with pytest.raises(ValueError, match="Unsupported language"):
            write_scores_to_sheet([], 'Spanish', 'Alice')

    @patch('google_sheet_io._get_sheets_service')
    def test_write_scores_targets_users_sheet(self, mock_get_service):
        """Test that scores land in the selected user's spreadsheet and tab."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {'values': [['Fremdsprache', 'Status', 'Date']]}
        mock_service.spreadsheets().values().batchUpdate().execute.return_value = {}

        write_scores_to_sheet([{'Fremdsprache': 'domus', 'score_status': 'Red-2'}], 'Latein', user_name='Bob')

        bob = USERS['Bob']
        read_kwargs = mock_service.spreadsheets().values().get.call_args.kwargs
        assert read_kwargs['spreadsheetId'] == bob.spreadsheet_id
        assert read_kwargs['range'].startswith("'Scores Latein (Bob)'")
        write_kwargs = mock_service.spreadsheets().values().batchUpdate.call_args.kwargs
        assert write_kwargs['spreadsheetId'] == bob.spreadsheet_id
        assert write_kwargs['body']['data'][0]['range'].startswith("'Scores Latein (Bob)'")

    def test_write_scores_unknown_user(self):
        """Test that an unknown user raises error before touching the API."""
        with pytest.raises(ValueError, match="Unknown user"):
            write_scores_to_sheet([], 'Latein', user_name='Mallory')


class TestUserSheets:
    """Test the per-user spreadsheet configuration."""

    def test_users_come_from_config(self):
        """USERS mirrors the [user:<Name>] sections conftest put into VOCAB_APP_CONFIG."""
        assert list(USERS) == ['Alice', 'Bob']
        assert USERS['Alice'].spreadsheet_id == 'alice-sheet-id'
        assert USERS['Bob'].spreadsheet_id == 'bob-sheet-id'

    def test_users_have_distinct_spreadsheets(self):
        ids = [sheet.spreadsheet_id for sheet in USERS.values()]
        assert len(set(ids)) == len(ids)

    def test_user_sheet_urls_and_tab_names(self):
        sheet = UserSheet('Bob', 'SHEET-ID')
        assert sheet.vocab_csv_url('Latein') == 'https://docs.google.com/spreadsheets/d/SHEET-ID/export?format=csv&gid=0'
        assert sheet.vocab_csv_url('Englisch') == 'https://docs.google.com/spreadsheets/d/SHEET-ID/export?format=csv&gid=897548588'
        assert sheet.scores_sheet_name('Latein') == 'Scores Latein (Bob)'
        assert sheet.scores_sheet_name('Englisch') == 'Scores Englisch (Bob)'

    def test_get_user_sheet_unknown(self):
        with pytest.raises(ValueError, match="Unknown user"):
            get_user_sheet('Mallory')

    @patch('google_sheet_io._fetch_scores', return_value={})
    @patch('google_sheet_io._fetch_data_from_google_sheet', return_value=[])
    def test_fetch_data_reads_users_sheet(self, mock_fetch_csv, mock_fetch_scores):
        """Test that fetch_data reads the CSV exports and scores of the given user."""
        fetch_data('Bob')

        bob = USERS['Bob']
        urls = [call.args[0] for call in mock_fetch_csv.call_args_list]
        assert urls == [bob.vocab_csv_url('Latein'), bob.vocab_csv_url('Englisch')]
        assert mock_fetch_scores.call_args.args[0] is bob
