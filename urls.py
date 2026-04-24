"""
Compatibility shim.

The canonical Django URLConf is `helpdesk.urls`.
This file exists only to avoid breaking older imports or scripts.
"""

from helpdesk.urls import *  # noqa: F401,F403
