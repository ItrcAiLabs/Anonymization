"""
Module: processor.py
Defines CourtCaseProcessor to read HTML, parse fields, and apply
SensitiveInfoExtractor to ruling text, outputting persons, addresses, and dates.
"""
import re
import pandas as pd
from bs4 import BeautifulSoup
import html
import json
from sensitive_extractor import SensitiveInfoExtractor

class CourtCaseProcessor:
    """
    Pipeline to:
    1. Read input file containing CSV lines with HTML body.
    2. Extract plain text.
    3. Parse legal fields (case number, parties, ruling).
    4. Extract persons, addresses, dates via SensitiveInfoExtractor.
    """

    def __init__(self, input_path: str):
        self.input_path = input_path
        self.df_raw = pd.DataFrame()
        self.df_processed = pd.DataFrame()
        self.extractor = SensitiveInfoExtractor()

    def read_and_extract(self):
        """
        Reads each line, splits by first 4 commas, parses HTML,
        and stores id and clean text.
        """
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

    def parse_cases(self):
            """
            استخراج اطلاعات با جزئیات کامل و یکپارچه
            """
            parsed = []
            patterns = {
                'case_no': re.compile(r'شماره\s+پرونده\s*[:؛]?\s*([\w\u0600-\u06FF\/\-]+)'),
                'executive_no': re.compile(r'اجراییه\s+شماره\s*[:؛]?\s*([\w\u0600-\u06FF\/\-]+)'),
                'archive_no': re.compile(r'بایگانی\s*[:؛]?\s*(\d+)')
            }

            for _, row in self.df_raw.iterrows():
                text = row['text']
                
                # استخراج اطلاعات پایه
                start = text.find('رای دادگاه')
                ruling = text[start:] if start != -1 else text
                
                # استخراج اطلاعات حساس
                ents = self.extractor.extract_entities(ruling)
                
                # استخراج اطلاعات پرونده
                case_info = {}
                for field, pattern in patterns.items():
                    match = pattern.search(text)
                    case_info[field] = match.group(1).strip() if match else 'نامشخص'

                parsed.append({
                    'id': row['id'],
                    'case_info': {
                        'case_number': case_info.get('case_no', 'نامشخص'),
                        'executive_number': case_info.get('executive_no', 'نامشخص'),
                        'archive_number': case_info.get('archive_no', 'نامشخص')
                    },
                    'court_info': ents.get('COURT_INFO', {}),
                    'persons': ents.get('PERSON', []),
                    'dates': ents.get('DATE', []),
                    'amounts': ents.get('AMOUNT', []),
                    'law_references': ents.get('LAW_REFERENCE', []),
                    'ruling_text': ruling
                })

            self.df_processed = pd.DataFrame(parsed)
            print(f"Parsed {len(self.df_processed)} cases.")
            return self.df_processed