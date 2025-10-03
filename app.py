from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import pandas as pd
import random
import json
import os
from datetime import timedelta
from typing import List, Dict, Any, Tuple
from google_sheet_io import fetch_data, write_scores_to_sheet, COL_NAME_TERM, COL_NAME_COMMENT, COL_NAME_TRANSLATION, COL_NAME_CATEGORY, COL_NAME_LANGUAGE, VocabularyDatabase, VocabularyTerm, VocabularyScore
from level import LevelSystem
from flask import Flask
from flask_session import Session
import time

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_FILE_THRESHOLD'] = 250
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=10)
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
Session(app)

# Password protection
LOGIN_PASSWORD = os.environ.get('LOGIN_PASSWORD', 'password')

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
    vocab_db = fetch_data()  # This now returns VocabularyDatabase
    session['vocab_data'] = vocab_db
    print(f"Loaded {len(vocab_db.data)} vocabulary entries.")
    return len(vocab_db.data)

def is_authenticated() -> bool:
    """Check if user is authenticated"""
    return session.get('authenticated', False)

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        failed_attempts = session.get('failed_attempts', 0)
        last_attempt_time = session.get('last_attempt_time', 0)
        
        # Implement delay for failed attempts
        current_time = time.time()
        if failed_attempts > 0 and current_time - last_attempt_time < failed_attempts * 2:
            remaining_delay = int(failed_attempts * 2 - (current_time - last_attempt_time))
            return render_template('login.html', 
                                 error=f'Too many failed attempts. Please wait {remaining_delay} seconds.',
                                 delay=remaining_delay)
        
        if password == LOGIN_PASSWORD:
            session['authenticated'] = True
            session['failed_attempts'] = 0
            # Redirect to loading page to fetch vocabulary data
            return redirect(url_for('loading_data', source='login'))
        else:
            session['failed_attempts'] = failed_attempts + 1
            session['last_attempt_time'] = current_time
            return render_template('login.html', 
                                 error='Incorrect password. Please try again.',
                                 delay=0)
    
    return render_template('login.html', error=None, delay=0)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@require_auth
def index():
    languages = ['Latein', 'Englisch']
    return render_template('index.html', languages=languages)

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

@app.route('/reload_data', methods=['POST'])
@require_auth
def reload_data():
    # Preserve authentication and failed attempts data
    authenticated = session.get('authenticated', False)
    failed_attempts = session.get('failed_attempts', 0)
    last_attempt_time = session.get('last_attempt_time', 0)
    
    session.clear()
    
    session['authenticated'] = authenticated
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
    return render_template('loading.html', source=source)

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
    selected_categories = [category for category in request.form['categories'].split(',')]

    vocab_db = get_vocab_data()  # Now returns VocabularyDatabase
    
    # Get filtered data using the new database methods
    filtered_items = []
    for category in selected_categories:
        category_items = vocab_db.get_by_category(selected_language, category)
        filtered_items.extend(category_items)
    
    # Convert to dict format for backward compatibility
    filtered_data = _convert_vocab_tuples_to_dict(filtered_items)
    
    # Remove 'Unnamed' keys (though this shouldn't be needed with the new structure)
    filtered_data = [{key: value for key, value in item.items() if not key.startswith('Unnamed')} for item in filtered_data] 

    return _practice_on(filtered_data, selected_language, "Üben")

@app.route('/review_failures')
@require_auth
def review_failures():
    return _practice_on(session['list_of_wrong_answers'], session['test_data'][0][COL_NAME_LANGUAGE], "Fehler wiederholen", is_error_review=True)

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

def _get_language_labels(language: str, show_term: bool) -> Dict[str, Any]:
    """
    Utility function to determine labels for term, translation, and language based on the given language
    and whether the term or translation is currently being shown.

    :param language: The language of the current data.
    :param show_term: Boolean indicating whether the term is being shown (True) or the translation (False).
    :return: A dictionary with the following keys: label_language, label_translation, label_term, and show_comment.
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

    show_comment = language != 'Englisch'  # Only show comments for non-English languages

    return {
        'label_language': label_language,
        'label_translation': label_translation,
        'label_term': label_term,
        'show_comment': show_comment
    }
    
def _practice_on(filtered_data, selected_language, header, is_error_review=False):
    # Add status information to each item
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
        col_name_term=COL_NAME_TERM,
        col_name_comment=COL_NAME_COMMENT if selected_language != 'Englisch' else None,
        col_name_translation=COL_NAME_TRANSLATION,
        is_error_review=is_error_review
    )

def random_order(length: int) -> List[int]:
    return random.sample(range(length), length)


@app.route('/start_test', methods=['POST'])
@require_auth
def start_test():
    selected_language = request.form['language']
    selected_categories = [category for category in request.form['categories'].split(',')]
    vocab_db = get_vocab_data()  # Now returns VocabularyDatabase
    
    # Use the new database method to get filtered and testable terms
    testable_items = []
    for category in selected_categories:
        category_items = vocab_db.get_testable_terms(language=selected_language, category=category)
        testable_items.extend(category_items)
    
    # Convert to dict format for backward compatibility with existing session logic
    testable_terms = _convert_vocab_tuples_to_dict(testable_items)
    
    if not testable_terms:
        # No terms available for testing - redirect back with message
        # TODO: Add flash message support for user feedback
        return redirect(url_for('index'))
    
    session['test_data'] = testable_terms
    session['correct_answers'] = 0
    session['wrong_answers'] = 0
    session['skipped_answers'] = 0
    session['show_term'] = True
    session['list_of_wrong_answers'] = []
    session['all_tested_items'] = []

    return redirect(url_for('test'))

@app.route('/test_errors', methods=['POST'])
@require_auth
def test_errors():
    if not session.get('list_of_wrong_answers'):
        return redirect(url_for('index'))
    
    session['test_data'] = session['list_of_wrong_answers']
    session['correct_answers'] = 0
    session['wrong_answers'] = 0
    session['skipped_answers'] = 0
    session['show_term'] = True
    session['list_of_wrong_answers'] = []
    session['all_tested_items'] = []

    return redirect(url_for('test'))

def _get_position_in_test() -> int:
    skipped = session.get('skipped_answers', 0)
    correct = session.get('correct_answers', 0)
    wrong = session.get('wrong_answers', 0)
    total_answered = correct + wrong + skipped
    return total_answered % len(session['test_data'])

def _get_data_at_position(position: int) -> Dict[str, Any]:
    return session['test_data'][session['order'][position]]


@app.route('/test')
@require_auth
def test():
    if not session.get('test_data'):
        return redirect(url_for('index'))

    position = _get_position_in_test()
    if position == 0:
        session['order'] = random_order(len(session['test_data']))
    
    current_data = _get_data_at_position(position)
    language = current_data[COL_NAME_LANGUAGE]
    show_term = session.get('show_term', True)

    # Create minimal copy with only required fields for template
    minimal_current_data = {
        COL_NAME_TERM: current_data[COL_NAME_TERM],
        COL_NAME_TRANSLATION: current_data[COL_NAME_TRANSLATION], 
        COL_NAME_COMMENT: current_data.get(COL_NAME_COMMENT, ''),
        COL_NAME_LANGUAGE: current_data[COL_NAME_LANGUAGE],
        'score_status': current_data.get('score_status', 'Red-1'),
        'score_date': current_data.get('score_date')
    }

    # Use the utility function to get the labels and comment visibility
    labels = _get_language_labels(language, show_term)

    # Add status info to minimal_current_data
    minimal_current_data = _add_status_info_to_data(minimal_current_data)

    return render_template(
        'test.html',
        current_data=minimal_current_data,
        term_key=COL_NAME_TERM,
        language_key=COL_NAME_LANGUAGE,
        comment_key=COL_NAME_COMMENT if labels['show_comment'] else None,
        translation_key=COL_NAME_TRANSLATION,
        correct_count=session['correct_answers'],
        wrong_count=session['wrong_answers'],
        show_translation=False,
        show_term=show_term,
        label_language=labels['label_language'],
        label_translation=labels['label_translation'],
        label_term=labels['label_term']
    )

@app.route('/show_translation', methods=['POST'])
@require_auth
def show_translation():
    current_data_str = request.form['current_data']
    current_data = json.loads(current_data_str)

    language = current_data[COL_NAME_LANGUAGE]
    show_term = session.get('show_term', True)

    # Use the utility function to get the labels and comment visibility
    labels = _get_language_labels(language, show_term)

    return render_template(
        'test.html',
        current_data=current_data,
        term_key=COL_NAME_TERM,
        language_key=COL_NAME_LANGUAGE,
        comment_key=COL_NAME_COMMENT if labels['show_comment'] else None,
        translation_key=COL_NAME_TRANSLATION,
        correct_count=session['correct_answers'],
        wrong_count=session['wrong_answers'],
        show_translation=True,
        show_term=show_term,
        label_language=labels['label_language'],
        label_translation=labels['label_translation'],
        label_term=labels['label_term']
    )

@app.route('/check_answer', methods=['POST'])
@require_auth
def check_answer():
    """Handle the user's response during testing with level system progression."""
    # Capture the current test position before counters are modified
    position = _get_position_in_test()
    current_data = _get_data_at_position(position)

    answer_correct = request.form['answer_correct'] == 'Richtig'
    
    # Get current level information
    current_level = current_data.get('score_status', 'Red-1')
    last_test_date = current_data.get('score_date')
    
    # Process the answer through the level system
    new_level, new_date = LevelSystem.process_answer(current_level, answer_correct, last_test_date)
    
    # Update the item in session data using direct position access instead of search
    if 'test_data' in session and 'order' in session:
        # Get the actual index in the test_data array using the current position
        actual_index = session['order'][position]
        session['test_data'][actual_index]['score_status'] = new_level
        session['test_data'][actual_index]['score_date'] = new_date
        
        # Also update in vocab_data if it exists in session
        vocab_db = session.get('vocab_data')
        if vocab_db:
            # Create temporary VocabularyTerm for direct lookup instead of sequential search
            temp_vocab_term = VocabularyTerm(
                term=current_data.get(COL_NAME_TERM),
                translation=current_data.get(COL_NAME_TRANSLATION),
                language=current_data.get(COL_NAME_LANGUAGE),
                category=current_data.get(COL_NAME_CATEGORY),
                comment=current_data.get(COL_NAME_COMMENT, '')
            )
            
            # Direct lookup using the VocabularyTerm as key
            vocab_score = vocab_db.get_score(temp_vocab_term)
            if vocab_score:
                vocab_db.update_score(temp_vocab_term, new_level, new_date)

    # Update counters and track all tested items for writing back to sheets
    if 'all_tested_items' not in session:
        session['all_tested_items'] = []
    
    # Add current item with updated level/date to tested items
    tested_item = current_data.copy()
    tested_item['score_status'] = new_level
    tested_item['score_date'] = new_date
    session['all_tested_items'].append(tested_item)
    
    if answer_correct:
        session['correct_answers'] += 1
    else:
        # Add to wrong answers for review (still needed for review functionality)
        session['list_of_wrong_answers'].append(tested_item)
        session['wrong_answers'] += 1

    return redirect(url_for('test'))

@app.route('/switch_direction', methods=['POST'])
@require_auth
def switch_direction():
    current_data_str = request.form['current_data']
    current_data = json.loads(current_data_str)

    # Toggle the direction (show term or show translation)
    session['show_term'] = not session.get('show_term', True)
    show_term = session['show_term']

    language = current_data[COL_NAME_LANGUAGE]

    # Use the utility function to get the labels and comment visibility
    labels = _get_language_labels(language, show_term)

    # Add status info to current_data
    current_data = _add_status_info_to_data(current_data)

    return render_template(
        'test.html',
        current_data=current_data,
        term_key=COL_NAME_TERM,
        language_key=COL_NAME_LANGUAGE,
        comment_key=COL_NAME_COMMENT if labels['show_comment'] else None,
        translation_key=COL_NAME_TRANSLATION,
        correct_count=session['correct_answers'],
        wrong_count=session['wrong_answers'],
        show_translation=False,
        show_term=show_term,
        label_language=labels['label_language'],
        label_translation=labels['label_translation'],
        label_term=labels['label_term']
    )

@app.route('/skip_question', methods=['POST'])
@require_auth
def skip_question():
    """Skip current question and advance to next without changing score"""
    # Increment skip counter to advance position
    session['skipped_answers'] = session.get('skipped_answers', 0) + 1
    return redirect(url_for('test'))

@app.route('/write_scores', methods=['POST'])
@require_auth
def write_scores():
    """Write vocabulary scores to Google Sheets"""
    all_tested_items = session.get('all_tested_items', [])
    if not all_tested_items:
        return redirect(url_for('index'))
    
    try:
        # Group items by language
        items_by_language = {}
        for item in all_tested_items:
            language = item.get(COL_NAME_LANGUAGE, 'Englisch')
            if language not in items_by_language:
                items_by_language[language] = []
            items_by_language[language].append(item)
        
        # Write scores for each language in a single batch
        total_rows_written = 0
        for language, items in items_by_language.items():
            rows_written = write_scores_to_sheet(items, language)
            total_rows_written += rows_written
        
        # Clear tested items after successful write
        session['all_tested_items'] = []
        
        # Redirect back to the error review if there were wrong answers, otherwise to index
        if session.get('list_of_wrong_answers'):
            return redirect(url_for('review_failures'))
        else:
            return redirect(url_for('index'))
        
    except Exception as e:
        # Handle errors gracefully - could add flash message here
        print(f"Error writing scores: {e}")
        if session.get('list_of_wrong_answers'):
            return redirect(url_for('review_failures'))
        else:
            return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
