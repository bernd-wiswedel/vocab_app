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
    
    # Categorize all test items
    wrong_items = []
    skipped_items = []
    correct_items = []
    
    for item in test_data:
        # Add status information to each item
        item.update(_add_status_info_to_data(item))
        
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
        total_count=len(test_data)
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
        col_name_comment=COL_NAME_COMMENT,  # Always show comment column
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
    
    # Convert to dict format and add test_result field to each term
    testable_terms = _convert_vocab_tuples_to_dict(testable_items)
    
    # Initialize all terms as "skipped" (default state)
    for term in testable_terms:
        term['test_result'] = 'skipped'
    
    if not testable_terms:
        # No terms available for testing - redirect back with message
        # TODO: Add flash message support for user feedback
        return redirect(url_for('index'))
    
    session['test_data'] = testable_terms
    session['order'] = random_order(len(testable_terms))
    session['current_position'] = 0  # Track position in order array
    session['show_term'] = True

    return redirect(url_for('test'))

@app.route('/test_errors', methods=['POST'])
@require_auth
def test_errors():
    test_data = session.get('test_data', [])
    if not test_data:
        return redirect(url_for('index'))
    
    # Find indices of wrong and skipped terms in the original test_data
    wrong_indices = [i for i, term in enumerate(test_data) if term.get('test_result') == 'wrong']
    skipped_indices = [i for i, term in enumerate(test_data) if term.get('test_result') == 'skipped']
    
    if not wrong_indices and not skipped_indices:
        return redirect(url_for('index'))
    
    # Shuffle each group before merging (wrong first, then skipped)
    random.shuffle(wrong_indices)
    random.shuffle(skipped_indices)
    
    # Create new order with just the incomplete term indices (wrong first, then skipped)
    session['order'] = wrong_indices + skipped_indices
    session['current_position'] = 0
    session['show_term'] = True
    # Keep the same test_data - no replacement needed!

    return redirect(url_for('test'))

def _get_position_in_test() -> int:
    """Get the index in test_data of the next term to show, or -1 if no more terms"""
    test_data = session.get('test_data', [])
    order = session.get('order', [])
    current_position = session.get('current_position', 0)
    
    # Find next term that hasn't been answered correctly
    while current_position < len(order):
        index = order[current_position]
        term = test_data[index]
        
        # If term is not correct, we should show it
        if term.get('test_result') != 'correct':
            return index
            
        current_position += 1
    
    return -1  # No more terms to show

@app.route('/test')
@require_auth
def test():
    if not session.get('test_data'):
        return redirect(url_for('index'))

    position = _get_position_in_test()
    
    # If no more terms to show, redirect to review
    if position == -1:
        return redirect(url_for('review'))
    
    current_data = session['test_data'][position]
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

    # Calculate progress information based on current position in order
    order = session.get('order', [])
    current_position = session.get('current_position', 0)
    total_terms = len(order)
    completed_terms = current_position
    progress_percentage = int((completed_terms / total_terms) * 100) if total_terms > 0 else 0
    
    # Also calculate counts for display
    test_data = session['test_data']
    correct_count = sum(1 for term in test_data if term.get('test_result') == 'correct')
    wrong_count = sum(1 for term in test_data if term.get('test_result') == 'wrong')
    skipped_count = sum(1 for term in test_data if term.get('test_result') == 'skipped')

    return render_template(
        'test.html',
        current_data=minimal_current_data,
        term_key=COL_NAME_TERM,
        language_key=COL_NAME_LANGUAGE,
        comment_key=COL_NAME_COMMENT,
        translation_key=COL_NAME_TRANSLATION,
        correct_count=correct_count,
        wrong_count=wrong_count,
        skipped_count=skipped_count,
        total_terms=total_terms,
        completed_terms=completed_terms,
        progress_percentage=progress_percentage,
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

    # Calculate progress information based on current position in order
    order = session.get('order', [])
    current_position = session.get('current_position', 0)
    total_terms = len(order)
    completed_terms = current_position
    progress_percentage = int((completed_terms / total_terms) * 100) if total_terms > 0 else 0
    
    # Also calculate counts for display
    test_data = session.get('test_data', [])
    correct_count = sum(1 for term in test_data if term.get('test_result') == 'correct')
    wrong_count = sum(1 for term in test_data if term.get('test_result') == 'wrong')
    skipped_count = sum(1 for term in test_data if term.get('test_result') == 'skipped')

    return render_template(
        'test.html',
        current_data=current_data,
        term_key=COL_NAME_TERM,
        language_key=COL_NAME_LANGUAGE,
        comment_key=COL_NAME_COMMENT,
        translation_key=COL_NAME_TRANSLATION,
        correct_count=correct_count,
        wrong_count=wrong_count,
        skipped_count=skipped_count,
        total_terms=total_terms,
        completed_terms=completed_terms,
        progress_percentage=progress_percentage,
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
    # Get current position to identify the term being answered
    position = _get_position_in_test()
    if position == -1:
        # No more terms, redirect to review
        return redirect(url_for('review'))
    
    # Get the current term data directly by position
    current_data = session['test_data'][position]

    answer_correct = request.form['answer_correct'] == 'Richtig'
    
    # Get current level information
    current_level = current_data.get('score_status', 'Red-1')
    last_test_date = current_data.get('score_date')
    
    # Process the answer through the level system
    new_level, new_date = LevelSystem.process_answer(current_level, answer_correct, last_test_date)
    
    # Update the item in session data using direct position access
    session['test_data'][position]['score_status'] = new_level
    session['test_data'][position]['score_date'] = new_date
    
    # Update test result in the term
    if answer_correct:
        session['test_data'][position]['test_result'] = 'correct'
    else:
        session['test_data'][position]['test_result'] = 'wrong'
    
    # Update in vocab_data if it exists in session
    vocab_db = session.get('vocab_data')
    if vocab_db:
        # Create temporary VocabularyTerm for direct lookup
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

    # Advance position to next unanswered term
    session['current_position'] = session.get('current_position', 0) + 1

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

    # Calculate progress information (same as in test route)
    total_terms = len(session.get('test_data', []))
    completed_terms = session.get('correct_answers', 0) + session.get('wrong_answers', 0) + session.get('skipped_answers', 0)
    progress_percentage = int((completed_terms / total_terms) * 100) if total_terms > 0 else 0

    return render_template(
        'test.html',
        current_data=current_data,
        term_key=COL_NAME_TERM,
        language_key=COL_NAME_LANGUAGE,
        comment_key=COL_NAME_COMMENT,
        translation_key=COL_NAME_TRANSLATION,
        correct_count=session['correct_answers'],
        wrong_count=session['wrong_answers'],
        skipped_count=session.get('skipped_answers', 0),
        total_terms=total_terms,
        completed_terms=completed_terms,
        progress_percentage=progress_percentage,
        show_translation=False,
        show_term=show_term,
        label_language=labels['label_language'],
        label_translation=labels['label_translation'],
        label_term=labels['label_term']
    )

@app.route('/skip_question', methods=['POST'])
@require_auth
def skip_question():
    """Skip current question and mark it as skipped without changing score"""
    # Get current position to identify the term being skipped
    position = _get_position_in_test()
    if position == -1:
        # No more terms, redirect to review
        return redirect(url_for('review'))
    
    # The term retains its 'skipped' test_result (no change needed)
    # Just advance position to next unanswered term
    session['current_position'] = session.get('current_position', 0) + 1
    
    return redirect(url_for('test'))

@app.route('/write_scores', methods=['POST'])
@require_auth
def write_scores():
    """Write vocabulary scores to Google Sheets"""
    test_data = session.get('test_data', [])
    if not test_data:
        return redirect(url_for('index'))
    
    try:
        # Filter for items that were actually answered (not skipped)
        answered_items = [
            item for item in test_data 
            if item.get('test_result') in ['correct', 'wrong']
        ]
        
        if not answered_items:
            return redirect(url_for('index'))
        
        # Group items by language
        items_by_language = {}
        for item in answered_items:
            language = item.get(COL_NAME_LANGUAGE, 'Englisch')
            if language not in items_by_language:
                items_by_language[language] = []
            items_by_language[language].append(item)
        
        # Write scores for each language in a single batch
        total_rows_written = 0
        for language, items in items_by_language.items():
            rows_written = write_scores_to_sheet(items, language)
            total_rows_written += rows_written
        
        # Redirect back to index after successful write
        return redirect(url_for('index'))
        
    except Exception as e:
        # Handle errors gracefully - could add flash message here
        print(f"Error writing scores: {e}")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
