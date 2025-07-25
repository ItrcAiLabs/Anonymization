import os
from functools import lru_cache
from typing import List, Dict

_DISABLE = bool(int(os.getenv("DISABLE_SPACY_NER", "0")))

@lru_cache(1)
def _load_spacy_ner():
    """
    Load SpaCy model for Persian NER (parsBERT-based or fallback).
    """
    if _DISABLE:
        return None
    import spacy
    try:
        # Attempt to load a registered ParsBERT NER SpaCy model
        return spacy.load("parsbert_ner_spacy")
    except Exception:
        # Fallback to blank Persian model
        return spacy.blank("fa")


def spacy_extract(text: str) -> List[Dict]:
    """
    Extract entities using SpaCy pipeline; returns list of {text, label, start}.
    """
    nlp = _load_spacy_ner()
    if not nlp:
        return []
    doc = nlp(text)
    return [
        {"text": ent.text.strip(), "label": ent.label_, "start": ent.start_char}
        for ent in doc.ents
    ]