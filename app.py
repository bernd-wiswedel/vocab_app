from flask import Flask, render_template, request, jsonify, redirect, url_for, session, abort
import pandas as pd
import random
import json
import os
import secrets
import tempfile
from datetime import timedelta
from typing import List, Dict, Any, Optional, Tuple
from google_sheet_io import fetch_data, write_scores_to_sheet, COL_NAME_TERM, COL_NAME_COMMENT, COL_NAME_TRANSLATION, COL_NAME_CATEGORY, COL_NAME_LANGUAGE, VocabularyDatabase, VocabularyTerm, VocabularyScore, USERS
from config import LEARNERS
from level import LevelSystem, RED_1_LOW_URGENCY, NOT_EXPIRED_LOW_URGENCY
from flask import Flask
from flask_session import Session
import time

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
# Save the session only when a request actually changed it. Flask defaults this
# to True, which makes every request - a stylesheet or a favicon included - write
# the whole session back from the snapshot it read; a request that overlaps one
# that did change something then silently restores the older state. The routes
# that mutate nested session data therefore have to set session.modified
# themselves, because that mutation is invisible from the outside.
app.config['SESSION_REFRESH_EACH_REQUEST'] = False
app.config['SESSION_FILE_THRESHOLD'] = 250
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=10)
# gettempdir() honors TMPDIR, so a sandbox with a read-only /tmp still gets a writable directory
app.config['SESSION_FILE_DIR'] = os.environ.get('FLASK_SESSION_DIR', os.path.join(tempfile.gettempdir(), 'flask_session'))
Session(app)

# One password per learner (LOGIN_PASSWORD_<NAME>, or a password key in
# configuration.ini). None: that learner is guest-only.
LOGIN_PASSWORDS = {name: learner.password for name, learner in LEARNERS.items()}

def _convert_vocab_tuples_to_dict(items: List[Tuple[VocabularyTerm, VocabularyScore]]) -> List[Dict[str, Any]]:
    """Convert list of (VocabularyTerm, VocabularyScore) tuples to dictionary format"""
    result = []
    for term, score in items:
        result.append({
            COL_NAME_TERM: term.term,
            COL_NAME_TRANSLATION: term.translation,
            COL_NAME_LANGUAGE: term.language,
            COL_NAME_CATEGORY: term.category,
            COL_NAME_COMMENT: term.comment,
            'score_status': score.status,
            'score_date': score.date,
            'score_urgency': score.urgency
        })
    return result

def get_vocab_data() -> VocabularyDatabase:
    """Get vocabulary database from session (assumes it's already loaded)"""
    if 'vocab_data' not in session:
        # This shouldn't happen if login/reload work correctly
        raise RuntimeError("Vocabulary data not loaded. Please log in again.")
    return session['vocab_data']

def fetch_and_store_vocab_data() -> int:
    """Fetch vocabulary data from Google Sheets and store in session"""
    print("Fetching vocabulary data from Google Sheets...")
    vocab_db = fetch_data(current_user())
    session['vocab_data'] = vocab_db
    print(f"Loaded {len(vocab_db.data)} vocabulary entries.")
    return len(vocab_db.data)

def is_authenticated() -> bool:
    """Check if user is authenticated for a configured learner"""
    # A session without a (still) configured learner has nowhere to read from
    # or write to, so it counts as logged out rather than falling back to anyone.
    return session.get('authenticated', False) and session.get('user') in USERS

def current_user() -> str:
    """Name of the learner whose sheet this session works on (guarded by @require_auth)"""
    return session['user']

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Shared by every learner's manifest; the sizes match the files in static/.
_MANIFEST_ICONS = [
    {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
    {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
]

@app.route('/manifest.webmanifest')
def manifest():
    """Web app manifest, tailored to one learner when ?user=<Name> asks for it.

    Chrome on Android takes the URL of a home-screen shortcut from start_url,
    not from the page the shortcut was added on, so a bookmarked
    /login?user=<Name> would lose its query and fall back to the first learner.
    A manifest per learner gives every child their own shortcut and name.
    """
    user = request.args.get('user')
    if user not in USERS:
        user = None
    start_url = url_for('login', user=user)
    body = {
        "id": start_url,  # distinct id and start_url: one home-screen icon per learner
        "name": f"WortSpaß – {user}" if user else "WortSpaß",
        "short_name": user or "WortSpaß",
        "description": "Latein- und Englisch-Vokabeln üben",
        "start_url": start_url,
        "scope": "/",
        "display": "browser",
        "background_color": "#007bff",
        "theme_color": "#007bff",
        "icons": _MANIFEST_ICONS,
    }
    # json.dumps escapes the umlauts, so the bytes are plain ASCII whatever the
    # charset a client assumes for application/manifest+json.
    return app.response_class(json.dumps(body), mimetype='application/manifest+json')

@app.route('/login', methods=['GET', 'POST'])
def login():
    users = list(USERS)
    if request.method == 'POST':
        user = request.form.get('user')
        if user not in USERS:
            return render_template('login.html', users=users, selected_user=users[0],
                                 error='Unknown user. Please try again.', delay=0)

        # Check if this is a guest login
        if 'guest_login' in request.form:
            session['authenticated'] = True
            session['guest_mode'] = True
            session['user'] = user
            session['failed_attempts'] = 0
            return redirect(url_for('loading_data', source='guest'))

        # Regular password login
        password = request.form.get('password')
        failed_attempts = session.get('failed_attempts', 0)
        last_attempt_time = session.get('last_attempt_time', 0)

        # Implement delay for failed attempts
        current_time = time.time()
        if failed_attempts > 0 and current_time - last_attempt_time < failed_attempts * 2:
            remaining_delay = int(failed_attempts * 2 - (current_time - last_attempt_time))
            return render_template('login.html', users=users, selected_user=user,
                                 error=f'Too many failed attempts. Please wait {remaining_delay} seconds.',
                                 delay=remaining_delay)

        expected_password = LOGIN_PASSWORDS[user]
        if expected_password and password == expected_password:
            session['authenticated'] = True
            session['guest_mode'] = False
            session['user'] = user
            session['failed_attempts'] = 0
            # Redirect to loading page to fetch vocabulary data
            return redirect(url_for('loading_data', source='login'))
        else:
            session['failed_attempts'] = failed_attempts + 1
            session['last_attempt_time'] = current_time
            return render_template('login.html', users=users, selected_user=user,
                                 error='Incorrect password. Please try again.',
                                 delay=0)

    # /login?user=<Name> preselects a learner so the page can be bookmarked per child.
    # Only an explicitly requested, known name reaches the manifest link, so that a
    # plain visit to /login does not offer a home-screen shortcut for users[0].
    requested_user = request.args.get('user')
    requested_user = requested_user if requested_user in USERS else None
    selected_user = requested_user or users[0]
    return render_template('login.html', users=users, selected_user=selected_user,
                           manifest_user=requested_user, error=None, delay=0)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@require_auth
def index():
    languages = ['Latein', 'Englisch']
    guest_mode = session.get('guest_mode', False)
    return render_template('index.html', languages=languages, guest_mode=guest_mode, user=current_user())

@app.route('/get_categories')
@require_auth
def get_categories():
    language = request.args.get('language')
    if language:
        vocab_db = get_vocab_data()  # Now returns VocabularyDatabase
        items = vocab_db.get_by_language(language)
        seen = set()
        categories = []
        for term, score in items:  # Now returns tuples (VocabularyTerm, VocabularyScore)
            cat = term.category
            if cat and cat not in seen:
                categories.append(cat)
                seen.add(cat)
        categories.reverse()
    else:
        categories = []
    return jsonify(categories=categories)

@app.route('/get_lesson_stats')
@require_auth
def get_lesson_stats():
    """Get detailed lesson statistics for the table view"""
    language = request.args.get('language')
    if not language:
        return jsonify(lessons=[])
    
    vocab_db = get_vocab_data()
    items = vocab_db.get_by_language(language)
    guest_mode = session.get('guest_mode', False)
    
    # Group by category and calculate statistics
    lesson_stats = {}
    for term, score in items:
        category = term.category
        if not category:
            continue
            
        if category not in lesson_stats:
            lesson_stats[category] = {
                'title': category,
                'count': 0,
                'best_status': LevelSystem.LEVELS[0].name,  # First level (lowest)
                'worst_status': LevelSystem.LEVELS[-1].name,  # Last level (highest)
                'min_urgency_days': 999999,
                'statuses': []
            }
        if (category == 'Wohnen im alten Rom'):
            lesson_stats[category]['count'] += 0
        
        lesson_stats[category]['count'] += 1
        lesson_stats[category]['statuses'].append(score.status)
        
        # Track best status (highest level)
        current_best_index = LevelSystem.LEVEL_INDEX.get(lesson_stats[category]['best_status'], 0)
        current_score_index = LevelSystem.LEVEL_INDEX.get(score.status, 0)
        if current_score_index > current_best_index:
            lesson_stats[category]['best_status'] = score.status
            
        # Track worst status (lowest level)
        current_worst_index = LevelSystem.LEVEL_INDEX.get(lesson_stats[category]['worst_status'], 0)
        if current_score_index < current_worst_index:
            lesson_stats[category]['worst_status'] = score.status
            
        # Calculate minimum urgency (most urgent = lowest days)
        # Only skip Red-1 and NOT_EXPIRED_LOW_URGENCY cases
        if not guest_mode and score.urgency:
            urgency_days = score.urgency.days_until_expiry
            # Skip special urgency cases (Red-1 and not-ready items)
            if (score.urgency != RED_1_LOW_URGENCY and 
                score.urgency != NOT_EXPIRED_LOW_URGENCY and
                urgency_days < lesson_stats[category]['min_urgency_days']):
                lesson_stats[category]['min_urgency_days'] = urgency_days
    
    # Convert to list with index
    lessons = []
    for i, (category, stats) in enumerate(lesson_stats.items(), 1):
        urgency_days = stats['min_urgency_days'] if stats['min_urgency_days'] != 999999 else None
        lessons.append({
            'index': i,
            'category': category,
            'title': stats['title'],
            'count': stats['count'],
            'best_status': stats['best_status'],
            'worst_status': stats['worst_status'],
            'urgency_days': urgency_days if not guest_mode else None
        })
    
    return jsonify(lessons=lessons)

@app.route('/reload_data', methods=['POST'])
@require_auth
def reload_data():
    # Preserve authentication and failed attempts data
    authenticated = session.get('authenticated', False)
    guest_mode = session.get('guest_mode', False)
    user = current_user()
    failed_attempts = session.get('failed_attempts', 0)
    last_attempt_time = session.get('last_attempt_time', 0)

    session.clear()

    session['authenticated'] = authenticated
    session['guest_mode'] = guest_mode
    session['user'] = user
    session['failed_attempts'] = failed_attempts
    session['last_attempt_time'] = last_attempt_time
    
    # Force reload of vocabulary data
    if 'vocab_data' in session:
        del session['vocab_data']
    
    return redirect(url_for('loading_data', source='reload'))

@app.route('/loading_data')
@require_auth
def loading_data():
    """Show loading page while vocabulary data is being fetched"""
    source = request.args.get('source', 'login')  # 'login' or 'reload'
    return render_template('loading.html', source=source, user=current_user())

@app.route('/api/fetch_data', methods=['POST'])
@require_auth
def api_fetch_data():
    """API endpoint to fetch vocabulary data and return progress"""
    try:
        entry_count = fetch_and_store_vocab_data()
        return jsonify({
            'success': True, 
            'message': f'Successfully loaded {entry_count} vocabulary entries.',
            'entry_count': entry_count
        })
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error loading data: {str(e)}'
        }), 500

@app.route('/practice', methods=['POST'])
@require_auth
def practice():
    selected_language = request.form['language']
    selected_categories = request.form['categories']
    filtered_items = _practice_rows(get_vocab_data(), selected_language, selected_categories)
    filtered_data = _convert_vocab_tuples_to_dict(filtered_items)
    return _practice_on(filtered_data, selected_language, selected_categories, "Üben")

def _practice_rows(vocab_db: VocabularyDatabase, language: str, categories: str) -> List[Tuple[VocabularyTerm, VocabularyScore]]:
    """The rows of the practice page for a comma-separated category list, in page order.

    /test_selected receives row indices from that page, so both routes have
    to derive the list the same way.
    """
    rows = []
    for category in dict.fromkeys(categories.split(',')):
        rows.extend(vocab_db.get_by_category(language, category))
    return rows

@app.route('/review')
@require_auth
def review():
    """Show comprehensive review of all tested terms with sorting by result"""
    test_data = session.get('test_data', [])
    if not test_data:
        return redirect(url_for('index'))
    
    # Count results directly from test_data
    correct_count = sum(1 for term in test_data if term.get('test_result') == 'correct')
    wrong_count = sum(1 for term in test_data if term.get('test_result') == 'wrong')
    skipped_count = sum(1 for term in test_data if term.get('test_result') == 'skipped')
    guest_mode = session.get('guest_mode', False)
    
    # Categorize all test items
    wrong_items = []
    skipped_items = []
    correct_items = []
    
    for index, item in enumerate(test_data):
        # The checkbox of a row names the term by this index
        item = dict(item, test_index=index)
        if not guest_mode:
            # Show the level the term gets when this result is saved
            status, score_date = _projected_score(item)
            item.update(_add_status_info_to_data({'score_status': status, 'score_date': score_date}))
        
        result = item.get('test_result', 'skipped')
        if result == 'wrong':
            wrong_items.append(item)
        elif result == 'skipped':
            skipped_items.append(item)
        else:  # correct
            correct_items.append(item)
    
    # Sort items: wrong first, then skipped, then correct
    sorted_items = wrong_items + skipped_items + correct_items
    
    # Group by category for display
    grouped_data = {}
    for item in sorted_items:
        category = item.get(COL_NAME_CATEGORY, 'Unknown')
        if category not in grouped_data:
            grouped_data[category] = []
        grouped_data[category].append(item)
    
    # Get language for header
    language = test_data[0].get(COL_NAME_LANGUAGE, 'Unknown') if test_data else 'Unknown'
    
    return render_template(
        'review.html',
        vocab_data=grouped_data,
        header="Test Review",
        language=language,
        col_name_term=COL_NAME_TERM,
        col_name_comment=COL_NAME_COMMENT,  # Always show comment column
        col_name_translation=COL_NAME_TRANSLATION,
        correct_count=correct_count,
        wrong_count=wrong_count,
        skipped_count=skipped_count,
        total_count=len(test_data),
        guest_mode=guest_mode
    )

def _add_status_info_to_data(current_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate status info and add it to current_data dictionary.
    Adds 'current_status', 'days_until_retest', and 'days_until_expire' keys.
    """
    from datetime import date
    
    status = current_data.get('score_status', 'Red-1')
    last_date = current_data.get('score_date')
    
    # Calculate days until retest and expiry
    days_until_retest = None
    days_until_expire = None
    
    if last_date and status != 'Red-1':
        level = LevelSystem.get_level(status)
        test_date = date.fromisoformat(last_date)
        days_since_test = (date.today() - test_date).days
        
        # Days until eligible for retest (min_days - days_since_test)
        days_until_retest = max(0, level.min_days - days_since_test)
        
        # Days until expiry (max_days - days_since_test + 1)
        if level.max_days is not None:
            days_until_expire = max(0, level.max_days - days_since_test + 1)
        else:
            days_until_expire = None  # Never expires (only Red-1)
    elif status == 'Red-1':
        days_until_retest = 0  # Always ready for retest
        days_until_expire = None  # Red-1 doesn't expire further
    
    # Add calculated values to the data dictionary
    current_data['current_status'] = status
    current_data['days_until_retest'] = days_until_retest
    current_data['days_until_expire'] = days_until_expire
    return current_data

def _projected_score(item: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Level and date the term gets when its test result is saved; unchanged for a skipped term.

    A round records answers as facts and the level transition happens only
    here, once, against the level the term had when the test started. A term
    answered wrong and then right in a retest is therefore graded on its final
    result instead of being demoted and re-promoted (which, with Red-1 having
    min_days=0, gave every term a free Red-2).
    """
    status = item.get('score_status', 'Red-1')
    score_date = item.get('score_date')
    result = item.get('test_result')
    if result not in ANSWERED_RESULTS or item.get('saved'):
        return status, score_date
    return LevelSystem.process_answer(status, result == 'correct', score_date)

def _get_language_labels(language: str, show_term: bool) -> Dict[str, Any]:
    """
    Utility function to determine labels for term, translation, and language based on the given language
    and whether the term or translation is currently being shown.

    :param language: The language of the current data.
    :param show_term: Boolean indicating whether the term is being shown (True) or the translation (False).
    :return: A dictionary with the following keys: label_language, label_translation, label_term.
    """
    if language == 'Latein':
        label_language = 'Latein'
        label_translation = 'Deutsch' if show_term else 'Latein'
        label_term = 'Latein' if show_term else 'Deutsch'
    elif language == 'Englisch':
        label_language = 'Englisch'
        label_translation = 'Deutsch' if show_term else 'Englisch'
        label_term = 'Englisch' if show_term else 'Deutsch'
    else:
        # Add more logic here for other languages, if necessary
        label_language = language
        label_translation = 'Translation'
        label_term = 'Term'

    return {
        'label_language': label_language,
        'label_translation': label_translation,
        'label_term': label_term
    }
    
def _practice_on(filtered_data, selected_language, selected_categories, header, is_error_review=False):
    guest_mode = session.get('guest_mode', False)
    
    # Add status information to each item (but skip in guest mode)
    if not guest_mode:
        for item in filtered_data:
            item.update(_add_status_info_to_data(item))
    
    # create a transformation filter_data_grouped so that we can group the data by category
    filtered_data_grouped = {}
    # remove all keys in the item set whose name does not start with 'Unnamed'
    filtered_data_grouped = {item[COL_NAME_CATEGORY]: [] for item in filtered_data}
    for item in filtered_data:
        filtered_data_grouped[item[COL_NAME_CATEGORY]].append(item)
        
    # this is what filtered_data_grouped looks like:
    # {'Latein: Das Kapitol': [
    #      {'Fremdsprache': 'ascendere', 'Zusatz': 'ascendō;ascendī', 'Deutsch': 'besteigen, hinaufsteigen', 'Kategorie': 'Latein: Das Kapitol', 'Sprache': 'Latein'},
    #      {'Fremdsprache': 'templum', 'Zusatz': 'templī n.', 'Deutsch': 'der Tempel', 'Kategorie': 'Latein: Das Kapitol', 'Sprache': 'Latein'}
    #  ],
    #  'Latein: Salve': [
    #      {'Fremdsprache': 'Salvē', 'Zusatz': '', 'Deutsch': 'Sei gegrüßt', 'Kategorie': 'Latein: Salve', 'Sprache': 'Latein'}
    #  ]}
    
    return render_template(
        'practice.html',
        vocab_data=filtered_data_grouped,
        header=header,
        language=selected_language,
        categories=selected_categories,
        col_name_term=COL_NAME_TERM,
        col_name_comment=COL_NAME_COMMENT,  # Always show comment column
        col_name_translation=COL_NAME_TRANSLATION,
        is_error_review=is_error_review,
        guest_mode=guest_mode
    )

def random_order(length: int) -> List[int]:
    return random.sample(range(length), length)

# What the browser sends for an answer, and the test_result it stands for
ANSWER_RESULTS = {'Richtig': 'correct', 'Falsch': 'wrong'}
ANSWERED_RESULTS = frozenset(ANSWER_RESULTS.values())

def _begin_round(test_data: List[Dict[str, Any]], order: List[int]) -> None:
    """Store a round: the terms and the order in which /test hands them to the browser."""
    session['test_data'] = test_data
    session['order'] = order
    # Positions in a /finish_test submission only mean something against the
    # order they were generated for, so the browser has to send this id back.
    session['round_id'] = secrets.token_hex(8)

def _end_round() -> None:
    """A round is in progress exactly while 'order' is non-empty."""
    session['order'] = []
    session.pop('round_id', None)

def _new_test_data(items: List[Tuple[VocabularyTerm, VocabularyScore]]) -> List[Dict[str, Any]]:
    test_data = _convert_vocab_tuples_to_dict(items)
    for term in test_data:
        term['test_result'] = 'skipped'
    return test_data


@app.route('/test_selected', methods=['POST'])
@require_auth
def test_selected():
    """Start a test with the rows ticked on the practice page, given as indices into that page"""
    selected = request.form.get('selected-items', '')
    if not selected:
        return redirect(url_for('index'))
    rows = _practice_rows(get_vocab_data(), request.form.get('language', ''), request.form.get('categories', ''))
    try:
        indices = sorted({int(index) for index in selected.split(',')})
    except ValueError:
        abort(400)
    if any(not 0 <= index < len(rows) for index in indices):
        abort(400)

    test_data = _new_test_data([rows[index] for index in indices])
    _begin_round(test_data, random_order(len(test_data)))
    return redirect(url_for('test'))

@app.route('/start_test', methods=['POST'])
@require_auth
def start_test():
    selected_language = request.form['language']
    selected_categories = [category for category in request.form['categories'].split(',')]
    vocab_db = get_vocab_data()
    guest_mode = session.get('guest_mode', False)
    
    testable_items = []
    for category in selected_categories:
        category_items = vocab_db.get_testable_terms(language=selected_language, category=category, guest_mode=guest_mode)
        testable_items.extend(category_items)
    
    if not testable_items:
        # No terms available for testing - redirect back with message
        # TODO: Add flash message support for user feedback
        return redirect(url_for('index'))
    
    test_data = _new_test_data(testable_items)
    _begin_round(test_data, random_order(len(test_data)))
    return redirect(url_for('test'))

@app.route('/test_errors', methods=['POST'])
@require_auth
def test_errors():
    """Start another round over the terms of this test that are wrong or skipped, wrong first"""
    test_data = session.get('test_data', [])
    if not test_data:
        return redirect(url_for('index'))
    
    wrong_indices = [i for i, term in enumerate(test_data) if term.get('test_result') == 'wrong']
    skipped_indices = [i for i, term in enumerate(test_data) if term.get('test_result') == 'skipped']
    
    if not wrong_indices and not skipped_indices:
        return redirect(url_for('index'))
    
    random.shuffle(wrong_indices)
    random.shuffle(skipped_indices)
    _begin_round(test_data, wrong_indices + skipped_indices)
    return redirect(url_for('test'))

@app.route('/test')
@require_auth
def test():
    """Hand the whole round to the browser, which runs it and reports back to /finish_test"""
    test_data = session.get('test_data')
    if not test_data:
        return redirect(url_for('index'))
    order = session.get('order', [])
    round_id = session.get('round_id')
    if not order or not round_id:
        return redirect(url_for('review'))
    guest_mode = session.get('guest_mode', False)

    round_items = [test_data[index] for index in order]
    languages = {item[COL_NAME_LANGUAGE] for item in round_items}
    # The progress counters cover the whole test, so terms outside this
    # round (already correct in an earlier round) go in as a base count.
    in_round = set(order)
    outside = [item for index, item in enumerate(test_data) if index not in in_round]
    round_data = {
        'id': round_id,
        'items': [{
            'term': item[COL_NAME_TERM],
            'translation': item[COL_NAME_TRANSLATION],
            'comment': item.get(COL_NAME_COMMENT, ''),
            'language': item[COL_NAME_LANGUAGE],
            'result': item.get('test_result', 'skipped'),
        } for item in round_items],
        # [asked side is the term, asked side is the translation], per language
        'labels': {language: [_get_language_labels(language, True), _get_language_labels(language, False)]
                   for language in languages},
        'base': {
            'correct': sum(1 for item in outside if item.get('test_result') == 'correct'),
            'wrong': sum(1 for item in outside if item.get('test_result') == 'wrong'),
        },
    }
    # One rendered status line per position; the browser shows the current one
    status_items = [] if guest_mode else [
        _add_status_info_to_data({'score_status': item.get('score_status', 'Red-1'), 'score_date': item.get('score_date')})
        for item in round_items
    ]

    return render_template(
        'test.html',
        round_data=round_data,
        status_items=status_items,
        guest_mode=guest_mode
    )

@app.route('/finish_test', methods=['POST'])
@require_auth
def finish_test():
    """Record the round's answers: which positions were graded, and whether right or wrong.

    Level transitions are not applied here; see _projected_score.
    """
    test_data = session.get('test_data')
    if not test_data:
        return redirect(url_for('index'))
    order = session.get('order', [])
    if not order or request.form.get('round_id') != session.get('round_id'):
        # No round in progress, or a stale tab reporting on an earlier round
        return redirect(url_for('test'))

    try:
        answers = json.loads(request.form.get('answers', '[]'))
        graded = [(int(answer['position']), ANSWER_RESULTS[answer['answer']]) for answer in answers]
    except (ValueError, TypeError, KeyError):
        abort(400)
    if any(not 0 <= position < len(order) for position, _ in graded):
        abort(400)

    for position, result in graded:
        item = test_data[order[position]]
        # Saving settles a term: the sheet already records how it went, so the
        # next answer is judged on its own again.
        settled = item.pop('saved', None)
        # Until then a wrong answer stands for the rest of the test. Getting the
        # term right on a retest a minute later says nothing about whether it
        # will still be there next week.
        if settled or item.get('test_result') != 'wrong':
            item['test_result'] = result
    session.modified = True
    _end_round()
    return redirect(url_for('review'))

@app.route('/write_scores', methods=['POST'])
@require_auth
def write_scores():
    """Write vocabulary scores to Google Sheets"""
    guest_mode = session.get('guest_mode', False)
    
    # Redirect guest users away from score writing
    if guest_mode:
        return redirect(url_for('index'))
    
    # Check if this is a save action (from review page)
    action = request.form.get('action')
    if action != 'save':
        return redirect(url_for('index'))
    
    test_data = session.get('test_data', [])
    if not test_data:
        return redirect(url_for('index'))

    # The review page names the selected rows by their index into test_data;
    # no selection means every answered term (backward compatibility).
    try:
        selected = sorted({int(index) for index in request.form.getlist('selected-items')})
    except ValueError:
        abort(400)
    if any(not 0 <= index < len(test_data) for index in selected):
        abort(400)
    if not selected:
        selected = range(len(test_data))
    answered_items = [test_data[index] for index in selected
                      if test_data[index].get('test_result') in ANSWERED_RESULTS and not test_data[index].get('saved')]
    if not answered_items:
        return redirect(url_for('index'))

    # The level transition happens here, once per term (see _projected_score)
    saved_by_language: Dict[str, List[Tuple[Dict[str, Any], str, Optional[str]]]] = {}
    for item in answered_items:
        status, score_date = _projected_score(item)
        saved_by_language.setdefault(item.get(COL_NAME_LANGUAGE, 'Englisch'), []).append((item, status, score_date))

    vocab_db = session.get('vocab_data')
    try:
        for language, saved in saved_by_language.items():
            write_scores_to_sheet([dict(item, score_status=status, score_date=score_date) for item, status, score_date in saved],
                                  language, current_user())
            # What the sheet now says becomes the session's truth as well, so
            # another round or save in this session starts from it.
            for item, status, score_date in saved:
                item['score_status'] = status
                item['score_date'] = score_date
                item['saved'] = True
                if vocab_db is not None:
                    vocab_db.update_score(_vocab_term_of(item), status, score_date)
    except Exception as e:
        # Handle errors gracefully - could add flash message here
        print(f"Error writing scores: {e}")
    session.modified = True
    return redirect(url_for('index'))

def _vocab_term_of(item: Dict[str, Any]) -> VocabularyTerm:
    """The database key of a test_data entry; all five fields take part in the hash."""
    return VocabularyTerm(
        term=item.get(COL_NAME_TERM),
        translation=item.get(COL_NAME_TRANSLATION),
        language=item.get(COL_NAME_LANGUAGE),
        category=item.get(COL_NAME_CATEGORY),
        comment=item.get(COL_NAME_COMMENT, '')
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
