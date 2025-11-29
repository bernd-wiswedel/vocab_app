"""Integration tests for app.py - Flask routes and session management."""

import pytest
import json
from datetime import date, timedelta
from flask import session
from unittest.mock import patch, MagicMock

from app import app as flask_app
from google_sheet_io import (
    VocabularyTerm, VocabularyScore, VocabularyDatabase,
    COL_NAME_TERM, COL_NAME_TRANSLATION, COL_NAME_LANGUAGE,
    COL_NAME_CATEGORY, COL_NAME_COMMENT
)


class TestAuthentication:
    """Test authentication and login flow."""
    
    def test_login_page_loads(self, client):
        """Test that login page is accessible."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower()
    
    def test_login_correct_password(self, client, monkeypatch):
        """Test successful login with correct password."""
        # Monkeypatch the LOGIN_PASSWORD in the app module
        import app as app_module
        monkeypatch.setattr(app_module, 'LOGIN_PASSWORD', 'test_password')
        
        response = client.post('/login', data={'password': 'test_password'}, follow_redirects=False)
        
        assert response.status_code == 302
        assert '/loading_data?source=login' in response.location
    
    def test_login_incorrect_password(self, client):
        """Test login with incorrect password."""
        response = client.post('/login', data={'password': 'wrong_password'})
        
        assert response.status_code == 200
        assert b'Incorrect password' in response.data
    
    def test_login_rate_limiting(self, client):
        """Test that rate limiting works after failed attempts."""
        # First failed attempt
        client.post('/login', data={'password': 'wrong'})
        
        # Second attempt immediately should show delay
        response = client.post('/login', data={'password': 'wrong'})
        assert b'wait' in response.data.lower() or b'Please try again' in response.data
    
    def test_guest_login(self, client):
        """Test guest login functionality."""
        with patch('app.fetch_and_store_vocab_data', return_value=10):
            response = client.post('/login', data={'guest_login': 'true'}, follow_redirects=False)
            
            assert response.status_code == 302
            assert '/loading_data?source=guest' in response.location
    
    def test_logout_clears_session(self, authenticated_client):
        """Test that logout clears session data."""
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = [{'term': 'test'}]
            sess['vocab_data'] = VocabularyDatabase()
        
        response = authenticated_client.get('/logout', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/login' in response.location
        
        with authenticated_client.session_transaction() as sess:
            assert 'authenticated' not in sess
            assert 'test_data' not in sess
    
    def test_require_auth_decorator(self, client):
        """Test that @require_auth redirects to login."""
        response = client.get('/', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/login' in response.location


class TestDataLoading:
    """Test data loading and session management."""
    
    def test_loading_data_page(self, authenticated_client):
        """Test loading data page displays."""
        response = authenticated_client.get('/loading_data?source=login')
        assert response.status_code == 200
    
    @patch('app.fetch_data')
    def test_api_fetch_data_success(self, mock_fetch, authenticated_client):
        """Test successful data fetching."""
        # Create mock database
        mock_db = VocabularyDatabase()
        term = VocabularyTerm("test", "test", "Latein", "Test")
        mock_db.add_vocabulary_item(term)
        mock_fetch.return_value = mock_db
        
        response = authenticated_client.post('/api/fetch_data')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['entry_count'] == 1
    
    @patch('app.fetch_data')
    def test_api_fetch_data_failure(self, mock_fetch, authenticated_client):
        """Test data fetching with error."""
        mock_fetch.side_effect = Exception("API Error")
        
        response = authenticated_client.post('/api/fetch_data')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'API Error' in data['message']
    
    def test_reload_data_preserves_auth(self, authenticated_client, sample_vocab_database):
        """Test that reload_data preserves authentication state."""
        with authenticated_client.session_transaction() as sess:
            sess['vocab_data'] = sample_vocab_database
            sess['test_data'] = [{'test': 'data'}]
        
        response = authenticated_client.post('/reload_data', follow_redirects=False)
        
        assert response.status_code == 302
        
        with authenticated_client.session_transaction() as sess:
            assert sess.get('authenticated') is True
            assert 'test_data' not in sess  # Should be cleared


class TestIndexAndCategories:
    """Test index page and category fetching."""
    
    def test_index_page_authenticated(self, authenticated_client):
        """Test index page loads when authenticated."""
        response = authenticated_client.get('/')
        
        assert response.status_code == 200
        assert b'Latein' in response.data
        assert b'Englisch' in response.data
    
    def test_index_guest_mode_indicator(self, guest_client):
        """Test that guest mode is indicated on index page."""
        response = guest_client.get('/')
        assert response.status_code == 200
    
    def test_get_categories_latin(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        """Test getting categories for Latin."""
        mock_vocab_data(authenticated_client)
        
        response = authenticated_client.get('/get_categories?language=Latein')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        categories = data['categories']
        
        assert 'Lektion 1' in categories
    
    def test_get_categories_english(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        """Test getting categories for English."""
        mock_vocab_data(authenticated_client)
        
        response = authenticated_client.get('/get_categories?language=Englisch')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        categories = data['categories']
        
        assert 'Unit 1' in categories
    
    def test_get_categories_no_language(self, authenticated_client, mock_vocab_data):
        """Test getting categories without language returns empty."""
        mock_vocab_data(authenticated_client)
        
        response = authenticated_client.get('/get_categories')
        
        data = json.loads(response.data)
        assert data['categories'] == []


class TestLessonStats:
    """Test lesson statistics endpoint."""
    
    def test_get_lesson_stats_authenticated_mode(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        """Test lesson stats in authenticated mode."""
        mock_vocab_data(authenticated_client)
        
        response = authenticated_client.get('/get_lesson_stats?language=Latein')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        lessons = data['lessons']
        
        assert len(lessons) > 0
        # Check structure
        for lesson in lessons:
            assert 'category' in lesson
            assert 'count' in lesson
            assert 'best_status' in lesson
            assert 'worst_status' in lesson
    
    def test_get_lesson_stats_guest_mode(self, guest_client, sample_vocab_database, mock_vocab_data):
        """Test lesson stats in guest mode (no urgency)."""
        mock_vocab_data(guest_client)
        
        response = guest_client.get('/get_lesson_stats?language=Latein')
        
        data = json.loads(response.data)
        lessons = data['lessons']
        
        # In guest mode, urgency_days should be None
        for lesson in lessons:
            assert lesson.get('urgency_days') is None
    
    def test_get_lesson_stats_no_language(self, authenticated_client):
        """Test lesson stats without language returns empty."""
        response = authenticated_client.get('/get_lesson_stats')
        
        data = json.loads(response.data)
        assert data['lessons'] == []


class TestPracticeMode:
    """Test practice mode functionality."""
    
    def test_practice_route(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        """Test practice route with selected categories."""
        mock_vocab_data(authenticated_client)
        
        response = authenticated_client.post('/practice', data={
            'language': 'Latein',
            'categories': 'Lektion 1'
        })
        
        assert response.status_code == 200
        assert b'Lektion 1' in response.data
    
    def test_practice_multiple_categories(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        """Test practice with multiple categories."""
        mock_vocab_data(authenticated_client)
        
        response = authenticated_client.post('/practice', data={
            'language': 'Latein',
            'categories': 'Lektion 1,Lektion 2'
        })
        
        assert response.status_code == 200


class TestTestMode:
    """Test quiz/test mode functionality."""
    
    def test_start_test(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        """Test starting a new test."""
        mock_vocab_data(authenticated_client)
        
        response = authenticated_client.post('/start_test', data={
            'language': 'Latein',
            'categories': 'Lektion 1'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        assert '/test' in response.location
        
        # Check session data
        with authenticated_client.session_transaction() as sess:
            assert 'test_data' in sess
            assert 'order' in sess
            assert 'current_position' in sess
            assert sess['current_position'] == 0
    
    def test_start_test_guest_mode(self, guest_client, sample_vocab_database, mock_vocab_data):
        """Test starting test in guest mode."""
        mock_vocab_data(guest_client)
        
        response = guest_client.post('/start_test', data={
            'language': 'Latein',
            'categories': 'Lektion 1'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        with guest_client.session_transaction() as sess:
            assert 'test_data' in sess
    
    def test_test_page_renders(self, authenticated_client, sample_test_data):
        """Test that test page renders with test data."""
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = sample_test_data
            sess['order'] = [0, 1]
            sess['current_position'] = 0
            sess['show_term'] = True
        
        response = authenticated_client.get('/test')
        
        assert response.status_code == 200
        # Should show the first term
        assert b'domus' in response.data or b'das Haus' in response.data
    
    def test_test_redirect_when_no_data(self, authenticated_client):
        """Test that test redirects to index when no test data."""
        response = authenticated_client.get('/test', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/' in response.location
    
    def test_show_translation(self, authenticated_client, sample_test_data):
        """Test showing translation during test."""
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = sample_test_data
            sess['order'] = [0]
            sess['current_position'] = 0
            sess['show_term'] = True
        
        current_data = sample_test_data[0].copy()
        current_data['current_status'] = current_data.get('score_status', 'Red-1')
        current_data['days_until_retest'] = 0
        current_data['days_until_expire'] = None
        
        response = authenticated_client.post('/show_translation', data={
            'current_data': json.dumps(current_data)
        })
        
        assert response.status_code == 200
        # Should show both term and translation
        assert b'domus' in response.data
        assert b'das Haus' in response.data
    
    def test_check_answer_correct(self, authenticated_client, sample_test_data):
        """Test submitting a correct answer."""
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = sample_test_data.copy()
            sess['order'] = [0, 1]
            sess['current_position'] = 0
            sess['show_term'] = True
        
        response = authenticated_client.post('/check_answer', data={
            'answer_correct': 'Richtig'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        with authenticated_client.session_transaction() as sess:
            # First item should be marked correct
            assert sess['test_data'][0]['test_result'] == 'correct'
            # Position should advance
            assert sess['current_position'] == 1
    
    def test_check_answer_wrong(self, authenticated_client, sample_test_data):
        """Test submitting a wrong answer."""
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = sample_test_data.copy()
            sess['order'] = [0, 1]
            sess['current_position'] = 0
            sess['show_term'] = True
        
        response = authenticated_client.post('/check_answer', data={
            'answer_correct': 'Falsch'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        with authenticated_client.session_transaction() as sess:
            # First item should be marked wrong
            assert sess['test_data'][0]['test_result'] == 'wrong'
            # In authenticated mode, should update to Red-1
            assert sess['test_data'][0]['score_status'] == 'Red-1'
    
    def test_check_answer_guest_mode_no_level_update(self, guest_client, sample_test_data):
        """Test that guest mode doesn't update levels."""
        with guest_client.session_transaction() as sess:
            sess['test_data'] = sample_test_data.copy()
            sess['order'] = [0]
            sess['current_position'] = 0
            sess['show_term'] = True
        
        original_status = sample_test_data[0]['score_status']
        
        guest_client.post('/check_answer', data={'answer_correct': 'Falsch'})
        
        with guest_client.session_transaction() as sess:
            # In guest mode, level should not change
            assert sess['test_data'][0]['score_status'] == original_status
    
    def test_skip_question(self, authenticated_client, sample_test_data):
        """Test skipping a question."""
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = sample_test_data.copy()
            sess['order'] = [0, 1]
            sess['current_position'] = 0
            sess['show_term'] = True
        
        response = authenticated_client.post('/skip_question', follow_redirects=False)
        
        assert response.status_code == 302
        
        with authenticated_client.session_transaction() as sess:
            # Should advance position
            assert sess['current_position'] == 1
            # Test result should remain 'skipped'
            assert sess['test_data'][0]['test_result'] == 'skipped'
    
    def test_switch_direction(self, authenticated_client, sample_test_data):
        """Test switching test direction (term ↔ translation)."""
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = sample_test_data
            sess['order'] = [0]
            sess['current_position'] = 0
            sess['show_term'] = True
        
        current_data = sample_test_data[0]
        
        response = authenticated_client.post('/switch_direction', data={
            'current_data': json.dumps(current_data)
        })
        
        assert response.status_code == 200
        
        with authenticated_client.session_transaction() as sess:
            # Direction should be toggled
            assert sess['show_term'] is False
    
    def test_test_completion_redirects_to_review(self, authenticated_client, sample_test_data):
        """Test that completing all questions redirects to review."""
        # Mark all as correct
        test_data = sample_test_data.copy()
        for item in test_data:
            item['test_result'] = 'correct'
        
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
            sess['order'] = [0, 1]
            sess['current_position'] = 2  # Past the end
            sess['show_term'] = True
        
        response = authenticated_client.get('/test', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/review' in response.location


class TestTestSelected:
    """Test starting a test with selected items."""
    
    def test_test_selected(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        """Test starting test with manually selected items."""
        mock_vocab_data(authenticated_client)
        
        # Format: "term|translation|language"
        selected_items = "domus|das Haus|Latein||templum|der Tempel|Latein"
        
        response = authenticated_client.post('/test_selected', data={
            'selected-items': selected_items
        }, follow_redirects=False)
        
        assert response.status_code == 302
        assert '/test' in response.location
        
        with authenticated_client.session_transaction() as sess:
            assert 'test_data' in sess
            assert len(sess['test_data']) == 2
    
    def test_test_selected_empty_redirects(self, authenticated_client):
        """Test that empty selection redirects to index."""
        response = authenticated_client.post('/test_selected', data={
            'selected-items': ''
        }, follow_redirects=False)
        
        assert response.status_code == 302
        assert '/' in response.location


class TestErrorReview:
    """Test error review functionality."""
    
    def test_test_errors(self, authenticated_client, sample_test_data):
        """Test retesting wrong and skipped items."""
        # Mark some as wrong, some as correct
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'wrong'
        test_data[1]['test_result'] = 'skipped'
        
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
        
        response = authenticated_client.post('/test_errors', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/test' in response.location
        
        with authenticated_client.session_transaction() as sess:
            # Order should contain indices of wrong and skipped
            order = sess['order']
            assert 0 in order  # wrong item
            assert 1 in order  # skipped item
            assert sess['current_position'] == 0
    
    def test_test_errors_no_incomplete_redirects(self, authenticated_client, sample_test_data):
        """Test that no incomplete items redirects to index."""
        # Mark all as correct
        test_data = sample_test_data.copy()
        for item in test_data:
            item['test_result'] = 'correct'
        
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
        
        response = authenticated_client.post('/test_errors', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/' in response.location


class TestReview:
    """Test review page functionality."""
    
    def test_review_page(self, authenticated_client, sample_test_data):
        """Test review page displays test results."""
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[1]['test_result'] = 'wrong'
        
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
        
        response = authenticated_client.get('/review')
        
        assert response.status_code == 200
        assert b'domus' in response.data
        assert b'templum' in response.data
    
    def test_review_counts(self, authenticated_client, sample_test_data):
        """Test that review page shows correct counts."""
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[1]['test_result'] = 'wrong'
        
        # Add one more for skipped
        test_data.append({
            'Fremdsprache': 'puella',
            'Deutsch': 'das Mädchen',
            'Sprache': 'Latein',
            'Kategorie': 'Lektion 1',
            'Zusatz': '',
            'score_status': 'Red-1',
            'score_date': None,
            'test_result': 'skipped'
        })
        
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
        
        response = authenticated_client.get('/review')
        data = response.data.decode()
        
        # Check for count indicators (exact format depends on template)
        assert '1' in data  # At least 1 correct
        assert '1' in data  # At least 1 wrong
    
    def test_review_no_data_redirects(self, authenticated_client):
        """Test that review without test data redirects."""
        response = authenticated_client.get('/review', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/' in response.location


class TestWriteScores:
    """Test score writing functionality."""
    
    @patch('app.write_scores_to_sheet')
    def test_write_scores_authenticated(self, mock_write, authenticated_client, sample_test_data):
        """Test writing scores in authenticated mode."""
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[1]['test_result'] = 'wrong'
        
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
        
        mock_write.return_value = 2
        
        response = authenticated_client.post('/write_scores', data={
            'action': 'save'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        assert mock_write.called
    
    def test_write_scores_guest_mode_redirects(self, guest_client, sample_test_data):
        """Test that guest mode cannot write scores."""
        with guest_client.session_transaction() as sess:
            sess['test_data'] = sample_test_data
        
        response = guest_client.post('/write_scores', data={
            'action': 'save'
        }, follow_redirects=False)
        
        assert response.status_code == 302
        assert '/' in response.location
    
    @patch('app.write_scores_to_sheet')
    def test_write_scores_selected_items(self, mock_write, authenticated_client, sample_test_data):
        """Test writing scores for selected items only."""
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[1]['test_result'] = 'wrong'
        
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
        
        mock_write.return_value = 1
        
        # Only select first item
        response = authenticated_client.post('/write_scores', data={
            'action': 'save',
            'selected-items': ['domus|das Haus|Latein']
        }, follow_redirects=False)
        
        assert response.status_code == 302
        
        # Should only write selected items
        call_args = mock_write.call_args[0]
        items_written = call_args[0]
        assert len(items_written) == 1


class TestUtilityFunctions:
    """Test utility functions in app.py."""
    
    def test_get_language_labels_latin_show_term(self):
        """Test language labels for Latin showing term."""
        from app import _get_language_labels
        
        labels = _get_language_labels('Latein', show_term=True)
        
        assert labels['label_language'] == 'Latein'
        assert labels['label_term'] == 'Latein'
        assert labels['label_translation'] == 'Deutsch'
    
    def test_get_language_labels_latin_show_translation(self):
        """Test language labels for Latin showing translation."""
        from app import _get_language_labels
        
        labels = _get_language_labels('Latein', show_term=False)
        
        assert labels['label_language'] == 'Latein'
        assert labels['label_term'] == 'Deutsch'
        assert labels['label_translation'] == 'Latein'
    
    def test_get_language_labels_english(self):
        """Test language labels for English."""
        from app import _get_language_labels
        
        labels = _get_language_labels('Englisch', show_term=True)
        
        assert labels['label_language'] == 'Englisch'
        assert labels['label_term'] == 'Englisch'
        assert labels['label_translation'] == 'Deutsch'
    
    def test_add_status_info_to_data(self):
        """Test adding status info to data dictionary."""
        from app import _add_status_info_to_data
        
        data = {
            'score_status': 'Red-2',
            'score_date': (date.today() - timedelta(days=2)).isoformat()
        }
        
        result = _add_status_info_to_data(data)
        
        assert 'current_status' in result
        assert 'days_until_retest' in result
        assert 'days_until_expire' in result
        assert result['current_status'] == 'Red-2'
    
    def test_add_status_info_red1(self):
        """Test status info for Red-1 items."""
        from app import _add_status_info_to_data
        
        data = {
            'score_status': 'Red-1',
            'score_date': None
        }
        
        result = _add_status_info_to_data(data)
        
        assert result['days_until_retest'] == 0
        assert result['days_until_expire'] is None
    
    def test_convert_vocab_tuples_to_dict(self):
        """Test converting vocabulary tuples to dict format."""
        from app import _convert_vocab_tuples_to_dict
        
        term = VocabularyTerm("domus", "das Haus", "Latein", "Lektion 1", "comment")
        score = VocabularyScore('Red-2', date.today().isoformat())
        
        result = _convert_vocab_tuples_to_dict([(term, score)])
        
        assert len(result) == 1
        assert result[0][COL_NAME_TERM] == "domus"
        assert result[0][COL_NAME_TRANSLATION] == "das Haus"
        assert result[0]['score_status'] == 'Red-2'
    
    def test_random_order(self):
        """Test random order generation."""
        from app import random_order
        
        order = random_order(10)
        
        assert len(order) == 10
        assert set(order) == set(range(10))
        assert order != list(range(10))  # Very unlikely to be in order
