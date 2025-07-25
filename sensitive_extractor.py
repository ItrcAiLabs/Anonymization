import re
from typing import Dict, List, Union
from hf_ner import hf_extract
from ner_pipeline import spacy_extract

# Digit normalization map
_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789"
)


def _normalize(text: str) -> str:
    """
    Normalize digits and remove invisible/zero-width chars.
    """
    text = text.translate(_DIGIT_MAP)
    text = re.sub(r"[\u200c\u200d\u2060]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


class SensitiveInfoExtractor:
    """
    Extract entities via Regex, HF NER, and SpaCy NER.
    """
    # Base regex patterns
    _BASE_PATTERNS = {
        "PERSON": re.compile(
            r"(?:خانم|آقای|سرکار\s+خانم|جناب\s+آقای)?\s*((?:[\u0600-\u06FF]\.){1,4}\s*[\u0600-\u06FF]\.?)",
            re.I
        ),
        "COURT_BRANCH": re.compile(r"(شعبه)\s*(\d+|[*])", re.I),
        "JUDGE": re.compile(
            r"(?:رییس شعبه|دادرس|قاضی)\s*((?:[\u0600-\u06FF]\.){1,4}\s*[\u0600-\u06FF]\.?)",
            re.I
        ),
        "AMOUNT": re.compile(
            r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(ریال|تومان|دلار|یورو|درهم)",
            re.I
        ),
        "DATE": re.compile(r"\b(1[34]\d{2}/\d{1,2}/\d{1,2})\b"),
        "LAW_REFERENCE": re.compile(
            r"(?:ماده|مواد)\s*(\d+)\s*قانون\s*([\u0600-\u06FF\s]+)",
            re.I
        ),
        "REDACTED": re.compile(r"([\u0600-\u06FF\s]+?)\s*\*\b"),
        # Address and place patterns
        "ADDRESS": re.compile(
            r"(?:(?:استان|شهر(?:ستان)?|منطقه|خیابان|بلوار|کوچه|میدان|"
            r"پلاک|طبقه|واحد|کدپستی)\s*[\u0600-\u06FF0-9\-,.\s]*){2,}",
            re.I
        ),
        "PLACE": re.compile(
            r"(?:دانشگاه|مرکز|دادگاه|محکمه|سازمان|دفتر|بانک|"
            r"کلانتری|بازداشتگاه|بیمارستان)\s+[\u0600-\u06FF\s]{2,30}",
            re.I
        ),
    }

    # Role inference settings
    _ROLE_WINDOW = 35
    _ROLE_MAP = {
        "خواهان": ["خواهان", "مدعی", "دادخواست"],
        "خوانده": ["خوانده", "طرفیت", "مدعی‌علیه"],
        "قاضی":   ["قاضی", "رییس شعبه", "دادرس"],
    }

    def __init__(self, use_hf: bool = True, use_spacy: bool = True):
        self.use_hf = use_hf
        self.use_spacy = use_spacy

    def extract_entities(self, raw_text: str) -> Dict[str, List[Union[str, Dict]]]:
        txt = _normalize(raw_text)
        ents: Dict[str, List] = {k: [] for k in self._BASE_PATTERNS}

        # 1) Regex layer
        for key, pat in self._BASE_PATTERNS.items():
            ents[key] = [m.group(0).strip(" .،") for m in pat.finditer(txt)]

        # 2) HF NER
        if self.use_hf:
            for ent in hf_extract(txt):
                lbl = ent["label"]
                if lbl in ("PER", "Person"):
                    ents["PERSON"].append(ent["text"])
                elif lbl in ("LOC", "FAC", "GPE"):
                    ents["PLACE"].append(ent["text"])

        # 3) spaCy NER
        if self.use_spacy:
            for ent in spacy_extract(txt):
                lbl = ent["label"]
                if lbl in ("PER", "PERSON"):
                    ents["PERSON"].append(ent["text"])
                elif lbl in ("LOC", "GPE", "FAC"):
                    ents["PLACE"].append(ent["text"])

        # Deduplicate
        for k in ents:
            seen = set()
            uniq = []
            for v in ents[k]:
                if v not in seen:
                    seen.add(v)
                    uniq.append(v)
            ents[k] = uniq

        # Role assignment
        persons_with_roles = []
        for p in ents["PERSON"]:
            persons_with_roles.append({"name": p, "role": self._infer_role(txt, p)})
        ents["PERSON"] = persons_with_roles

        # Court info
        branch = (
            "REDACTED" if "*" in ents["COURT_BRANCH"] else
            (ents["COURT_BRANCH"][0] if ents["COURT_BRANCH"] else "نامشخص")
        )
        ents["COURT_INFO"] = {"branch": branch, "judges": ents.get("JUDGE", ["نامشخص"]) }
        return ents

    def _infer_role(self, text: str, person: str) -> str:
        idx = text.find(person)
        if idx < 0:
            return "نامشخص"
        start = max(0, idx - self._ROLE_WINDOW)
        end   = min(len(text), idx + self._ROLE_WINDOW)
        snippet = text[start:end]
        for role, kws in self._ROLE_MAP.items():
            if any(kw in snippet for kw in kws):
                return role
        return "نامشخص"