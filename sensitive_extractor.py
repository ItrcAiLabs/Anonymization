import re
from typing import Dict, List, Union

class SensitiveInfoExtractor:
    """
    Extracts sensitive entities with enhanced precision and role detection
    """
    
    def __init__(self):
        # الگوهای بهبود یافته برای استخراج موجودیت‌ها
        self.patterns = {
            'PERSON': re.compile(
                r'(?:(?:خانم|آقای|سرکار\s+خانم|جناب\s+آقای)\s*)?'  # پیشوندهای اختیاری
                r'([\u0600-\u06FF]+\.\s*[\u0600-\u06FF]+(?:\.\s*[\u0600-\u06FF]+)?\s*\.?)',
                re.IGNORECASE
            ),
            'COURT_BRANCH': re.compile(
                r'شعبه\s*[۰-۹\d]+',
                re.IGNORECASE
            ),
            'JUDGE': re.compile(
                r'(?:رییس شعبه|دادرس|قاضی)\s*([\u0600-\u06FF]+\.\s*[\u0600-\u06FF]+\.?)',
                re.IGNORECASE
            ),
            'AMOUNT': re.compile(
                r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:ریال|تومان|دلار|یورو|درهم)',
                re.IGNORECASE
            ),
            'DATE': re.compile(
                r'\b(1[3-4]\d{2}\/\d{1,2}\/\d{1,2})\b'
            ),
            'LAW_REFERENCE': re.compile(
                r'(?:ماده|مواد)\s*(\d+)\s*(?:قانون|آیین‌نامه)\s*([\u0600-\u06FF\s]+)',
                re.IGNORECASE
            )
        }

        # الگوهای نقش‌ها با قابلیت تطابق دقیق‌تر
        self.role_patterns = {
            'خواهان': [
                r'خواهان(?!\s*:?\s*خوانده)[^:]*?({})',
                r'به\s+خواسته\s+{}',
                r'دادخواست\s+{}',
                r'اقای\s+{}'
            ],
            'خوانده': [
                r'به\s+طرفیت\s+{}',
                r'خوانده(?:ان)?\s*:?\s*{}',
                r'مقابل\s+{}',
                r'خانم\s+{}'
            ],
            'قاضی': [
                r'(رییس شعبه|دادرس|قاضی)\s*:?\s*{}'
            ]
        }
    
    def extract_entities(self, text: str) -> Dict[str, List[Union[str, Dict]]]:
        """
        استخراج موجودیت‌ها با نقش‌های دقیق
        """
        entities = {}
        
        # استخراج موجودیت‌های پایه
        for name, pattern in self.patterns.items():
            matches = pattern.findall(text)
            if matches:
                clean_matches = []
                for match in matches:
                    if isinstance(match, tuple):
                        clean_matches.extend([m.strip() for m in match if m.strip()])
                    else:
                        clean_matches.append(match.strip())
                entities[name] = list(set(clean_matches))
        
        # استخراج اشخاص با نقش
        persons_with_roles = []
        for person in entities.get('PERSON', []):
            role = self.determine_role(person, text)
            persons_with_roles.append({
                'name': person,
                'role': role
            })
        
        entities['PERSON'] = persons_with_roles
        
        # استخراج اطلاعات شعبه و قاضی
        entities['COURT_INFO'] = {
            'branch': entities.get('COURT_BRANCH', ['نامشخص'])[0],
            'judge': entities.get('JUDGE', ['نامشخص'])[0]
        }
        
        return entities
    
    def determine_role(self, person: str, text: str) -> str:
        """
        تعیین نقش شخص با دقت بالا
        """
        # جایگزینی الگو با نام شخص
        for role, patterns in self.role_patterns.items():
            for pattern in patterns:
                specific_pattern = pattern.format(re.escape(person))
                if re.search(specific_pattern, text, re.IGNORECASE):
                    return role
        
        # استنتاج نقش بر اساس زمینه متن
        if 'خواهان' in text.split(person)[0]:
            return 'خواهان'
        if 'خوانده' in text.split(person)[0]:
            return 'خوانده'
        if 'قاضی' in text.split(person)[0] or 'رییس' in text.split(person)[0]:
            return 'قاضی'
        
        return 'نامشخص'