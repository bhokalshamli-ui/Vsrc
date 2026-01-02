import re
from typing import Dict, Any

def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return bool(pattern.match(url))

def normalize_source(source: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize source format"""
    if isinstance(source, str):
        return {"file": source, "label": "Auto", "type": "mp4"}
    return source
