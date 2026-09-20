"""
Learner configuration: which Google Spreadsheet and which password belong to whom.

The configuration is INI text with one ``[user:<Name>]`` section per learner:

    [user:Anna]
    spreadsheet_id = 1AbC...
    password = secret

It is read from ``configuration.ini`` next to this module. If the
``VOCAB_APP_CONFIG`` environment variable is set it holds the same INI text and
replaces the file, which is how the test-suite keeps the real learners out.

Passwords are meant to come from ``LOGIN_PASSWORD_<NAME>`` environment
variables, so the committed ini only carries names and spreadsheet IDs; a
``password`` key in a section is honoured as the fallback.
"""

import os
from collections import OrderedDict
from configparser import ConfigParser
from typing import Dict, Optional

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = 'configuration.ini'
CONFIG_ENV = 'VOCAB_APP_CONFIG'
USER_SECTION_PREFIX = 'user:'


class LearnerConfig:
    """The settings of one ``[user:<Name>]`` section."""
    def __init__(self, name: str, spreadsheet_id: str, password: Optional[str]):
        self.name = name
        self.spreadsheet_id = spreadsheet_id
        self.password = password  # None means: no password login for this learner (guest only)

    def __repr__(self) -> str:
        return f"LearnerConfig('{self.name}', spreadsheet_id='{self.spreadsheet_id}')"


def load_config() -> ConfigParser:
    """Parse the INI source described in the module docstring."""
    # No interpolation: passwords may legitimately contain '%'
    config = ConfigParser(interpolation=None)
    inline = os.environ.get(CONFIG_ENV)
    if inline:
        config.read_string(inline)
    else:
        config.read(os.path.join(CONFIG_DIR, CONFIG_FILE), encoding='utf-8')
    return config


def load_learners(config: ConfigParser = None) -> Dict[str, LearnerConfig]:
    """
    Build the learner registry from the ``[user:<Name>]`` sections, in file order.

    :raises ValueError: for a section without a name or spreadsheet_id
    :raises RuntimeError: when no learner is configured at all
    """
    if config is None:
        config = load_config()
    learners: Dict[str, LearnerConfig] = OrderedDict()
    for section in config.sections():
        if not section.startswith(USER_SECTION_PREFIX):
            continue
        name = section[len(USER_SECTION_PREFIX):].strip()
        spreadsheet_id = config.get(section, 'spreadsheet_id', fallback='').strip()
        if not name or not spreadsheet_id:
            raise ValueError(f"Section [{section}] needs a name and a spreadsheet_id")
        password = (os.environ.get(f'LOGIN_PASSWORD_{name.upper()}')
                    or config.get(section, 'password', fallback=None))
        learners[name] = LearnerConfig(name, spreadsheet_id, password)
    if not learners:
        raise RuntimeError(
            f"No learner configured. Add a [user:<Name>] section to {CONFIG_FILE} "
            f"or set the {CONFIG_ENV} environment variable.")
    return learners


LEARNERS: Dict[str, LearnerConfig] = load_learners()
