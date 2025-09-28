import pandas as pd
import json
import os
import glob
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from level import LevelSystem, Urgency, NOT_EXPIRED_LOW_URGENCY
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from collections import OrderedDict

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


class VocabularyTerm:
    """Represents a single vocabulary term with its metadata"""
    def __init__(self, term: str, translation: str, language: str, category: str, comment: str = ""):
        self.term = term              # Foreign language term (Fremdsprache)
        self.translation = translation # German translation (Deutsch)
        self.language = language      # 'Latein' or 'Englisch'
        self.category = category      # Lesson/chapter grouping
        self.comment = comment        # Grammar notes (Zusatz)
    
    def __str__(self) -> str:
        return f"{self.term} -> {self.translation}"


class ScoreData:
    """Represents scoring/progress data for a vocabulary term"""
    def __init__(self, status: str = 'Red-1', date: str = None, urgency: Urgency = None):
        self.status = status          # Level name ('Red-1', 'Yellow-2', etc.)
        self.date = date             # Last test date (ISO format YYYY-MM-DD)
        self.urgency = urgency or LevelSystem.calculate_urgency(status, date)
    
    def update_score(self, new_status: str, new_date: str) -> None:
        """Update score with new test result"""
        self.status = new_status
        self.date = new_date
        self.urgency = LevelSystem.calculate_urgency(new_status, new_date)


class VocabularyItem:
    """Combined vocabulary term and its score data"""
    def __init__(self, vocab_term: VocabularyTerm, score_data: ScoreData = None):
        self.vocab = vocab_term
        self.score = score_data or ScoreData()  # Default to Red-1 if no score
    
    @property
    def key(self) -> Tuple[str, str]:
        """Unique identifier: (term, language)"""
        return (self.vocab.term, self.vocab.language)
    
    def to_dict(self) -> dict:
        """Convert to dictionary format for backward compatibility"""
        return {
            COL_NAME_TERM: self.vocab.term,
            COL_NAME_TRANSLATION: self.vocab.translation,
            COL_NAME_LANGUAGE: self.vocab.language,
            COL_NAME_CATEGORY: self.vocab.category,
            COL_NAME_COMMENT: self.vocab.comment,
            'score_status': self.score.status,
            'score_date': self.score.date,
            'score_urgency': self.score.urgency
        }


class VocabularyDatabase:
    """Main data container using the requested mapping structure"""
    def __init__(self):
        # Use OrderedDict to preserve insertion order (Google Sheets order)
        self.data: OrderedDict[Tuple[str, str], VocabularyItem] = OrderedDict()
    
    def add_vocabulary_item(self, vocab_term: VocabularyTerm, score_data: ScoreData = None) -> None:
        """Add or update a vocabulary item"""
        item = VocabularyItem(vocab_term, score_data)
        key = (vocab_term.term, vocab_term.language)
        self.data[key] = item
    
    def get_item(self, term: str, language: str) -> Optional[VocabularyItem]:
        """Get vocabulary item by term and language"""
        return self.data.get((term, language))
    
    def get_by_language(self, language: str) -> List[VocabularyItem]:
        """Get all items for a specific language in Google Sheets order"""
        # OrderedDict preserves insertion order, so we just filter
        return [item for key, item in self.data.items() if key[1] == language]
    
    def get_by_category(self, language: str, category: str) -> List[VocabularyItem]:
        """Get items filtered by language and category"""
        return [item for item in self.get_by_language(language) 
                if item.vocab.category == category]
    
    def get_testable_terms(self, language: str = None, category: str = None, limit: int = 10000) -> List[VocabularyItem]:
        """Get terms ready for testing, filtered and sorted by urgency"""
        items = list(self.data.values())
        
        # Apply filters
        if language:
            items = [item for item in items if item.vocab.language == language]
        if category:
            items = [item for item in items if item.vocab.category == category]
        
        # Filter testable and sort by urgency
        testable_items = [item for item in items if item.score.urgency != NOT_EXPIRED_LOW_URGENCY]
        testable_items.sort(key=lambda x: x.score.urgency)
        return testable_items[:limit]
    
    def update_score(self, term: str, language: str, new_status: str, new_date: str) -> None:
        """Update score for a specific term"""
        item = self.get_item(term, language)
        if item:
            item.score.update_score(new_status, new_date)
    
    def to_dict_list(self) -> List[dict]:
        """Convert to legacy dictionary list format for backward compatibility"""
        return [item.to_dict() for item in self.data.values()]


def _get_google_credentials() -> Credentials:
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

def _fetch_data_from_google_sheet(csv_url: str, sheet_name: str) -> List[dict]:
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

def fetch_data() -> VocabularyDatabase:
    """
    Fetches the vocabulary data from the Google Sheet and returns it as a VocabularyDatabase.
    
    The database contains VocabularyItem objects with both vocabulary terms and score data.
    For backward compatibility, you can call .to_dict_list() on the returned database.
    
    :return: VocabularyDatabase instance containing all vocabulary with score information
    """
    print("Fetching vocabulary data from sheets...")
    latin_data = _fetch_data_from_google_sheet(SHEET_URL_LATEIN, SHEET_NAME_LATEIN)
    english_data = _fetch_data_from_google_sheet(SHEET_URL_ENGLISH, SHEET_NAME_ENGLISH)
    
    # Combine vocabulary data
    raw_vocab_data = latin_data + english_data
    print(f"Loaded {len(raw_vocab_data)} vocabulary entries")
    
    # Fetch scores
    print("Fetching score data...")
    scores = _fetch_scores()
    print(f"Loaded {len(scores)} score entries")
    
    # Create vocabulary database
    vocab_db = VocabularyDatabase()
    
    # Process each vocabulary entry
    for raw_item in raw_vocab_data:
        # Create vocabulary term
        vocab_term = VocabularyTerm(
            term=raw_item[COL_NAME_TERM],
            translation=raw_item[COL_NAME_TRANSLATION],
            language=raw_item[COL_NAME_LANGUAGE],
            category=raw_item[COL_NAME_CATEGORY],
            comment=raw_item.get(COL_NAME_COMMENT, "")
        )
        
        # Get or create score data
        term_key = vocab_term.term
        if term_key in scores:
            score_info = scores[term_key]
            old_status = score_info.get('status')
            # Migrate old status to new level system
            migrated_status = LevelSystem.migrate_old_status(old_status)
            date_val = score_info.get('date')
            urgency = LevelSystem.calculate_urgency(migrated_status, date_val)
            score_data = ScoreData(migrated_status, date_val, urgency)
        else:
            # Default Red-1 for new terms
            urgency = LevelSystem.calculate_urgency('Red-1', None)
            score_data = ScoreData('Red-1', None, urgency)
        
        # Add to database
        vocab_db.add_vocabulary_item(vocab_term, score_data)
    
    vocab_with_scores = len([item for item in vocab_db.data.values() 
                           if item.score.status != 'Red-1' or item.score.date])
    print(f"Processed {vocab_with_scores} vocabulary items with score history")
    
    return vocab_db

def write_scores_to_sheet(vocab_items, language='Englisch', level_name='Red-1'):
    """
    Write vocabulary scores to the appropriate Google Sheet tab.
    
    :param vocab_items: List of vocabulary items (dictionaries with term keys)
    :param language: 'Englisch' or 'Latein' to determine which sheet tab to write to
    :param level_name: Level name to write (default 'Red-1' for wrong answers)
    """
    from datetime import date
    
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
        current_date = date.today().isoformat()
        updates = []
        
        for item in vocab_items:
            key = item.get('Fremdsprache', '')
            if not key:
                continue  # Skip items without keys
                
            row_data = [key, level_name, current_date]
            
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

def _fetch_scores():
    """
    Fetch vocabulary scores from both English and Latin score sheets.
    Returns a dictionary mapping vocabulary terms to their score data.
    
    :return: Dictionary with structure {term: {'status': 'red', 'date': 'YYYY-MM-DD'}}
    """
    service = _get_sheets_service()
    scores = {}
    
    # Define sheets to fetch from
    score_sheets = [
        (SCORES_SHEET_NAME_ENGLISH, 'Englisch'),
        (SCORES_SHEET_NAME_LATEIN, 'Latein')
    ]
    
    try:
        for sheet_name, language in score_sheets:
            try:
                # Fetch score data from the sheet
                result = service.spreadsheets().values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"'{sheet_name}'!A:C"
                ).execute()
                
                score_data = result.get('values', [])
                
                # Skip header row if present, process score data
                if len(score_data) > 1:  # Has header + data
                    for row in score_data[1:]:  # Skip header
                        if len(row) >= 3:  # Ensure we have term, status, date
                            term = row[0]
                            status = row[1] 
                            date_value = row[2]
                            
                            scores[term] = {
                                'status': status,
                                'date': date_value,
                                'language': language
                            }
                            
                print(f"Loaded {len([s for s in scores.values() if s.get('language') == language])} scores from {language} sheet")
                            
            except Exception as e:
                print(f"Warning: Could not fetch scores from {sheet_name}: {e}")
                # Continue with other sheets even if one fails
                
        return scores
        
    except Exception as e:
        print(f"Error fetching scores: {e}")
        return {}  # Return empty dict on error

# Keep the existing debug print for backwards compatibility
if __name__ == "__main__":
    vocab_data = fetch_data()
    print(f'Read {len(vocab_data.data)} rows of data from the Google Sheet.')
