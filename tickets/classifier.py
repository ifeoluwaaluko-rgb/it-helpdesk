"""
Rule-based classifier with 3-level categorization.
Swap classify() with OpenAI call when ready — interface is identical.
"""

RULES = [
    {
        'keywords': ['password', 'reset', 'forgot', 'locked out', "can't login", 'cant login', 'account locked'],
        'category': 'password', 'subcategory': 'Account Access', 'item': 'Password Reset',
        'priority': 'medium', 'level': 'associate', 'sla_hours': 4,
    },
    {
        'keywords': ['printer', 'print', 'scanner', 'scanning', 'photocopier'],
        'category': 'printer', 'subcategory': 'Printing', 'item': 'Printer Issue',
        'priority': 'low', 'level': 'associate', 'sla_hours': 8,
    },
    {
        'keywords': ['internet', 'wifi', 'wi-fi', 'network', 'vpn', 'connection', 'slow connection', 'no internet', 'bandwidth'],
        'category': 'network', 'subcategory': 'Connectivity', 'item': 'Network Issue',
        'priority': 'high', 'level': 'consultant', 'sla_hours': 4,
    },
    {
        'keywords': ['email', 'outlook', 'mail', 'inbox', 'calendar', 'exchange'],
        'category': 'email', 'subcategory': 'Email Client', 'item': 'Email Issue',
        'priority': 'medium', 'level': 'consultant', 'sla_hours': 8,
    },
    {
        'keywords': ['teams', 'microsoft teams', 'zoom', 'meet', 'google meet', 'meeting', 'video call', 'collaboration'],
        'category': 'software', 'subcategory': 'Collaboration Tools', 'item': 'Video Conferencing',
        'priority': 'medium', 'level': 'associate', 'sla_hours': 8,
    },
    {
        'keywords': ['access', 'permission', 'share', 'folder', 'drive', 'unauthorized', 'denied'],
        'category': 'access', 'subcategory': 'Permissions', 'item': 'Access Request',
        'priority': 'medium', 'level': 'consultant', 'sla_hours': 8,
    },
    {
        'keywords': ['laptop', 'computer', 'pc', 'screen', 'monitor', 'keyboard', 'mouse', 'hardware', 'broken', 'not turning on', 'speaker', 'battery'],
        'category': 'hardware', 'subcategory': 'End User Device', 'item': 'Hardware Fault',
        'priority': 'high', 'level': 'consultant', 'sla_hours': 8,
    },
    {
        'keywords': ['install', 'software', 'application', 'app', 'update', 'crash', 'error', 'not working', 'license'],
        'category': 'software', 'subcategory': 'Applications', 'item': 'Software Issue',
        'priority': 'medium', 'level': 'associate', 'sla_hours': 24,
    },
    {
        'keywords': ['new staff', 'onboarding', 'new employee', 'new hire', 'joining', 'new user'],
        'category': 'onboarding', 'subcategory': 'New Staff Setup', 'item': 'Onboarding Request',
        'priority': 'high', 'level': 'senior', 'sla_hours': 24,
    },
    {
        'keywords': ['server', 'database', 'system down', 'outage', 'breach', 'security', 'hacked', 'ransomware'],
        'category': 'network', 'subcategory': 'Infrastructure', 'item': 'Critical Outage',
        'priority': 'critical', 'level': 'manager', 'sla_hours': 1,
    },
]

DEFAULT = {
    'category': 'other', 'subcategory': 'General', 'item': '',
    'priority': 'medium', 'level': 'associate', 'sla_hours': 24,
}


def classify(title: str, body: str) -> dict:
    """
    Classify a ticket. Returns dict with category, subcategory, item,
    priority, level, sla_hours.
    AI SWAP POINT: replace this function body with an OpenAI call.
    """
    text = (title + ' ' + body).lower()
    for rule in RULES:
        if any(kw in text for kw in rule['keywords']):
            return {k: rule[k] for k in ('category','subcategory','item','priority','level','sla_hours')}
    return DEFAULT.copy()


# 3-level category tree for UI dropdowns
CATEGORY_TREE = {
    'software': {
        'label': 'Software',
        'subcategories': {
            'Collaboration Tools': ['Microsoft Teams', 'Zoom', 'Google Meet', 'Slack', 'Other'],
            'Productivity Suite': ['Microsoft Office', 'Google Workspace', 'Other'],
            'Applications': ['ERP', 'CRM', 'Accounting Software', 'Other'],
            'Operating System': ['Windows', 'macOS', 'Linux', 'Other'],
            'Other': ['Other'],
        }
    },
    'hardware': {
        'label': 'Hardware',
        'subcategories': {
            'End User Device': ['Laptop', 'Desktop', 'Monitor', 'Keyboard/Mouse', 'Other'],
            'Peripherals': ['Headset', 'Webcam', 'USB Hub', 'Docking Station', 'Other'],
            'Mobile Device': ['Phone', 'Tablet', 'Other'],
            'Other': ['Other'],
        }
    },
    'network': {
        'label': 'Network',
        'subcategories': {
            'Connectivity': ['WiFi', 'Ethernet', 'VPN', 'Internet', 'Other'],
            'Infrastructure': ['Server', 'Switch', 'Router', 'Firewall', 'Other'],
            'Other': ['Other'],
        }
    },
    'email': {
        'label': 'Email',
        'subcategories': {
            'Email Client': ['Outlook', 'Gmail', 'Apple Mail', 'Other'],
            'Calendar': ['Outlook Calendar', 'Google Calendar', 'Other'],
            'Distribution List': ['Add to List', 'Remove from List', 'Other'],
            'Other': ['Other'],
        }
    },
    'access': {
        'label': 'Access / Permissions',
        'subcategories': {
            'Permissions': ['Shared Drive', 'File/Folder', 'Application', 'Other'],
            'Account': ['New Account', 'Disable Account', 'Role Change', 'Other'],
            'Other': ['Other'],
        }
    },
    'password': {
        'label': 'Password Reset',
        'subcategories': {
            'Account Access': ['Windows Login', 'Email', 'Application', 'Other'],
            'Other': ['Other'],
        }
    },
    'printer': {
        'label': 'Printer',
        'subcategories': {
            'Printing': ['Paper Jam', 'Offline', 'Quality Issue', 'Other'],
            'Scanning': ['Scanner Offline', 'Driver Issue', 'Other'],
            'Other': ['Other'],
        }
    },
    'onboarding': {
        'label': 'Onboarding',
        'subcategories': {
            'New Staff Setup': ['Laptop Setup', 'Email Creation', 'System Access', 'Full Onboarding', 'Other'],
            'Offboarding': ['Account Disable', 'Equipment Return', 'Other'],
            'Other': ['Other'],
        }
    },
    'other': {
        'label': 'Other',
        'subcategories': {
            'General': ['General Request', 'Other'],
        }
    },
}
