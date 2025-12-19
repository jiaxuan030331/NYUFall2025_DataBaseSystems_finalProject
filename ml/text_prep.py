# ml/text_prep.py
from __future__ import annotations

import re

def normalize_text(s: str) -> str:
    # very light cleaning to keep explainability
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s
