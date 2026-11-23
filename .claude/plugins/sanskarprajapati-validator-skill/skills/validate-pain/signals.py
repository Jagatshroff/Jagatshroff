"""Fixed, published rules that spot money, workaround and intensity signals in a complaint.

Each rule is a regular expression. detect() returns, for every kind, the exact
words that matched (or None), so every signal can be shown and checked. Rules
lean towards missing a signal rather than inventing one: money is the heaviest
part of the Pain Index, so a false "would pay" costs more than a missed one.
"""

import re

MAX_SCAN = 5000  # only the first 5,000 characters are read; enough for any real complaint
_CURLY = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
_NOT_ATTENTION = r"(?!\s+(?:attention|off|back|respects?|homage|tribute|the\s+price\s+of)\b)"
_NOBODY = r"(?<!no one )(?<!nobody )(?<!noone )(?<!who )(?<!never )(?<!no one would )"
# Amounts never start mid-number, and their digits are bounded, so the scan stays linear.
_NUMBER = r"(?<![\w,.])\d{1,6}(?:[,.]\d{3}){0,3}(?:\.\d{1,2})?"
_AMOUNT = r"(?:[$€£₹]\s?" + _NUMBER[len(r"(?<![\w,.])"):] + r"|" + _NUMBER + r"\s?(?:usd|eur|gbp|inr|dollars?|bucks|euros?|rupees?)\b)"
_PERIOD = r"(?:\s?/\s?|\s(?:per|a|an|each)\s)(?:mo|month|yr|year|seat|user)\b"
_MONEY_OBJECT = r"(?:money|cash|\$|€|£|₹|\d)"

RULES = {
    "wtp": [
        r"\b(?:i'?d|i\s+would|we'?d|we\s+would|i'?ll|we'?ll)(?:\s+(?:happily|gladly|totally|definitely|easily))?"
        r"\s+(?:pay\b" + _NOT_ATTENTION + r"|spend\s+" + _MONEY_OBJECT + r")",
        r"\b(?:happy|willing|ready)\s+to\s+(?:pay\b" + _NOT_ATTENTION + r"|spend\s+" + _MONEY_OBJECT + r")",
        r"\btake\s+my\s+money\b",
        r"\b" + _NOBODY + r"would\s+(?:happily\s+|gladly\s+)?pay\b" + _NOT_ATTENTION,
    ],
    "spend": [
        _AMOUNT + r"(?:" + _PERIOD + r")?",
        r"\b(?:i'?m|we'?re|i\s+am|we\s+are)\s+paying\b",
        r"\b(?:i|we)\s+pay\s+for\b",
        r"\b(?:pro|paid|premium|annual|monthly)\s+(?:plan|tier|subscription)\b",
        r"\bsubscri(?:be|bed|ption)\b",
    ],
    "price": [
        r"\b(?:too|so|way\s+too|very|really|crazy)\s+(?:expensive|pricey|costly)\b",
        r"\boverpriced\b",
        r"\bcan'?t\s+afford\b",
        r"\bnot\s+worth\s+(?:the\s+(?:money|price|cost)|paying)\b",
        r"\bprice\s+(?:hike|increase|went\s+up)\b",
    ],
    "switch": [
        r"\bswitch(?:ed|ing)?\s+(?:from|away|over\s+to|back\s+to)\b",
        r"\bmigrat(?:ed|ing)\s+(?:away\s+)?(?:from|off)\b",  # "moved from" is left out: people move cities
        r"\bcancel+(?:ed|ing)?\s+(?:my|our|the)\s+(?:subscription|plan|account)\b",
        r"\b(?:asked\s+for|got|want(?:ed)?|requested)\s+(?:a\s+)?refund\b",
        r"\b(?:ditched|dropped|uninstalled|churned\s+from)\s+(?:it|them|the\s+app)\b",
    ],
    "workaround": [
        r"\b(?:spreadsheets?|google\s+sheets?|airtable|zapier|make\.com|ifttt|n8n)\b",
        r"\bexcel\b(?!\s+(?:at|in)\b)",
        r"(?-i:\bNotion\b)",
        r"\b(?:i|we)\s+(?:built|wrote|made|hacked|cobbled|rigged|set\s+up)\s+(?:together\s+)?"
        r"(?:my\s+own|our\s+own|(?:a|an|some)\s+(?:script|tool|bot|spreadsheet|system|workflow|zap|shortcut|automation))\b",
        r"\b(?:hacked|cobbled|duct[- ]taped)\s+together\b",
        r"\bscripts?\b(?!\s+(?:for|of)\s+(?:the|a|my)\s+(?:film|movie|show|play|video))",
        r"\bworkarounds?\b",
        r"\bmanually\b",
        r"\bcopy(?:ing)?[- ]?past(?:e|ing)\b",
        r"\bsticky\s+notes?\b",
        r"\bhired\s+(?:a|an|someone)\b",
        r"\bvirtual\s+assistant\b",
        r"\b(?:a|my|our|hired)\s+(?-i:VA)\b",
    ],
    "intense": [
        r"\b(?:hate|hated|nightmare|furious|infuriating|frustrat\w*|unusable|awful|terrible|horrible|disaster)\b",
        r"\b(?:drives?|driving)\s+me\s+(?:nuts|crazy|insane|mad|up\s+the\s+wall)\b",
        r"\b(?:sick|tired)\s+of\b|\bfed\s+up\b|\blosing\s+my\s+mind\b|\bpulling\s+my\s+hair\b",
        r"\b(?:fuck\w*|shit\w*|wtf)\b",
        r"!{2,}",
    ],
}
MONEY = ("wtp", "spend", "price", "switch")
KINDS = MONEY + ("workaround", "intense")

_COMPILED = {kind: [re.compile(p, re.I) for p in patterns] for kind, patterns in RULES.items()}
_CAPS_RUN = re.compile(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})+\b")
_ACRONYMS = {"API", "CRM", "HTML", "USA", "SMS", "UK", "US", "EU", "AI", "SaaS", "PDF", "URL", "CEO", "CTO",
             "FAQ", "ASAP", "IMAP", "SMTP", "JSON", "CSV", "IOS", "MCP", "LLM", "AWS", "VPN", "OK"}


def _shouting(text):
    """Two or more capitalised words in a row, with at least one real word of 4+ letters."""
    for match in _CAPS_RUN.finditer(text):
        words = [w for w in match.group(0).split() if w not in _ACRONYMS]
        if len(words) >= 2 and any(len(w) >= 4 for w in words):
            return match.group(0)
    return None


def _first(kind, text):
    for pattern in _COMPILED[kind]:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def detect(text):
    """{kind: matched words or None for each kind, "money": bool}."""
    text = (text or "")[:MAX_SCAN].translate(_CURLY)
    found = {kind: _first(kind, text) for kind in KINDS}
    if not found["intense"]:
        found["intense"] = _shouting(text)
    found["money"] = any(found[k] for k in MONEY)
    return found
