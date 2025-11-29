"""Shared test fixtures and configuration."""

import pytest
import os
import tempfile
from datetime import date, timedelta
from collections import OrderedDict
from flask import session

from app import app as flask_app
from google_sheet_io import VocabularyTerm, VocabularyScore, VocabularyDatabase
from level import LevelSystem, Urgency


@pytest.fixture
def app():
    """Create and configure a test Flask application."""
    # Create a temporary directory for session files
    test_session_dir = tempfile.mkdtemp()
    
    # Set environment variable for LOGIN_PASSWORD
    original_password = os.environ.get('LOGIN_PASSWORD')
    os.environ['LOGIN_PASSWORD'] = 'test_password'
    
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test_secret_key',
        'SESSION_TYPE': 'filesystem',
        'SESSION_FILE_DIR': test_session_dir,
        'WTF_CSRF_ENABLED': False
    })
    
    yield flask_app
    
    # Restore original password
    if original_password is not None:
        os.environ['LOGIN_PASSWORD'] = original_password
    elif 'LOGIN_PASSWORD' in os.environ:
        del os.environ['LOGIN_PASSWORD']
    
    # Cleanup
    import shutil
    shutil.rmtree(test_session_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def authenticated_client(client):
    """Create an authenticated test client."""
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['guest_mode'] = False
    return client


@pytest.fixture
def guest_client(client):
    """Create a guest-mode authenticated test client."""
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['guest_mode'] = True
    return client


@pytest.fixture
def sample_vocab_terms():
    """Create sample vocabulary terms for testing."""
    return [
        VocabularyTerm(
            term="domus",
            translation="das Haus",
            language="Latein",
            category="Lektion 1",
            comment="domus, domūs f."
        ),
        VocabularyTerm(
            term="templum",
            translation="der Tempel",
            language="Latein",
            category="Lektion 1",
            comment="templī n."
        ),
        VocabularyTerm(
            term="house",
            translation="das Haus",
            language="Englisch",
            category="Unit 1",
            comment=""
        ),
        VocabularyTerm(
            term="temple",
            translation="der Tempel",
            language="Englisch",
            category="Unit 1",
            comment=""
        ),
    ]


@pytest.fixture
def sample_vocab_database(sample_vocab_terms):
    """Create a sample VocabularyDatabase for testing."""
    db = VocabularyDatabase()
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    
    # Add terms with various scores
    db.add_vocabulary_item(
        sample_vocab_terms[0],
        VocabularyScore('Red-1', None)
    )
    db.add_vocabulary_item(
        sample_vocab_terms[1],
        VocabularyScore('Red-2', yesterday)
    )
    db.add_vocabulary_item(
        sample_vocab_terms[2],
        VocabularyScore('Yellow-1', week_ago)
    )
    db.add_vocabulary_item(
        sample_vocab_terms[3],
        VocabularyScore('Green', (date.today() - timedelta(days=30)).isoformat())
    )
    
    return db


@pytest.fixture
def mock_vocab_data(sample_vocab_database):
    """Fixture to inject vocabulary database into Flask session."""
    def _inject(client):
        with client.session_transaction() as sess:
            sess['vocab_data'] = sample_vocab_database
    return _inject


@pytest.fixture
def sample_test_data():
    """Create sample test data for testing test flow."""
    return [
        {
            'Fremdsprache': 'domus',
            'Deutsch': 'das Haus',
            'Sprache': 'Latein',
            'Kategorie': 'Lektion 1',
            'Zusatz': 'domus, domūs f.',
            'score_status': 'Red-1',
            'score_date': None,
            'test_result': 'skipped'
        },
        {
            'Fremdsprache': 'templum',
            'Deutsch': 'der Tempel',
            'Sprache': 'Latein',
            'Kategorie': 'Lektion 1',
            'Zusatz': 'templī n.',
            'score_status': 'Red-2',
            'score_date': (date.today() - timedelta(days=1)).isoformat(),
            'test_result': 'skipped'
        },
    ]


@pytest.fixture
def mock_google_sheets_data():
    """Mock data structure that would come from Google Sheets."""
    return {
        'latin_vocab': [
            {
                'Fremdsprache': 'domus',
                'Deutsch': 'das Haus',
                'Kategorie': 'Lektion 1',
                'Zusatz': 'domus, domūs f.',
                'Sprache': 'Latein'
            },
            {
                'Fremdsprache': 'templum',
                'Deutsch': 'der Tempel',
                'Kategorie': 'Lektion 1',
                'Zusatz': 'templī n.',
                'Sprache': 'Latein'
            },
        ],
        'english_vocab': [
            {
                'Fremdsprache': 'house',
                'Deutsch': 'das Haus',
                'Kategorie': 'Unit 1',
                'Zusatz': '',
                'Sprache': 'Englisch'
            },
        ],
        'scores': {
            'domus': {'status': 'Red-1', 'date': '', 'language': 'Latein'},
            'templum': {'status': 'Red-2', 'date': date.today().isoformat(), 'language': 'Latein'},
        }
    }


@pytest.fixture
def freeze_date():
    """Fixture to freeze time for date-dependent tests."""
    from freezegun import freeze_time
    with freeze_time("2025-11-29"):
        yield date(2025, 11, 29)
