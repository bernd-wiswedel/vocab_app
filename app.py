from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import pandas as pd
import random
import json
import os
import hashlib
import base64
from datetime import timedelta
from google_sheet_io import fetch_data, write_scores_to_sheet, COL_NAME_TERM, COL_NAME_COMMENT, COL_NAME_TRANSLATION, COL_NAME_CATEGORY, COL_NAME_LANGUAGE
from flask import Flask
from flask_session import Session
from cryptography.fernet import Fernet
import time

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_FILE_THRESHOLD'] = 250
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=10)
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
Session(app)

# Load data from public Google Sheets
app.config['VOCAB_DATA'] = fetch_data()

# Password protection
LOGIN_PASSWORD = os.environ.get('LOGIN_PASSWORD', 'default_password')

def is_authenticated():
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
            return redirect(url_for('index'))
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
        vocab_data = app.config['VOCAB_DATA']
        categories_dict = {
            str(item[COL_NAME_CATEGORY]): None for item in reversed(vocab_data)
            if item[COL_NAME_LANGUAGE] == language and pd.notna(item[COL_NAME_CATEGORY])
        }
        categories = list(categories_dict.keys())
    else:
        categories = []
    return jsonify(categories=categories)

@app.route('/reload_data', methods=['POST'])
@require_auth
def reload_data():
    session.clear()
    app.config['VOCAB_DATA'] = fetch_data()
    return redirect(url_for('index'))

@app.route('/practice', methods=['POST'])
@require_auth
def practice():
    selected_language = request.form['language']
    selected_categories = [category for category in request.form['categories'].split(',')]

    filtered_data = [item for item in app.config['VOCAB_DATA'] if item[COL_NAME_CATEGORY] in selected_categories and item[COL_NAME_LANGUAGE] == selected_language]
    # remove all keys in the item set whose name does not start with 'Unnamed'
    filtered_data = [{key: value for key, value in item.items() if not key.startswith('Unnamed')} for item in filtered_data] 
    
    # this is what filtered_data looks like:
    # {'Fremdsprache': 'Salvē', 'Zusatz': '', 'Deutsch': 'Sei gegrüßt', 'Kategorie': 'Latein: Salve', 'Sprache': 'Latein'}
    # {'Fremdsprache': 'pater', 'Zusatz': 'm.', 'Deutsch': 'der Vater', 'Kategorie': 'Latein: Salve', 'Sprache': 'Latein'}
    # {'Fremdsprache': 'māter', 'Zusatz': 'f.', 'Deutsch': 'die Mutter', 'Kategorie': 'Latein: Das Kapitol', 'Sprache': 'Latein'}
    # {'Fremdsprache': 'filius', 'Zusatz': 'm.', 'Deutsch': 'der Sohn', 'Kategorie': 'Latein: Das Kapitol', 'Sprache': 'Latein'}
    # {'Fremdsprache': 'filia', 'Zusatz': 'f.', 'Deutsch': 'die Tochter', 'Kategorie': 'Latein: Amphitheater', 'Sprache': 'Latein'}

    return _practice_on(filtered_data, selected_language, "Üben")

@app.route('/review_failures')
@require_auth
def review_failures():
    return _practice_on(session['list_of_wrong_answers'], session['test_data'][0][COL_NAME_LANGUAGE], "Fehler wiederholen", is_error_review=True)

def _get_language_labels(language, show_term):
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

def random_order(length):
    return random.sample(range(length), length)


@app.route('/test', methods=['POST'])
@require_auth
def test():
    selected_language = request.form['language']
    selected_categories = [category for category in request.form['categories'].split(',')]
    vocab_data = app.config['VOCAB_DATA']
    filtered_data = [item for item in vocab_data if item[COL_NAME_CATEGORY] in selected_categories and item[COL_NAME_LANGUAGE] == selected_language]
    session['test_data'] = filtered_data
    session['correct_answers'] = 0
    session['wrong_answers'] = 0
    session['show_term'] = True
    session['list_of_wrong_answers'] = []

    return redirect(url_for('testing'))

@app.route('/test_errors', methods=['POST'])
@require_auth
def test_errors():
    if not session.get('list_of_wrong_answers'):
        return redirect(url_for('index'))
    
    session['test_data'] = session['list_of_wrong_answers']
    session['correct_answers'] = 0
    session['wrong_answers'] = 0
    session['show_term'] = True
    session['list_of_wrong_answers'] = []

    return redirect(url_for('testing'))

def _get_position_in_test():
    return (session['correct_answers'] + session['wrong_answers']) % len(session['test_data'])

def _get_data_at_position(position):
    return session['test_data'][session['order'][position]]


@app.route('/testing')
@require_auth
def testing():
    if not session.get('test_data'):
        return redirect(url_for('index'))

    position = _get_position_in_test()
    if position == 0:
        session['order'] = random_order(len(session['test_data']))
    
    current_data = _get_data_at_position(position)
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
    """Handle the user's response during testing.

    Incorrect answers are logged before counters are updated.
    """
    # Capture the current test position before counters are modified so that
    # the associated data can be retrieved reliably.
    position = _get_position_in_test()
    current_data = _get_data_at_position(position)

    answer_correct = request.form['answer_correct'] == 'Richtig'
    if answer_correct:
        session['correct_answers'] += 1
    else:
        session['list_of_wrong_answers'].append(current_data)
        session['wrong_answers'] += 1

    return redirect(url_for('testing'))

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

@app.route('/write_scores', methods=['POST'])
@require_auth
def write_scores():
    """Write vocabulary scores to Google Sheets"""
    if not session.get('list_of_wrong_answers'):
        return redirect(url_for('index'))
    
    try:
        # Get the language from the first item in wrong answers
        wrong_answers = session['list_of_wrong_answers']
        if not wrong_answers:
            return redirect(url_for('index'))
            
        language = wrong_answers[0].get(COL_NAME_LANGUAGE, 'Englisch')
        
        # Write the scores to the appropriate sheet
        rows_written = write_scores_to_sheet(wrong_answers, language)
        
        # You could add a success message here if desired
        # For now, just redirect back to the error review
        return redirect(url_for('review_failures'))
        
    except Exception as e:
        # Handle errors gracefully - could add flash message here
        print(f"Error writing scores: {e}")
        return redirect(url_for('review_failures'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
