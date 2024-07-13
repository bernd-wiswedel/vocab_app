import pandas as pd

SHEET_URL_BASE = 'https://docs.google.com/spreadsheets/d/1jTv5qPBcGCTcGFqnj9mnQvEwfjsf4YtQnA5GTJbU-Ig/export?format=csv&gid='
SHEET_URL_LATEIN = SHEET_URL_BASE + '0'
SHEET_URL_ENGLISH = SHEET_URL_BASE + '897548588'

COL_NAME_TERM = 'Fremdsprache'
COL_NAME_COMMENT = 'Zusatz'
COL_NAME_TRANSLATION = 'Deutsch'
COL_NAME_CATEGORY = 'Kategorie'
COL_NAME_LANGUAGE = 'Sprache'
SHEET_NAME_LATEIN = 'Latein'
SHEET_NAME_ENGLISH = 'Englisch'

def _fetch_data_from_google_sheet(csv_url, sheet_name):
    # Read the CSV into a DataFrame
    df = pd.read_csv(csv_url)
    
    # Replace NaN values with empty strings
    df.fillna('', inplace=True)
    
    # Process the data: ignore the first row and fill up missing category values
    if len(df) > 1:
        headers = df.columns.tolist()
        data_rows = df.iloc[1:].to_dict(orient='records')  # Skip the first row (header)
        filled_data = []
        previous_category = None

        for row in data_rows:
            row_dict = {headers[i]: row[headers[i]] for i in range(len(headers))}
            row_dict[COL_NAME_LANGUAGE] = sheet_name
            if row_dict[COL_NAME_CATEGORY] == '' and previous_category:
                row_dict[COL_NAME_CATEGORY] = previous_category
            previous_category = row_dict[COL_NAME_CATEGORY]
            filled_data.append(row_dict)

        return filled_data
    return []

def fetch_data():
    """
    Fetches the vocabulary data from the Google Sheet and returns it as a list of dictionaries.
    Each dictionary represents a row of the Google Sheet and contains the following
    key-value pairs:
    - 'Fremdsprache': The foreign language term.
    - 'Zusatz': Additional comments or information.
    - 'Deutsch': The German translation
    - 'Kategorie': The category of the vocabulary term.
    - 'Sprache': The language of the vocabulary term (either 'Latein' or 'Englisch').
    :return: A list of dictionaries containing the vocabulary data.
    """
    latin_data = _fetch_data_from_google_sheet(SHEET_URL_LATEIN, SHEET_NAME_LATEIN)
    english_data = _fetch_data_from_google_sheet(SHEET_URL_ENGLISH, SHEET_NAME_ENGLISH)
    return latin_data + english_data

vocab_data = fetch_data()
print(f'Read {len(vocab_data)} rows of data from the Google Sheet.')
