"""Unit tests for level.py - Spaced repetition system."""

import pytest
from datetime import date, timedelta
from level import Level, Urgency, LevelSystem, RED_1_LOW_URGENCY, NOT_EXPIRED_LOW_URGENCY


class TestLevel:
    """Test the Level class."""
    
    def test_level_creation(self):
        """Test creating a Level instance."""
        level = Level("Red-1", min_days=0, max_days=None)
        assert level.name == "Red-1"
        assert level.min_days == 0
        assert level.max_days is None
    
    def test_level_repr(self):
        """Test Level string representation."""
        level = Level("Red-2", min_days=1, max_days=7)
        assert "Red-2" in repr(level)
        assert "min=1" in repr(level)
        assert "max=7" in repr(level)


class TestUrgency:
    """Test the Urgency class and comparison logic."""
    
    def test_urgency_creation(self):
        """Test creating an Urgency instance."""
        urgency = Urgency(level_index=2, days_until_expiry=5)
        assert urgency.level_index == 2
        assert urgency.days_until_expiry == 5
    
    def test_urgency_comparison_by_days(self):
        """Test that urgency comparison prioritizes days until expiry."""
        urgent = Urgency(level_index=1, days_until_expiry=1)
        less_urgent = Urgency(level_index=1, days_until_expiry=5)
        
        assert urgent < less_urgent
        assert less_urgent > urgent
        assert urgent <= less_urgent
        assert less_urgent >= urgent
    
    def test_urgency_comparison_by_level_when_days_equal(self):
        """Test that higher level wins when days are equal."""
        higher_level = Urgency(level_index=5, days_until_expiry=3)
        lower_level = Urgency(level_index=2, days_until_expiry=3)
        
        # Higher level = more urgent when days are equal
        assert higher_level < lower_level
        assert lower_level > higher_level
    
    def test_urgency_equality(self):
        """Test urgency equality."""
        urg1 = Urgency(level_index=2, days_until_expiry=5)
        urg2 = Urgency(level_index=2, days_until_expiry=5)
        urg3 = Urgency(level_index=3, days_until_expiry=5)
        
        assert urg1 == urg2
        assert urg1 != urg3
    
    def test_urgency_sorting(self):
        """Test sorting a list of urgencies."""
        urgencies = [
            Urgency(level_index=1, days_until_expiry=10),
            Urgency(level_index=5, days_until_expiry=2),
            Urgency(level_index=3, days_until_expiry=2),
            Urgency(level_index=2, days_until_expiry=1),
        ]
        
        sorted_urgencies = sorted(urgencies)
        
        # Most urgent first: days=1, then days=2 (level 5 before 3), then days=10
        assert sorted_urgencies[0].days_until_expiry == 1
        assert sorted_urgencies[1].days_until_expiry == 2
        assert sorted_urgencies[1].level_index == 5
        assert sorted_urgencies[2].days_until_expiry == 2
        assert sorted_urgencies[2].level_index == 3
        assert sorted_urgencies[3].days_until_expiry == 10
    
    def test_urgency_repr(self):
        """Test Urgency string representation."""
        urgency = Urgency(level_index=3, days_until_expiry=7)
        repr_str = repr(urgency)
        assert "level=3" in repr_str
        assert "expiry_in=7" in repr_str
    
    def test_special_urgency_constants(self):
        """Test the special urgency constants."""
        assert NOT_EXPIRED_LOW_URGENCY.level_index == -1
        assert NOT_EXPIRED_LOW_URGENCY.days_until_expiry == 999999
        
        assert RED_1_LOW_URGENCY.level_index == 0
        assert RED_1_LOW_URGENCY.days_until_expiry == 999999
        
        # NOT_EXPIRED should be lower priority than RED_1
        assert RED_1_LOW_URGENCY < NOT_EXPIRED_LOW_URGENCY


class TestLevelSystem:
    """Test the LevelSystem class."""
    
    def test_level_system_has_all_levels(self):
        """Test that all expected levels are defined."""
        expected_levels = ['Red-1', 'Red-2', 'Red-3', 'Red-4', 'Yellow-1', 'Yellow-2', 'Green']
        assert len(LevelSystem.LEVELS) == 7
        for level_name in expected_levels:
            assert level_name in LevelSystem.LEVEL_BY_NAME
    
    def test_get_level(self):
        """Test getting a level by name."""
        red1 = LevelSystem.get_level('Red-1')
        assert red1.name == 'Red-1'
        assert red1.min_days == 0
        assert red1.max_days is None
        
        green = LevelSystem.get_level('Green')
        assert green.name == 'Green'
        assert green.min_days == 25
        assert green.max_days == 33
    
    def test_get_level_invalid_returns_red1(self):
        """Test that invalid level names default to Red-1."""
        level = LevelSystem.get_level('Invalid-Level')
        assert level.name == 'Red-1'
    
    def test_is_valid_level(self):
        """Test level name validation."""
        assert LevelSystem.is_valid_level('Red-1')
        assert LevelSystem.is_valid_level('Green')
        assert not LevelSystem.is_valid_level('Invalid')
        assert not LevelSystem.is_valid_level('')
    
    def test_get_valid_levels(self):
        """Test getting all valid level names."""
        levels = LevelSystem.get_valid_levels()
        assert len(levels) == 7
        assert 'Red-1' in levels
        assert 'Green' in levels
    
    def test_validate_and_sanitize_status_valid(self):
        """Test sanitizing a valid status."""
        assert LevelSystem.validate_and_sanitize_status('Red-2') == 'Red-2'
        assert LevelSystem.validate_and_sanitize_status('Green') == 'Green'
    
    def test_validate_and_sanitize_status_invalid(self):
        """Test sanitizing an invalid status defaults to Red-1."""
        assert LevelSystem.validate_and_sanitize_status('Invalid') == 'Red-1'
        assert LevelSystem.validate_and_sanitize_status('') == 'Red-1'
        assert LevelSystem.validate_and_sanitize_status(None) == 'Red-1'
    
    def test_validate_and_sanitize_status_expired(self):
        """Test sanitizing an expired status."""
        old_date = (date.today() - timedelta(days=10)).isoformat()
        # Red-2 has max_days=7, so 10 days ago is expired
        assert LevelSystem.validate_and_sanitize_status('Red-2', old_date) == 'Red-1'
    
    def test_get_next_level(self):
        """Test getting the next level in progression."""
        assert LevelSystem.get_next_level('Red-1') == 'Red-2'
        assert LevelSystem.get_next_level('Red-2') == 'Red-3'
        assert LevelSystem.get_next_level('Yellow-2') == 'Green'
        assert LevelSystem.get_next_level('Green') is None  # Highest level
    
    def test_is_testable_never_tested(self):
        """Test that never-tested terms are always testable."""
        assert LevelSystem.is_testable('Red-1', None)
        assert LevelSystem.is_testable('Red-2', None)
        assert LevelSystem.is_testable('Green', None)
    
    def test_is_testable_red1_always_testable(self):
        """Test that Red-1 terms are always testable."""
        today = date.today().isoformat()
        assert LevelSystem.is_testable('Red-1', today)
    
    def test_is_testable_respects_min_days(self):
        """Test that testability respects minimum days."""
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        
        # Red-2 has min_days=1
        assert not LevelSystem.is_testable('Red-2', today)
        assert LevelSystem.is_testable('Red-2', yesterday)
        
        # Yellow-1 has min_days=4
        assert not LevelSystem.is_testable('Yellow-1', yesterday)
        assert LevelSystem.is_testable('Yellow-1', week_ago)
        
        # Green has min_days=25
        assert not LevelSystem.is_testable('Green', week_ago)
        month_ago = (date.today() - timedelta(days=30)).isoformat()
        assert LevelSystem.is_testable('Green', month_ago)
    
    def test_is_expired_red1_never_expires(self):
        """Test that Red-1 never expires."""
        very_old = (date.today() - timedelta(days=365)).isoformat()
        assert not LevelSystem.is_expired('Red-1', very_old)
        assert not LevelSystem.is_expired('Red-1', None)
    
    def test_is_expired_respects_max_days(self):
        """Test that expiration respects maximum days."""
        # Red-2 has max_days=7
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        eight_days_ago = (date.today() - timedelta(days=8)).isoformat()
        
        assert not LevelSystem.is_expired('Red-2', week_ago)  # On the boundary
        assert LevelSystem.is_expired('Red-2', eight_days_ago)  # Past boundary
        
        # Green has max_days=33
        days_33_ago = (date.today() - timedelta(days=33)).isoformat()
        days_34_ago = (date.today() - timedelta(days=34)).isoformat()
        
        assert not LevelSystem.is_expired('Green', days_33_ago)
        assert LevelSystem.is_expired('Green', days_34_ago)
    
    def test_calculate_urgency_red1(self):
        """Test urgency calculation for Red-1 terms."""
        urgency = LevelSystem.calculate_urgency('Red-1', None)
        assert urgency == RED_1_LOW_URGENCY
        
        # Red-1 with date should also return RED_1_LOW_URGENCY
        urgency = LevelSystem.calculate_urgency('Red-1', date.today().isoformat())
        assert urgency == RED_1_LOW_URGENCY
    
    def test_calculate_urgency_not_ready(self):
        """Test urgency for terms not yet ready for testing."""
        # Red-2 tested today (min_days=1, not ready yet)
        today = date.today().isoformat()
        urgency = LevelSystem.calculate_urgency('Red-2', today)
        assert urgency == NOT_EXPIRED_LOW_URGENCY
    
    def test_calculate_urgency_ready_terms(self):
        """Test urgency calculation for ready terms."""
        # Red-2 tested 5 days ago (min_days=1, max_days=7)
        # days_until_expiry = 7 - 5 = 2
        five_days_ago = (date.today() - timedelta(days=5)).isoformat()
        urgency = LevelSystem.calculate_urgency('Red-2', five_days_ago)
        
        assert urgency.level_index == 1  # Red-2 is at index 1
        assert urgency.days_until_expiry == 2
    
    def test_calculate_urgency_expired_term(self):
        """Test urgency for expired terms (very urgent)."""
        # Red-2 tested 10 days ago (max_days=7, so expired)
        ten_days_ago = (date.today() - timedelta(days=10)).isoformat()
        urgency = LevelSystem.calculate_urgency('Red-2', ten_days_ago)
        
        # Expired terms get urgency of 0 (most urgent)
        assert urgency.days_until_expiry == 0
    
    def test_process_answer_correct_progression(self):
        """Test correct answer advances level when eligible."""
        # Red-2 tested yesterday (min_days=1, eligible for progression)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        new_level, new_date = LevelSystem.process_answer('Red-2', True, yesterday)
        
        assert new_level == 'Red-3'
        assert new_date == date.today().isoformat()
    
    def test_process_answer_correct_too_soon(self):
        """Test correct answer too soon stays at same level."""
        # Red-2 tested today (min_days=1, not eligible yet)
        today = date.today().isoformat()
        new_level, new_date = LevelSystem.process_answer('Red-2', True, today)
        
        assert new_level == 'Red-2'  # Stays at same level
        assert new_date == date.today().isoformat()  # Date updates
    
    def test_process_answer_incorrect_goes_to_red1(self):
        """Test incorrect answer always goes to Red-1."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        # From Red-2
        new_level, new_date = LevelSystem.process_answer('Red-2', False, yesterday)
        assert new_level == 'Red-1'
        
        # From Green
        month_ago = (date.today() - timedelta(days=30)).isoformat()
        new_level, new_date = LevelSystem.process_answer('Green', False, month_ago)
        assert new_level == 'Red-1'
    
    def test_process_answer_green_stays_green(self):
        """Test that Green (highest level) stays at Green when correct."""
        # Green tested 30 days ago (min_days=25, eligible)
        month_ago = (date.today() - timedelta(days=30)).isoformat()
        new_level, new_date = LevelSystem.process_answer('Green', True, month_ago)
        
        assert new_level == 'Green'  # Stays at Green
        assert new_date == date.today().isoformat()
    
    def test_process_answer_expired_goes_to_red1(self):
        """Test that expired terms go to Red-1 regardless of answer."""
        # Red-2 tested 10 days ago (max_days=7, expired)
        ten_days_ago = (date.today() - timedelta(days=10)).isoformat()
        
        # Even if correct, expired term goes to Red-1
        new_level, new_date = LevelSystem.process_answer('Red-2', True, ten_days_ago)
        assert new_level == 'Red-1'
    
    def test_process_answer_boundary_conditions(self):
        """Test process_answer at exact boundary days."""
        # Red-2: min_days=1, max_days=7
        
        # At exactly 1 day (min_days boundary) - should progress
        one_day_ago = (date.today() - timedelta(days=1)).isoformat()
        new_level, _ = LevelSystem.process_answer('Red-2', True, one_day_ago)
        assert new_level == 'Red-3'
        
        # At exactly 7 days (max_days boundary) - should progress, not expire
        seven_days_ago = (date.today() - timedelta(days=7)).isoformat()
        new_level, _ = LevelSystem.process_answer('Red-2', True, seven_days_ago)
        assert new_level == 'Red-3'
        
        # At 8 days (past max_days) - should expire to Red-1
        eight_days_ago = (date.today() - timedelta(days=8)).isoformat()
        new_level, _ = LevelSystem.process_answer('Red-2', True, eight_days_ago)
        assert new_level == 'Red-1'
    
    def test_process_answer_yellow_progression(self):
        """Test Yellow level progression (min_days=4)."""
        # Yellow-1 tested 5 days ago (min_days=4, eligible)
        five_days_ago = (date.today() - timedelta(days=5)).isoformat()
        new_level, _ = LevelSystem.process_answer('Yellow-1', True, five_days_ago)
        assert new_level == 'Yellow-2'
        
        # Yellow-1 tested 3 days ago (min_days=4, not eligible)
        three_days_ago = (date.today() - timedelta(days=3)).isoformat()
        new_level, _ = LevelSystem.process_answer('Yellow-1', True, three_days_ago)
        assert new_level == 'Yellow-1'
    
    def test_level_index_mapping(self):
        """Test that LEVEL_INDEX correctly maps level names to indices."""
        assert LevelSystem.LEVEL_INDEX['Red-1'] == 0
        assert LevelSystem.LEVEL_INDEX['Red-2'] == 1
        assert LevelSystem.LEVEL_INDEX['Red-3'] == 2
        assert LevelSystem.LEVEL_INDEX['Red-4'] == 3
        assert LevelSystem.LEVEL_INDEX['Yellow-1'] == 4
        assert LevelSystem.LEVEL_INDEX['Yellow-2'] == 5
        assert LevelSystem.LEVEL_INDEX['Green'] == 6
