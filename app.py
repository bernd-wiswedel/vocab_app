from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import pandas as pd
import random
import json
import os
from datetime import timedelta
from fetch_data import fetch_data, COL_NAME_TERM, COL_NAME_COMMENT, COL_NAME_TRANSLATION, COL_NAME_CATEGORY, COL_NAME_LANGUAGE
from flask import Flask
from flask_session import Session

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

def get_language_labels(language, show_term):
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

@app.route('/')
def index():
    languages = ['Latein', 'Englisch']
    return render_template('index.html', languages=languages)

@app.route('/get_categories')
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
def reload_data():
    session.clear()
    app.config['VOCAB_DATA'] = fetch_data()
    return redirect(url_for('index'))

@app.route('/practice', methods=['POST'])
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
def review_failures():
    return _practice_on(session['list_of_wrong_answers'], session['test_data'][0][COL_NAME_LANGUAGE], "Fehler wiederholen")

    
def _practice_on(filtered_data, selected_language, header):
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
        col_name_translation=COL_NAME_TRANSLATION
    )

def random_order(length):
    return random.sample(range(length), length)


@app.route('/test', methods=['POST'])
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

def _get_position_in_test():
    return (session['correct_answers'] + session['wrong_answers']) % len(session['test_data'])

def _get_data_at_position(position):
    return session['test_data'][session['order'][position]]


@app.route('/testing')
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
    labels = get_language_labels(language, show_term)

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
def show_translation():
    current_data_str = request.form['current_data']
    current_data = json.loads(current_data_str)

    language = current_data[COL_NAME_LANGUAGE]
    show_term = session.get('show_term', True)

    # Use the utility function to get the labels and comment visibility
    labels = get_language_labels(language, show_term)

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
def check_answer():
    answer_correct = request.form['answer_correct'] == 'Richtig'
    if answer_correct:
        session['correct_answers'] += 1
    else:
        session['wrong_answers'] += 1
        position = _get_position_in_test()
        current_data = _get_data_at_position(position)
        session['list_of_wrong_answers'].append(current_data)

    return redirect(url_for('testing'))

@app.route('/switch_direction', methods=['POST'])
def switch_direction():
    current_data_str = request.form['current_data']
    current_data = json.loads(current_data_str)

    # Toggle the direction (show term or show translation)
    session['show_term'] = not session.get('show_term', True)
    show_term = session['show_term']

    language = current_data[COL_NAME_LANGUAGE]

    # Use the utility function to get the labels and comment visibility
    labels = get_language_labels(language, show_term)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
