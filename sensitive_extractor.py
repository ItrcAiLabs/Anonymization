import re
from typing import Dict, List, Union
from hf_ner import hf_extract
from ner_pipeline import spacy_extract

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
    _BASE_PATTERNS = {
        "PERSON": re.compile(
            r"(?:خانم|آقای|سرکار\s+خانم|جناب\s+آقای|قاضی|رییس\s+شعبه|دادرس)?\s*((?:[\u0600-\u06FF]\.){1,4}\s*[\u0600-\u06FF]\.?)",
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

    _ROLE_WINDOW = 40
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

        for key, pat in self._BASE_PATTERNS.items():
            if key == "PERSON":
                filtered = []
                for m in pat.finditer(txt):
                    name = m.group(1).strip(" .،")
                    start = m.start(1)
                    end = m.end(1)

                    if len(name) <= 1:
                        continue

                    # بررسی اینکه نام بخشی از کلمه نباشد
                    before = txt[start - 1] if start > 0 else " "
                    after = txt[end] if end < len(txt) else " "
                    if re.match(r"[\u0600-\u06FF]", before) or re.match(r"[\u0600-\u06FF]", after):
                        continue

                    # بررسی وجود واژه‌های نقش در نزدیکی
                    window_start = max(0, start - self._ROLE_WINDOW)
                    window_end = min(len(txt), end + self._ROLE_WINDOW)
                    context = txt[window_start:window_end]

                    if any(kw in context for kws in self._ROLE_MAP.values() for kw in kws):
                        filtered.append(name)

                ents[key] = filtered
            else:
                ents[key] = [m.group(0).strip(" .،") for m in pat.finditer(txt)]

        # HF NER
        if self.use_hf:
            for ent in hf_extract(txt):
                lbl = ent["label"]
                if lbl in ("PER", "Person"):
                    ents["PERSON"].append(ent["text"])
                elif lbl in ("LOC", "FAC", "GPE"):
                    ents["PLACE"].append(ent["text"])

        # spaCy NER
        if self.use_spacy:
            for ent in spacy_extract(txt):
                lbl = ent["label"]
                if lbl in ("PER", "PERSON"):
                    ents["PERSON"].append(ent["text"])
                elif lbl in ("LOC", "GPE", "FAC"):
                    ents["PLACE"].append(ent["text"])

        # Dedup
        for k in ents:
            seen = set()
            uniq = []
            for v in ents[k]:
                if v not in seen:
                    seen.add(v)
                    uniq.append(v)
            ents[k] = uniq

        # Assign roles
        ents["PERSON"] = [
            {"name": p, "role": self._infer_role(txt, p)}
            for p in ents["PERSON"]
        ]

        ents["COURT_INFO"] = {
            "branch": (
                "REDACTED" if "*" in ents["COURT_BRANCH"] else
                (ents["COURT_BRANCH"][0] if ents["COURT_BRANCH"] else "نامشخص")
            ),
            "judges": ents.get("JUDGE", ["نامشخص"])
        }

        return ents

    def _infer_role(self, text: str, person: str) -> str:
        idx = text.find(person)
        if idx < 0:
            return "نامشخص"
        start = max(0, idx - self._ROLE_WINDOW)
        end = min(len(text), idx + self._ROLE_WINDOW)
        snippet = text[start:end]
        for role, kws in self._ROLE_MAP.items():
            if any(kw in snippet for kw in kws):
                return role
        return "نامشخص"
