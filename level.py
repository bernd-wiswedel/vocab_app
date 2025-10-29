"""
Level system for vocabulary learning with spaced repetition.

This module defines the progression levels for vocabulary terms and implements
the logic for level transitions, test eligibility, and urgency calculations.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

class Urgency:
    """Represents urgency for test selection with proper comparison."""
    
    def __init__(self, level_index: int, days_until_expiry: int):
        """
        Initialize urgency.
        
        :param level_index: Index of the level (higher = more advanced)
        :param days_until_expiry: Days until term expires (lower = more urgent)
        """
        self.level_index = level_index
        self.days_until_expiry = days_until_expiry
    
    def __lt__(self, other):
        """Less than comparison (for sorting - higher urgency comes first)."""
        if not isinstance(other, Urgency):
            return NotImplemented
        
        # First compare by days until expiry (fewer days = more urgent)
        if self.days_until_expiry != other.days_until_expiry:
            return self.days_until_expiry < other.days_until_expiry
        
        # If same expiry, higher level wins (more urgent)
        return self.level_index > other.level_index
    
    def __le__(self, other):
        return self < other or self == other
    
    def __gt__(self, other):
        return not self <= other
    
    def __ge__(self, other):
        return not self < other
    
    def __eq__(self, other):
        if not isinstance(other, Urgency):
            return NotImplemented
        return (self.level_index == other.level_index and 
                self.days_until_expiry == other.days_until_expiry)
    
    def __repr__(self):
        return f"Urgency(level={self.level_index}, expiry_in={self.days_until_expiry})"


# Special urgency instances for common cases
NOT_EXPIRED_LOW_URGENCY = Urgency(-1, 999999)  # Lowest priority - not ready for testing
RED_1_LOW_URGENCY = Urgency(0, 999999)  # 2nd Lowest priority - Red-1 terms

class Level:
    """Represents a single level in the vocabulary learning system."""
    
    def __init__(self, name: str, min_days: int, max_days: Optional[int]):
        """
        Initialize a level.
        
        :param name: Level name (e.g., "Red-1", "Yellow-2", "Green")
        :param min_days: Minimum days before term can be tested again
        :param max_days: Maximum days before term falls back to Red-1 (None for infinite)
        """
        self.name = name
        self.min_days = min_days
        self.max_days = max_days
    
    def __repr__(self):
        return f"Level('{self.name}', min={self.min_days}, max={self.max_days})"


class LevelSystem:
    """Manages the vocabulary learning level system."""
    
    # Define all levels in progression order
    LEVELS = [
        Level("Red-1", min_days=0, max_days=None),  # Always available, never expires
        Level("Red-2", min_days=1, max_days=7),
        Level("Red-3", min_days=1, max_days=7),
        Level("Red-4", min_days=1, max_days=7),
        Level("Yellow-1", min_days=4, max_days=7),
        Level("Yellow-2", min_days=4, max_days=7),
        Level("Green", min_days=25, max_days=33),
    ]
    
    # Create lookup dictionaries
    LEVEL_BY_NAME = {level.name: level for level in LEVELS}
    LEVEL_INDEX = {level.name: i for i, level in enumerate(LEVELS)}
    
    @classmethod
    def get_level(cls, level_name: str) -> Level:
        """Get level by name."""
        return cls.LEVEL_BY_NAME.get(level_name, cls.LEVELS[0])  # Default to Red-1
    
    @classmethod
    def is_valid_level(cls, level_name: str) -> bool:
        """Check if a level name is valid."""
        return level_name in cls.LEVEL_BY_NAME
    
    @classmethod
    def get_valid_levels(cls) -> List[str]:
        """Get list of all valid level names."""
        return list(cls.LEVEL_BY_NAME.keys())
    
    @classmethod
    def validate_and_sanitize_status(cls, status: str, last_test_date: str = None) -> str:
        """
        Validate status value and return a sanitized version.
        
        :param status: The status to validate
        :param last_test_date: When the term was last tested (for expiry check)
        :return: Valid status (defaults to Red-1 if invalid or expired)
        """
        # Check if status is valid
        if not cls.is_valid_level(status):
            return "Red-1"  # Default to Red-1 for invalid status
        
        # Check if status has expired (fallen back to Red-1)
        if last_test_date and cls.is_expired(status, last_test_date):
            return "Red-1"
        
        return status
    
    @classmethod
    def get_next_level(cls, current_level: str) -> Optional[str]:
        """Get the next level name for escalation."""
        current_index = cls.LEVEL_INDEX.get(current_level, 0)
        if current_index < len(cls.LEVELS) - 1:
            return cls.LEVELS[current_index + 1].name
        return None  # Already at highest level
    
    @classmethod
    def is_testable(cls, level_name: str, last_test_date: str) -> bool:
        """
        Check if a term is eligible for testing based on minimum days.
        
        :param level_name: Current level of the term
        :param last_test_date: Date when term was last tested (YYYY-MM-DD format)
        :return: True if term can be tested now
        """
        if not last_test_date:
            return True  # Never tested, always testable
            
        level = cls.get_level(level_name)
        last_date = date.fromisoformat(last_test_date)
        days_since_test = (date.today() - last_date).days
        
        return days_since_test >= level.min_days
    
    @classmethod
    def is_expired(cls, level_name: str, last_test_date: str) -> bool:
        """
        Check if a term has exceeded maximum days and should fall back to Red-1.
        
        :param level_name: Current level of the term
        :param last_test_date: Date when term was last tested
        :return: True if term has expired
        """
        if not last_test_date or level_name == "Red-1":
            return False  # Red-1 never expires
            
        level = cls.get_level(level_name)
        if level.max_days is None:
            return False  # No expiration
            
        last_date = date.fromisoformat(last_test_date)
        days_since_test = (date.today() - last_date).days
        
        return days_since_test > level.max_days
    
    @classmethod
    def calculate_urgency(cls, level_name: str, last_test_date: str) -> Urgency:
        """
        Calculate urgency for test selection.
        
        :param level_name: Current level of the term
        :param last_test_date: Date when term was last tested
        :return: Urgency object for comparison
        """
        level = cls.get_level(level_name)
        level_index = cls.LEVEL_INDEX.get(level_name, 0)
        
        # Handle Red-1 terms (second lowest priority)
        if level_name == "Red-1":
            return RED_1_LOW_URGENCY
        
        last_date = date.fromisoformat(last_test_date)
        days_since_test = (date.today() - last_date).days
        
        # Check if term is not yet ready for testing (age < min_days)
        if days_since_test < level.min_days:
            return NOT_EXPIRED_LOW_URGENCY
        
        # Calculate days until expiry
        if level.max_days is None:
            # No expiration - medium priority
            days_until_expiry = 500
        else:
            days_until_expiry = level.max_days - days_since_test
            # If already expired, make it very urgent
            if days_until_expiry < 0:
                days_until_expiry = 0
        
        return Urgency(level_index, days_until_expiry)
    
    @classmethod
    def process_answer(cls, current_level: str, is_correct: bool, last_test_date: str) -> Tuple[str, str]:
        """
        Process a test answer and determine new level and date.
        
        :param current_level: Current level of the term
        :param is_correct: Whether the answer was correct
        :param last_test_date: When the term was last tested
        :return: Tuple of (new_level, new_date)
        """
        today = date.today().isoformat()
        
        # Handle expired terms - they fall back to Red-1 regardless of answer
        if cls.is_expired(current_level, last_test_date):
            return "Red-1", today
        
        # Incorrect answer always goes to Red-1
        if not is_correct:
            return "Red-1", today
        
        # Correct answer - check if minimum time has passed for escalation
        if cls.is_testable(current_level, last_test_date):
            next_level = cls.get_next_level(current_level)
            if next_level:
                return next_level, today
            else:
                # Already at highest level (Green) - reset timer
                return current_level, today
        
        # Correct but too soon - stay at current level with updated date
        return current_level, today
    
def get_testable_terms(vocab_data: List[Dict], max_terms: int = 10000) -> List[Dict]:
    """
    Select terms for testing based on eligibility and urgency.
    
    :param vocab_data: List of vocabulary items with pre-calculated urgency
    :param max_terms: Maximum number of terms to return
    :return: List of terms sorted by urgency (most urgent first)
    """
    testable_terms = []
    
    for item in vocab_data:
        # Use pre-calculated urgency from fetch_data()
        urgency = item.get('score_urgency')
        
        # Skip items without urgency (shouldn't happen) or non-testable terms
        if urgency is None or urgency is NOT_EXPIRED_LOW_URGENCY:
            continue
            
        testable_terms.append({
            'item': item,
            'urgency': urgency,
            'level': item.get('score_status', 'Red-1')
        })
    
    # Sort by urgency (most urgent first - smallest urgency values come first)
    testable_terms.sort(key=lambda x: x['urgency'])
    
    # Return top terms
    return [term['item'] for term in testable_terms[:max_terms]]


if __name__ == "__main__":
    # Test the level system
    system = LevelSystem()
    
    print("Level System Configuration:")
    for level in system.LEVELS:
        print(f"  {level}")
    
    print(f"\nNext level after Red-2: {system.get_next_level('Red-2')}")
    print(f"Next level after Green: {system.get_next_level('Green')}")
    
    # Test urgency calculation and comparison
    print(f"\nUrgency comparison test:")
    test_cases = [
        ('Red-1', None, 'Red-1 never tested'),
        ('Red-1', date.today().isoformat(), 'Red-1 tested today'),
        ('Red-2', None, 'Red-2 never tested'),
        ('Red-2', date.today().isoformat(), 'Red-2 tested today'),
        ('Red-2', (date.today() - timedelta(days=7)).isoformat(), 'Red-2 week ago (expired)'),
        ('Green', date.today().isoformat(), 'Green tested today (not ready)'),
        ('Green', (date.today() - timedelta(days=30)).isoformat(), 'Green 30 days ago'),
        ('Green', (date.today() - timedelta(days=35)).isoformat(), 'Green 35 days ago (expired)'),
    ]
    
    # Calculate urgencies
    urgencies = []
    for level, test_date, desc in test_cases:
        urgency = system.calculate_urgency(level, test_date)
        urgencies.append((urgency, desc))
    
    # Sort by urgency (most urgent first)
    urgencies.sort()
    
    print("Priority ranking (most urgent first):")
    for i, (urgency, desc) in enumerate(urgencies, 1):
        print(f"{i:2d}. {urgency} - {desc}")