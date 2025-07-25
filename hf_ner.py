from functools import lru_cache
from typing import List, Dict
import os

@lru_cache(1)
def _load_pipeline():
    """
    Lazy-load a HuggingFace token-classification pipeline for ParsBERT.
    Disable by setting DISABLE_HF_NER env var.
    """
    if os.getenv("DISABLE_HF_NER"):
        return None
    from transformers import pipeline
    return pipeline(
        task="token-classification",
        model="HooshvareLab/bert-base-parsbert-ner-uncased",
        aggregation_strategy="simple"
    )


def hf_extract(text: str) -> List[Dict]:
    """
    Run HF NER and return list of {text, label, start} items.
    """
    nlp = _load_pipeline()
    if not nlp:
        return []
    out = []
    for ent in nlp(text):
        out.append({
            "text": ent["word"],
            "label": ent["entity_group"],  # PER, LOC, ORG, etc.
            "start": ent["start"]
        })
    return out