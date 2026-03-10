import re

def clean_text(text: str) -> str: #for having clean chunk boundaries.
    """
    Normalizes PDF text for better chunking + retrieval.
    - removes soft hyphens
    - fixes broken hyphenated line words
    - normalizes whitespace
    """
    t = text.replace("\u00ad", "")  # soft hyphen
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)  # "atten-\n tion" -> "attention"
    t = re.sub(r"\s+", " ", t).strip()
    return t

