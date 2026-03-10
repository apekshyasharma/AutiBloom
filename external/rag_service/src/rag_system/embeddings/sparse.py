import re
from rank_bm25 import BM25Okapi

def bm25_tokenize(text: str):
    # simple tokenization: alnum words
    return re.findall(r"[a-zA-Z0-9]+", text.lower())

def build_bm25(chunks):
    tokenized = [bm25_tokenize(c["text"]) for c in chunks]
    return BM25Okapi(tokenized)
