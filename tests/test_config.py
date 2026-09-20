"""Tests for config.py - the learner registry read from INI text."""

import pytest
from configparser import ConfigParser

import config
from config import load_config, load_learners, LearnerConfig, CONFIG_ENV


def _parse(ini_text: str) -> ConfigParser:
    parser = ConfigParser(interpolation=None)
    parser.read_string(ini_text)
    return parser


class TestLoadLearners:
    """Test turning [user:<Name>] sections into LearnerConfig objects."""

    def test_reads_sections_in_order(self):
        learners = load_learners(_parse("""
            [user:Zed]
            spreadsheet_id = zed-id
            password = zed_pw
            [general]
            unrelated = yes
            [user:Amy]
            spreadsheet_id = amy-id
        """))

        assert list(learners) == ['Zed', 'Amy']
        assert learners['Zed'].spreadsheet_id == 'zed-id'
        assert learners['Zed'].password == 'zed_pw'
        assert learners['Amy'].password is None

    def test_strips_whitespace_around_name(self):
        learners = load_learners(_parse("[user: Amy ]\nspreadsheet_id = amy-id\n"))
        assert list(learners) == ['Amy']

    def test_password_may_contain_percent(self):
        learners = load_learners(_parse("[user:Amy]\nspreadsheet_id = amy-id\npassword = 100%sure\n"))
        assert learners['Amy'].password == '100%sure'

    def test_env_password_overrides_ini(self, monkeypatch):
        monkeypatch.setenv('LOGIN_PASSWORD_AMY', 'from_env')
        learners = load_learners(_parse("[user:Amy]\nspreadsheet_id = amy-id\npassword = from_ini\n"))
        assert learners['Amy'].password == 'from_env'

    def test_missing_spreadsheet_id_raises(self):
        with pytest.raises(ValueError, match="spreadsheet_id"):
            load_learners(_parse("[user:Amy]\npassword = x\n"))

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            load_learners(_parse("[user:]\nspreadsheet_id = x\n"))

    def test_no_learners_raises(self):
        with pytest.raises(RuntimeError, match="No learner configured"):
            load_learners(_parse("[general]\nfoo = bar\n"))


class TestLoadConfig:
    """Test where the INI text comes from."""

    def test_env_var_is_sole_source(self, monkeypatch):
        monkeypatch.setenv(CONFIG_ENV, "[user:EnvOnly]\nspreadsheet_id = env-id\n")
        learners = load_learners(load_config())
        # The committed configuration.ini must not show up
        assert list(learners) == ['EnvOnly']

    def test_file_is_read_when_env_unset(self, monkeypatch, tmp_path):
        monkeypatch.delenv(CONFIG_ENV, raising=False)
        monkeypatch.setattr(config, 'CONFIG_DIR', str(tmp_path))
        (tmp_path / 'configuration.ini').write_text("[user:Amy]\nspreadsheet_id = amy-id\n[user:Ben]\nspreadsheet_id = ben-id\n")

        learners = load_learners(load_config())

        assert list(learners) == ['Amy', 'Ben']
        assert learners['Amy'].spreadsheet_id == 'amy-id'
        assert learners['Amy'].password is None

    def test_committed_file_has_learners_without_passwords(self, monkeypatch):
        """The real configuration.ini parses, names learners and carries no secrets."""
        monkeypatch.delenv(CONFIG_ENV, raising=False)
        sections = [s for s in load_config().sections() if s.startswith('user:')]
        for section in sections:
            monkeypatch.delenv('LOGIN_PASSWORD_' + section[len('user:'):].strip().upper(), raising=False)

        learners = load_learners(load_config())

        assert len(learners) >= 1
        assert all(learner.password is None for learner in learners.values())

    def test_missing_file_is_tolerated(self, monkeypatch, tmp_path):
        monkeypatch.delenv(CONFIG_ENV, raising=False)
        monkeypatch.setattr(config, 'CONFIG_DIR', str(tmp_path))
        with pytest.raises(RuntimeError, match="No learner configured"):
            load_learners(load_config())


class TestLearnerConfig:
    def test_repr_hides_password(self):
        learner = LearnerConfig('Amy', 'amy-id', 'secret')
        assert 'secret' not in repr(learner)
        assert 'Amy' in repr(learner)
