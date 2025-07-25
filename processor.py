import re
import pandas as pd
from bs4 import BeautifulSoup
import html
from sensitive_extractor import SensitiveInfoExtractor

class CourtCaseProcessor:
    """
    Reads CSV HTML lines, extracts text, parses fields, and applies extractor.
    """
    def __init__(self, input_path: str):
        self.input_path = input_path
        self.df_raw = pd.DataFrame()
        self.df_processed = pd.DataFrame()
        self.extractor = SensitiveInfoExtractor()

    def read_and_extract(self):
        rows = []
        with open(self.input_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(',', 4)
                if len(parts) == 5:
                    rec_id, *_, html_blob = parts
                    soup = BeautifulSoup(html.unescape(html_blob), 'html.parser')
                    body = soup.find('body')
                    text = body.get_text(' ', strip=True) if body else ''
                    rows.append({'id': rec_id, 'text': text})
        self.df_raw = pd.DataFrame(rows)
        print(f"Extracted {len(self.df_raw)} records.")

    def parse_cases(self) -> pd.DataFrame:
        parsed = []
        patterns = {
            'case_no':    re.compile(r'شماره\s+پرونده\s*[:؛]?\s*([\w؀-ۿ\/\-*]+)'),
            'executive_no': re.compile(r'اجراییه\s+شماره\s*[:؛]?\s*([\w؀-ۿ\/\-*]+)'),
            'archive_no': re.compile(r'بایگانی\s*[:؛]?\s*([\d*]+)')
        }
        for _, row in self.df_raw.iterrows():
            text = row['text']
            start = text.find('رای دادگاه')
            ruling = text[start:] if start != -1 else text
            ents = self.extractor.extract_entities(ruling)
            case_info = {}
            for k, pat in patterns.items():
                m = pat.search(text)
                case_info[k] = m.group(1).strip() if m else 'نامشخص'
            parsed.append({
                'id': row['id'],
                'case_info': case_info,
                'court_info': ents.get('COURT_INFO', {}),
                'persons': ents.get('PERSON', []),
                'dates': ents.get('DATE', []),
                'amounts': ents.get('AMOUNT', []),
                'law_references': ents.get('LAW_REFERENCE', []),
                'places': ents.get('PLACE', []),
                'addresses': ents.get('ADDRESS', []),
                'redacted': ents.get('REDACTED', []),
                'ruling_text': ruling
            })
        self.df_processed = pd.DataFrame(parsed)
        print(f"Parsed {len(self.df_processed)} cases.")
        return self.df_processed
