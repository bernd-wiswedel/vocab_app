"""Integration tests for app.py - Flask routes and session management."""

import pytest
import json
import re
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
    
    def test_login_correct_password(self, client):
        """Test successful login with the password from the learner config."""
        response = client.post('/login', data={'user': 'Alice', 'password': 'alice_pw'}, follow_redirects=False)

        assert response.status_code == 302
        assert '/loading_data?source=login' in response.location
        with client.session_transaction() as sess:
            assert sess['user'] == 'Alice'
            assert sess['guest_mode'] is False

    def test_login_without_user_is_rejected(self, client):
        """Test that there is no default learner: a POST without user fails."""
        response = client.post('/login', data={'password': 'alice_pw'})
        assert response.status_code == 200
        assert b'Unknown user' in response.data
        with client.session_transaction() as sess:
            assert not sess.get('authenticated')

    def test_guest_only_learner_cannot_use_password(self, client, monkeypatch):
        """Test that a learner without a configured password is refused even for an empty password."""
        import app as app_module
        monkeypatch.setitem(app_module.LOGIN_PASSWORDS, 'Bob', None)
        response = client.post('/login', data={'user': 'Bob', 'password': ''})
        assert b'Incorrect password' in response.data

    def test_session_without_user_counts_as_logged_out(self, client):
        """Test that a pre-multi-user session (authenticated, no user) is sent to login."""
        with client.session_transaction() as sess:
            sess['authenticated'] = True
        response = client.get('/', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location

    def test_login_page_offers_user_choice(self, client):
        """Test that the login page lists every configured user."""
        response = client.get('/login')
        assert b'<option value="Alice"' in response.data
        assert b'<option value="Bob"' in response.data

    def test_login_page_preselects_user_from_query(self, client):
        """Test that /login?user=<Name> preselects that learner (bookmarkable)."""
        response = client.get('/login?user=Bob')
        assert b'<option value="Bob" selected>' in response.data
        assert b'<option value="Alice" selected>' not in response.data

    def test_login_page_has_favicon_and_password_toggle(self, client):
        """Test the favicon link and the show-password button on the login page."""
        html = client.get('/login').data.decode()
        assert 'rel="icon"' in html and 'favicon.svg' in html
        assert 'id="passwordToggle"' in html
        assert client.get('/static/favicon.svg').status_code == 200

    def test_home_screen_icons_and_manifest(self, client):
        """Test the PNG icons and manifest that tablets use for 'add to home screen'."""
        html = client.get('/login').data.decode()
        assert 'rel="apple-touch-icon"' in html
        assert 'rel="manifest"' in html
        for path in ('/static/apple-touch-icon.png', '/static/icon-192.png', '/static/icon-512.png'):
            assert client.get(path).status_code == 200, path
        manifest = json.loads(client.get('/manifest.webmanifest').data)
        assert manifest['start_url'] == '/login'
        assert {icon['sizes'] for icon in manifest['icons']} == {'192x192', '512x512'}

    def test_manifest_start_url_carries_the_learner(self, client):
        """Test that ?user= reaches start_url, which is where Chrome takes the shortcut URL from."""
        response = client.get('/manifest.webmanifest?user=Bob')
        assert response.mimetype == 'application/manifest+json'
        manifest = json.loads(response.data)
        assert manifest['start_url'] == '/login?user=Bob'
        # A distinct id keeps the two learners as two separate home-screen entries
        assert manifest['id'] == '/login?user=Bob'
        assert 'Bob' in manifest['name']
        assert manifest['short_name'] == 'Bob'

    def test_manifest_ignores_unknown_user(self, client):
        """Test that an unknown ?user falls back to the generic manifest, not to users[0]."""
        manifest = json.loads(client.get('/manifest.webmanifest?user=Mallory').data)
        assert manifest['start_url'] == '/login'
        assert 'Mallory' not in json.dumps(manifest)

    def test_login_page_links_its_learners_manifest(self, client):
        """Test that /login?user=<Name> links the manifest for that same learner."""
        html = client.get('/login?user=Bob').data.decode()
        assert '/manifest.webmanifest?user=Bob' in html

    def test_bare_login_page_links_the_generic_manifest(self, client):
        """Test that a plain /login does not offer a shortcut for the first learner."""
        html = client.get('/login').data.decode()
        assert '/manifest.webmanifest"' in html
        assert 'user=Alice' not in html

    def test_login_page_exposes_username_to_password_managers(self, client):
        """Test the hidden username mirror that lets browsers save one password per learner."""
        response = client.get('/login?user=Bob')
        html = response.data.decode()
        assert 'name="username"' in html
        assert 'autocomplete="username"' in html
        assert 'value="Bob"' in html
        assert 'autocomplete="current-password"' in html

    def test_login_page_ignores_unknown_query_user(self, client):
        """Test that an unknown ?user falls back to the first configured learner."""
        response = client.get('/login?user=Mallory')
        assert b'<option value="Alice" selected>' in response.data

    def test_login_as_second_user(self, client):
        """Test that each user has their own password and lands in their own session."""
        # Alice's password does not open Bob's account
        response = client.post('/login', data={'user': 'Bob', 'password': 'alice_pw'})
        assert response.status_code == 200
        assert b'Incorrect password' in response.data

        with client.session_transaction() as sess:
            sess['failed_attempts'] = 0
        response = client.post('/login', data={'user': 'Bob', 'password': 'bob_pw'}, follow_redirects=False)
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert sess['user'] == 'Bob'
            assert sess['guest_mode'] is False

    def test_login_unknown_user(self, client):
        """Test that an unknown user name is rejected."""
        response = client.post('/login', data={'user': 'Mallory', 'password': 'password'})
        assert response.status_code == 200
        assert b'Unknown user' in response.data

    def test_login_incorrect_password(self, client):
        """Test login with incorrect password."""
        response = client.post('/login', data={'user': 'Alice', 'password': 'wrong_password'})

        assert response.status_code == 200
        assert b'Incorrect password' in response.data
    
    def test_login_rate_limiting(self, client):
        """Test that rate limiting works after failed attempts."""
        # First failed attempt
        client.post('/login', data={'user': 'Alice', 'password': 'wrong'})

        # Second attempt immediately should show delay
        response = client.post('/login', data={'user': 'Alice', 'password': 'wrong'})
        assert b'wait' in response.data.lower() or b'Please try again' in response.data
    
    def test_guest_login(self, client):
        """Test guest login functionality."""
        with patch('app.fetch_and_store_vocab_data', return_value=10):
            response = client.post('/login', data={'user': 'Alice', 'guest_login': 'true'}, follow_redirects=False)

            assert response.status_code == 302
            assert '/loading_data?source=guest' in response.location

    def test_guest_login_for_second_user(self, client):
        """Test that a guest can browse Bob's vocabulary without a password."""
        response = client.post('/login', data={'user': 'Bob', 'guest_login': 'true'}, follow_redirects=False)

        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert sess['user'] == 'Bob'
            assert sess['guest_mode'] is True
    
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
        mock_fetch.assert_called_once_with('Alice')

    @patch('app.fetch_data')
    def test_api_fetch_data_for_session_user(self, mock_fetch, authenticated_client):
        """Test that data is fetched from the logged-in user's sheet."""
        mock_fetch.return_value = VocabularyDatabase()
        with authenticated_client.session_transaction() as sess:
            sess['user'] = 'Bob'

        authenticated_client.post('/api/fetch_data')

        mock_fetch.assert_called_once_with('Bob')

    @patch('app.fetch_data')
    def test_api_fetch_data_failure(self, mock_fetch, authenticated_client):
        """Test data fetching with error."""
        mock_fetch.side_effect = Exception("API Error")
        
        response = authenticated_client.post('/api/fetch_data')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'API Error' in data['message']
    
    def test_reload_data_preserves_user(self, authenticated_client):
        """Test that reloading keeps the session bound to the same learner."""
        with authenticated_client.session_transaction() as sess:
            sess['user'] = 'Bob'

        authenticated_client.post('/reload_data', follow_redirects=False)

        with authenticated_client.session_transaction() as sess:
            assert sess['user'] == 'Bob'
            assert sess['authenticated'] is True

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


def _round_data(response):
    """The round the test page hands to the browser."""
    html = response.data.decode()
    marker = '<script type="application/json" id="round-data">'
    start = html.index(marker) + len(marker)
    return json.loads(html[start:html.index('</script>', start)])


def _put_round(client, test_data, order, round_id='round-1'):
    with client.session_transaction() as sess:
        sess['test_data'] = test_data
        sess['order'] = order
        sess['round_id'] = round_id


def _finish(client, answers, round_id='round-1'):
    return client.post('/finish_test', data={
        'round_id': round_id,
        'answers': json.dumps(answers),
    }, follow_redirects=False)


class TestTestMode:
    """The test page: one GET hands the round over, one POST reports the answers."""

    def test_start_test(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        mock_vocab_data(authenticated_client)

        response = authenticated_client.post('/start_test', data={
            'language': 'Latein',
            'categories': 'Lektion 1'
        }, follow_redirects=False)

        assert response.status_code == 302
        assert '/test' in response.location

        with authenticated_client.session_transaction() as sess:
            assert len(sess['test_data']) == 2
            assert all(term['test_result'] == 'skipped' for term in sess['test_data'])
            assert sorted(sess['order']) == [0, 1]
            assert sess['round_id']
            # The browser owns the cursor and the direction
            assert 'current_position' not in sess
            assert 'show_term' not in sess

    def test_start_test_guest_mode(self, guest_client, sample_vocab_database, mock_vocab_data):
        mock_vocab_data(guest_client)

        response = guest_client.post('/start_test', data={
            'language': 'Latein',
            'categories': 'Lektion 1'
        }, follow_redirects=False)

        assert response.status_code == 302

        with guest_client.session_transaction() as sess:
            assert 'test_data' in sess

    def test_test_page_embeds_the_round(self, authenticated_client, sample_test_data):
        _put_round(authenticated_client, sample_test_data, [1, 0])

        response = authenticated_client.get('/test')

        assert response.status_code == 200
        html = response.data.decode()
        round_data = _round_data(response)
        assert round_data['id'] == 'round-1'
        assert [item['term'] for item in round_data['items']] == ['templum', 'domus']
        assert round_data['items'][0]['translation'] == 'der Tempel'
        assert round_data['items'][0]['comment'] == 'templī n.'
        assert round_data['items'][0]['result'] == 'skipped'
        assert round_data['base'] == {'correct': 0, 'wrong': 0}
        # Labels for both directions come from _get_language_labels
        assert round_data['labels']['Latein'][0]['label_term'] == 'Latein'
        assert round_data['labels']['Latein'][1]['label_term'] == 'Deutsch'
        # One pre-rendered status line per position, templum (Red-2) first
        assert html.count('class="status-info"') == 2
        assert 'data-position="1"' in html
        assert 'level-badge level-red">2<' in html

    def test_test_page_does_not_leak_scores(self, authenticated_client, sample_test_data):
        _put_round(authenticated_client, sample_test_data, [0, 1])
        round_data = _round_data(authenticated_client.get('/test'))
        assert set(round_data['items'][0]) == {'term', 'translation', 'comment', 'language', 'result'}

    def test_test_page_guest_mode_has_no_status(self, guest_client, sample_test_data):
        _put_round(guest_client, sample_test_data, [0, 1])

        response = guest_client.get('/test')

        assert response.status_code == 200
        assert 'class="status-info"' not in response.data.decode()
        assert 'Gast-Modus' in response.data.decode()

    def test_test_page_counts_terms_outside_the_round(self, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[1]['test_result'] = 'wrong'
        _put_round(authenticated_client, test_data, [1])

        round_data = _round_data(authenticated_client.get('/test'))

        assert round_data['base'] == {'correct': 1, 'wrong': 0}
        assert round_data['items'][0]['result'] == 'wrong'

    def test_test_redirect_when_no_data(self, authenticated_client):
        response = authenticated_client.get('/test', follow_redirects=False)

        assert response.status_code == 302
        assert '/' in response.location

    def test_test_redirects_to_review_when_round_is_over(self, authenticated_client, sample_test_data):
        _put_round(authenticated_client, sample_test_data, [])

        response = authenticated_client.get('/test', follow_redirects=False)

        assert response.status_code == 302
        assert '/review' in response.location

    def test_finish_test_records_answers_but_no_level(self, authenticated_client, sample_test_data):
        _put_round(authenticated_client, sample_test_data, [1, 0])

        response = _finish(authenticated_client, [
            {'position': 0, 'answer': 'Richtig'},
            {'position': 1, 'answer': 'Falsch'},
        ])

        assert response.status_code == 302
        assert '/review' in response.location
        with authenticated_client.session_transaction() as sess:
            assert sess['test_data'][1]['test_result'] == 'correct'
            assert sess['test_data'][0]['test_result'] == 'wrong'
            # The level moves when the result is saved, not when it is recorded
            assert sess['test_data'][1]['score_status'] == 'Red-2'
            assert sess['test_data'][0]['score_status'] == 'Red-1'
            assert sess['order'] == []
            assert 'round_id' not in sess

    def test_finish_test_leaves_ungraded_terms_alone(self, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[1]['test_result'] = 'wrong'
        _put_round(authenticated_client, test_data, [0, 1])

        _finish(authenticated_client, [{'position': 0, 'answer': 'Richtig'}])

        with authenticated_client.session_transaction() as sess:
            assert sess['test_data'][0]['test_result'] == 'correct'
            assert sess['test_data'][1]['test_result'] == 'wrong'

    def test_finish_test_guest_mode(self, guest_client, sample_test_data):
        _put_round(guest_client, sample_test_data, [0, 1])

        response = _finish(guest_client, [{'position': 0, 'answer': 'Falsch'}])

        assert '/review' in response.location
        with guest_client.session_transaction() as sess:
            assert sess['test_data'][0]['test_result'] == 'wrong'
            assert sess['test_data'][0]['score_status'] == 'Red-1'

    def test_finish_test_ignores_a_stale_round(self, authenticated_client, sample_test_data):
        _put_round(authenticated_client, sample_test_data, [0, 1], round_id='round-2')

        response = _finish(authenticated_client, [{'position': 0, 'answer': 'Richtig'}], round_id='round-1')

        assert response.status_code == 302
        assert '/test' in response.location
        with authenticated_client.session_transaction() as sess:
            assert sess['test_data'][0]['test_result'] == 'skipped'
            assert sess['order'] == [0, 1]

    def test_finish_test_without_round_redirects(self, authenticated_client, sample_test_data):
        _put_round(authenticated_client, sample_test_data, [])
        response = _finish(authenticated_client, [], round_id='')
        assert response.status_code == 302
        assert '/test' in response.location

    @pytest.mark.parametrize('answers', [
        '[{"position": 5, "answer": "Richtig"}]',
        '[{"position": -1, "answer": "Richtig"}]',
        '[{"position": 0, "answer": "correct"}]',
        '[{"position": 0}]',
        '[1, 2]',
        'not json',
    ])
    def test_finish_test_rejects_bad_answers(self, authenticated_client, sample_test_data, answers):
        _put_round(authenticated_client, sample_test_data, [0, 1])

        response = authenticated_client.post('/finish_test', data={'round_id': 'round-1', 'answers': answers})

        assert response.status_code == 400
        with authenticated_client.session_transaction() as sess:
            assert sess['test_data'][0]['test_result'] == 'skipped'


class TestTestSelected:
    """Starting a test from rows ticked on the practice page."""

    def test_practice_page_numbers_its_rows(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        mock_vocab_data(authenticated_client)

        response = authenticated_client.post('/practice', data={'language': 'Latein', 'categories': 'Lektion 1'})
        html = response.data.decode()

        assert 'name="item-checkbox" value="0"' in html
        assert 'name="item-checkbox" value="1"' in html
        assert 'name="item-checkbox" value="2"' not in html
        assert 'name="language" value="Latein"' in html
        assert 'name="categories" value="Lektion 1"' in html

    def test_test_selected(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        mock_vocab_data(authenticated_client)

        response = authenticated_client.post('/test_selected', data={
            'language': 'Latein',
            'categories': 'Lektion 1',
            'selected-items': '1,0',
        }, follow_redirects=False)

        assert response.status_code == 302
        assert '/test' in response.location

        with authenticated_client.session_transaction() as sess:
            assert [item[COL_NAME_TERM] for item in sess['test_data']] == ['domus', 'templum']
            assert sess['test_data'][0][COL_NAME_CATEGORY] == 'Lektion 1'
            assert sess['round_id']

    def test_test_selected_english_row(self, authenticated_client, sample_vocab_database, mock_vocab_data):
        mock_vocab_data(authenticated_client)

        authenticated_client.post('/test_selected', data={
            'language': 'Englisch', 'categories': 'Unit 1', 'selected-items': '1',
        })

        with authenticated_client.session_transaction() as sess:
            assert [item[COL_NAME_TERM] for item in sess['test_data']] == ['temple']

    def test_test_selected_empty_redirects(self, authenticated_client):
        response = authenticated_client.post('/test_selected', data={
            'selected-items': ''
        }, follow_redirects=False)

        assert response.status_code == 302
        assert '/' in response.location

    @pytest.mark.parametrize('selected', ['2', '-1', 'domus|das Haus|Latein'])
    def test_test_selected_rejects_bad_indices(self, authenticated_client, sample_vocab_database, mock_vocab_data, selected):
        mock_vocab_data(authenticated_client)
        response = authenticated_client.post('/test_selected', data={
            'language': 'Latein', 'categories': 'Lektion 1', 'selected-items': selected,
        })
        assert response.status_code == 400


class TestErrorReview:
    """Another round over the wrong and skipped terms."""

    def test_test_errors(self, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'skipped'
        test_data[1]['test_result'] = 'wrong'
        test_data.append(dict(test_data[0], Fremdsprache='puella', test_result='correct'))

        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data

        response = authenticated_client.post('/test_errors', follow_redirects=False)

        assert response.status_code == 302
        assert '/test' in response.location

        with authenticated_client.session_transaction() as sess:
            # wrong first, then skipped; the correct one is not retested
            assert sess['order'] == [1, 0]
            assert sess['round_id']

    def test_test_errors_no_incomplete_redirects(self, authenticated_client, sample_test_data):
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
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[1]['test_result'] = 'wrong'

        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data

        response = authenticated_client.get('/review')

        assert response.status_code == 200
        assert b'domus' in response.data
        assert b'templum' in response.data

    def test_review_selects_rows_by_index(self, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[1]['test_result'] = 'wrong'
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data

        html = authenticated_client.get('/review').data.decode()

        values = re.findall(r'name="selected-items"\s+value="([^"]*)"', html)
        assert sorted(values) == ['0', '1']

    def test_review_shows_the_level_the_save_will_give(self, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'   # Red-1 -> Red-2
        test_data[1]['test_result'] = 'wrong'     # Red-2 -> Red-1
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data

        html = authenticated_client.get('/review').data.decode()

        assert 'level-badge level-red">2<' in html
        assert 'level-badge level-red">1<' in html
        with authenticated_client.session_transaction() as sess:
            # a projection, not a transition
            assert sess['test_data'][0]['score_status'] == 'Red-1'

    def test_review_disables_saved_rows(self, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[0]['saved'] = True
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data

        html = authenticated_client.get('/review').data.decode()

        assert 'Bereits gespeichert' in html
        assert not re.search(r'<input[^>]*name="selected-items"', html)

    def test_review_counts(self, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[1]['test_result'] = 'wrong'
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

        html = authenticated_client.get('/review').data.decode()

        assert '1 Richtig' in html
        assert '1 Falsch' in html
        assert '1 Übersprungen' in html
        assert '3 Gesamt' in html

    def test_review_no_data_redirects(self, authenticated_client):
        response = authenticated_client.get('/review', follow_redirects=False)

        assert response.status_code == 302
        assert '/' in response.location


class TestWriteScores:
    """Saving: the one place where a result becomes a level."""

    @patch('app.write_scores_to_sheet')
    def test_write_scores_applies_the_level_transition(self, mock_write, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'   # Red-1, never tested
        test_data[1]['test_result'] = 'wrong'     # Red-2, yesterday

        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data

        mock_write.return_value = 2

        response = authenticated_client.post('/write_scores', data={
            'action': 'save'
        }, follow_redirects=False)

        assert response.status_code == 302
        written = {item[COL_NAME_TERM]: item['score_status'] for item in mock_write.call_args.args[0]}
        assert written == {'domus': 'Red-2', 'templum': 'Red-1'}
        assert mock_write.call_args.args[1] == 'Latein'

    @patch('app.write_scores_to_sheet')
    def test_write_scores_uses_session_user(self, mock_write, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'

        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
            sess['user'] = 'Bob'

        authenticated_client.post('/write_scores', data={'action': 'save'}, follow_redirects=False)

        assert mock_write.call_args.args[2] == 'Bob'

    def test_write_scores_guest_mode_redirects(self, guest_client, sample_test_data):
        with guest_client.session_transaction() as sess:
            sess['test_data'] = sample_test_data

        response = guest_client.post('/write_scores', data={
            'action': 'save'
        }, follow_redirects=False)

        assert response.status_code == 302
        assert '/' in response.location

    @patch('app.write_scores_to_sheet')
    def test_write_scores_selected_items(self, mock_write, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        test_data[1]['test_result'] = 'wrong'

        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data

        mock_write.return_value = 1

        response = authenticated_client.post('/write_scores', data={
            'action': 'save',
            'selected-items': ['1']
        }, follow_redirects=False)

        assert response.status_code == 302
        items_written = mock_write.call_args.args[0]
        assert [item[COL_NAME_TERM] for item in items_written] == ['templum']

    @patch('app.write_scores_to_sheet')
    def test_write_scores_updates_session_and_saves_once(self, mock_write, authenticated_client,
                                                         sample_test_data, sample_vocab_database, sample_vocab_terms):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
            sess['vocab_data'] = sample_vocab_database

        authenticated_client.post('/write_scores', data={'action': 'save'})

        with authenticated_client.session_transaction() as sess:
            item = sess['test_data'][0]
            assert item['score_status'] == 'Red-2'
            assert item['score_date'] == date.today().isoformat()
            assert item['saved'] is True
            assert sess['vocab_data'].get_score(sample_vocab_terms[0]).status == 'Red-2'

        # Saving again writes nothing: the result is already in the sheet
        mock_write.reset_mock()
        response = authenticated_client.post('/write_scores', data={'action': 'save'}, follow_redirects=False)
        assert response.status_code == 302
        assert not mock_write.called

    @patch('app.write_scores_to_sheet')
    def test_write_scores_keeps_session_when_the_sheet_fails(self, mock_write, authenticated_client, sample_test_data):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data
        mock_write.side_effect = RuntimeError('quota')

        response = authenticated_client.post('/write_scores', data={'action': 'save'}, follow_redirects=False)

        assert response.status_code == 302
        with authenticated_client.session_transaction() as sess:
            assert sess['test_data'][0]['score_status'] == 'Red-1'
            assert 'saved' not in sess['test_data'][0]

    @pytest.mark.parametrize('selected', ['7', '-1', 'domus|das Haus|Latein'])
    def test_write_scores_rejects_bad_indices(self, authenticated_client, sample_test_data, selected):
        test_data = sample_test_data.copy()
        test_data[0]['test_result'] = 'correct'
        with authenticated_client.session_transaction() as sess:
            sess['test_data'] = test_data

        response = authenticated_client.post('/write_scores', data={'action': 'save', 'selected-items': [selected]})

        assert response.status_code == 400


class TestRoundFlow:
    """A whole round through the real routes, the way the browser drives them."""

    def _play(self, client, answer_for):
        """GET the round, grade every position with answer_for(term), POST the result."""
        response = client.get('/test')
        assert response.status_code == 200
        round_data = _round_data(response)
        answers = [{'position': position, 'answer': answer_for(item['term'])}
                   for position, item in enumerate(round_data['items'])
                   if answer_for(item['term']) is not None]
        response = client.post('/finish_test', data={
            'round_id': round_data['id'], 'answers': json.dumps(answers)
        }, follow_redirects=False)
        assert '/review' in response.location
        return round_data

    @patch('app.write_scores_to_sheet')
    def test_retest_after_wrong_answer_grades_the_final_result_once(
            self, mock_write, authenticated_client, sample_vocab_database, mock_vocab_data):
        mock_vocab_data(authenticated_client)
        authenticated_client.post('/start_test', data={'language': 'Latein', 'categories': 'Lektion 1'})

        # Round 1: templum (Red-2, yesterday) wrong, domus skipped
        self._play(authenticated_client, lambda term: 'Falsch' if term == 'templum' else None)
        with authenticated_client.session_transaction() as sess:
            results = {item[COL_NAME_TERM]: item['test_result'] for item in sess['test_data']}
            assert results == {'domus': 'skipped', 'templum': 'wrong'}

        # Round 2 over the incomplete terms: both right
        response = authenticated_client.post('/test_errors', follow_redirects=False)
        assert '/test' in response.location
        round_data = self._play(authenticated_client, lambda term: 'Richtig')
        assert [item['term'] for item in round_data['items']] == ['templum', 'domus']  # wrong first
        assert round_data['items'][0]['result'] == 'wrong'

        # Save: templum is graded once, on its final result, against its original Red-2.
        # The old code demoted it to Red-1 after round 1 and then promoted that
        # Red-1 to Red-2 after round 2, whatever level it had started from.
        authenticated_client.post('/write_scores', data={'action': 'save'})
        written = {item[COL_NAME_TERM]: item['score_status'] for item in mock_write.call_args.args[0]}
        assert written == {'domus': 'Red-2', 'templum': 'Red-3'}

    @patch('app.write_scores_to_sheet')
    def test_round_in_guest_mode(self, mock_write, guest_client, sample_vocab_database, mock_vocab_data):
        mock_vocab_data(guest_client)
        guest_client.post('/start_test', data={'language': 'Englisch', 'categories': 'Unit 1'})

        response = guest_client.get('/test')
        assert 'class="status-info"' not in response.data.decode()
        # Guests get every term, urgency or not: temple is Green and not due
        round_data = self._play(guest_client, lambda term: 'Richtig' if term == 'house' else 'Falsch')
        assert sorted(item['term'] for item in round_data['items']) == ['house', 'temple']

        html = guest_client.get('/review').data.decode()
        assert '1 Richtig' in html and '1 Falsch' in html
        assert not re.search(r'<input[^>]*name="selected-items"', html)

        response = guest_client.post('/write_scores', data={'action': 'save'}, follow_redirects=False)
        assert response.status_code == 302
        assert not mock_write.called
        with guest_client.session_transaction() as sess:
            assert {item['score_status'] for item in sess['test_data']} == {'Yellow-1', 'Green'}


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
