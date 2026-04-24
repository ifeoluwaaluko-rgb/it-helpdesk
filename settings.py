"""
Compatibility shim.

The canonical Django settings module is `helpdesk.settings`.
This file exists only to avoid breaking any older imports or scripts.
"""

from helpdesk.settings import *  # noqa: F401,F403
