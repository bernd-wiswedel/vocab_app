import pandas as pd
import json
import os
import glob
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SHEET_URL_BASE = 'https://docs.google.com/spreadsheets/d/1jTv5qPBcGCTcGFqnj9mnQvEwfjsf4YtQnA5GTJbU-Ig/export?format=csv&gid='
SHEET_URL_LATEIN = SHEET_URL_BASE + '0'
SHEET_URL_ENGLISH = SHEET_URL_BASE + '897548588'
SPREADSHEET_ID = '1jTv5qPBcGCTcGFqnj9mnQvEwfjsf4YtQnA5GTJbU-Ig'

# Score sheet GIDs for writing
SCORES_GID_ENGLISH = '2016285208'
SCORES_GID_LATEIN = '410708540'
SCORES_SHEET_NAME_ENGLISH = 'Scores Englisch (Jakob)'
SCORES_SHEET_NAME_LATEIN = 'Scores Latein (Jakob)'

COL_NAME_TERM = 'Fremdsprache'
COL_NAME_COMMENT = 'Zusatz'
COL_NAME_TRANSLATION = 'Deutsch'
COL_NAME_CATEGORY = 'Kategorie'
COL_NAME_LANGUAGE = 'Sprache'
SHEET_NAME_LATEIN = 'Latein'
SHEET_NAME_ENGLISH = 'Englisch'

def _get_google_credentials():
    """
    Get Google Sheets API credentials from environment variable or local file.
    Returns authenticated credentials for Google Sheets API access.
    """
    # Define the required scopes for Google Sheets API
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    # Try to get credentials from environment variable first
    credentials_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    
    if credentials_json:
        # Use credentials from environment variable (for production/Koyeb)
        try:
            credentials_info = json.loads(credentials_json)
            credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
            return credentials
        except json.JSONDecodeError as e:
            print(f"Error parsing GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
            # Fall through to file-based authentication
    
    # Fallback to local file for development
    key_files = glob.glob('keys/vocab-app-*.json')
    if key_files:
        credentials = Credentials.from_service_account_file(key_files[0], scopes=SCOPES)
        return credentials
    
    raise Exception("No Google service account credentials found. Set GOOGLE_SERVICE_ACCOUNT_JSON environment variable or place key file in keys/ folder.")

def _get_sheets_service():
    """
    Get an authenticated Google Sheets API service instance.
    """
    credentials = _get_google_credentials()
    service = build('sheets', 'v4', credentials=credentials)
    return service

def _fetch_data_from_google_sheet(csv_url, sheet_name):
    # Read the CSV into a DataFrame
    df = pd.read_csv(csv_url, dtype=str)  # Ensure all data is read as strings
    
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
            
            # Skip rows where Fremdsprache is blank
            if row_dict[COL_NAME_TERM] == '':
                continue
                
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

def write_scores_to_sheet(vocab_items, language='Englisch'):
    """
    Write vocabulary scores to the appropriate Google Sheet tab.
    
    :param vocab_items: List of vocabulary items (dictionaries with 'Key' field)
    :param language: 'Englisch' or 'Latein' to determine which sheet tab to write to
    """
    from datetime import datetime
    
    # Determine which sheet to write to
    if language == 'Englisch':
        sheet_name = SCORES_SHEET_NAME_ENGLISH
    elif language == 'Latein':
        sheet_name = SCORES_SHEET_NAME_LATEIN
    else:
        raise ValueError(f"Unsupported language: {language}")
    
    # Get the sheets service
    service = _get_sheets_service()
    
    try:
        # Read existing data to find current row positions
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{sheet_name}'!A:C"
        ).execute()
        
        existing_data = result.get('values', [])
        
        # Create a map of existing keys to row numbers (1-indexed)
        key_to_row = {}
        if len(existing_data) > 1:  # Skip header row
            for i, row in enumerate(existing_data[1:], start=2):
                if row and len(row) > 0:  # Make sure row has data
                    key_to_row[row[0]] = i
        
        # Prepare batch update data
        current_time = datetime.now().isoformat(timespec='seconds')
        updates = []
        
        for item in vocab_items:
            key = item.get('Fremdsprache', '')
            if not key:
                continue  # Skip items without keys
                
            row_data = [key, 'red', current_time]
            
            if key in key_to_row:
                # Update existing row
                row_num = key_to_row[key]
                updates.append({
                    'range': f"'{sheet_name}'!A{row_num}:C{row_num}",
                    'values': [row_data]
                })
            else:
                # Append new row (find next empty row)
                next_row = len(existing_data) + 1
                updates.append({
                    'range': f"'{sheet_name}'!A{next_row}:C{next_row}",
                    'values': [row_data]
                })
                # Update our tracking for subsequent items
                existing_data.append(row_data)
        
        # Execute batch update if we have updates
        if updates:
            body = {
                'valueInputOption': 'RAW',
                'data': updates
            }
            
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=body
            ).execute()
            
            return len(updates)
        
        return 0
        
    except Exception as e:
        print(f"Error writing to Google Sheets: {e}")
        raise

# Keep the existing debug print for backwards compatibility
if __name__ == "__main__":
    vocab_data = fetch_data()
    print(f'Read {len(vocab_data)} rows of data from the Google Sheet.')
