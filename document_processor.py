import re
from typing import List, Dict, Any
from pypdf import PdfReader
from docx import Document
import io

class ClauseExtractor:
    """Extract clauses from legal documents in various formats"""
    
    def __init__(self):
        self.clause_patterns = [
            # Numbered patterns
            r'(?P<number>\d+\.?\d*)\s*[—–-]?\s*(?P<content>.*?)(?=\s*(?:\d+\.?\d*)\s*[—–-]|$)',
            r'(?:Article|Section|Clause|Paragraph)\s+(?P<number>\d+\.?\d*)\s*[—–-]?\s*(?P<content>.*?)(?=\s*(?:Article|Section|Clause|Paragraph)\s+|$)',
            # Roman numerals
            r'(?P<number>[IVXLCDM]+\.)\s*(?P<content>.*?)(?=\s*(?:[IVXLCDM]+\.)|$)',
            # Letter patterns
            r'(?P<number>[A-Z]\.)\s*(?P<content>.*?)(?=\s*(?:[A-Z]\.)|$)',
        ]
    
    def extract_from_pdf(self, file_content: bytes) -> List[Dict[str, Any]]:
        """Extract text from PDF file"""
        try:
            pdf = PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
            return self.extract_clauses(text)
        except Exception as e:
            raise Exception(f"Failed to extract from PDF: {str(e)}")
    
    def extract_from_docx(self, file_content: bytes) -> List[Dict[str, Any]]:
        """Extract text from DOCX file"""
        try:
            doc = Document(io.BytesIO(file_content))
            text = "\n".join([para.text for para in doc.paragraphs])
            return self.extract_clauses(text)
        except Exception as e:
            raise Exception(f"Failed to extract from DOCX: {str(e)}")
    
    def extract_clauses(self, text: str) -> List[Dict[str, Any]]:
        """Extract clauses from raw text using multiple strategies"""
        clauses = []
        text = self._clean_text(text)
        
        # Strategy 1: Try numbered patterns
        for pattern in self.clause_patterns:
            matches = list(re.finditer(pattern, text, re.DOTALL | re.MULTILINE))
            if matches:
                for match in matches:
                    clause = {
                        'number': match.group('number').strip(),
                        'text': match.group('content').strip(),
                        'metadata': {
                            'has_conditions': self._check_conditions(match.group('content')),
                            'has_exceptions': self._check_exceptions(match.group('content')),
                            'word_count': len(match.group('content').split())
                        }
                    }
                    clauses.append(clause)
                break
        
        # Strategy 2: If no numbered clauses, split by paragraphs
        if not clauses:
            paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
            for idx, para in enumerate(paragraphs):
                clause = {
                    'number': str(idx + 1),
                    'text': para,
                    'metadata': {
                        'has_conditions': self._check_conditions(para),
                        'has_exceptions': self._check_exceptions(para),
                        'word_count': len(para.split())
                    }
                }
                clauses.append(clause)
        
        # Clean up clause texts
        for clause in clauses:
            clause['text'] = self._clean_clause_text(clause['text'])
        
        return clauses
    
    def _clean_text(self, text: str) -> str:
        """Clean the raw text before extraction"""
        # Remove page numbers, headers, footers
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        text = re.sub(r'Page \d+ of \d+', '', text)
        # Normalize whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text
    
    def _clean_clause_text(self, text: str) -> str:
        """Clean individual clause text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Clean up bullet points
        text = re.sub(r'[•·▪]', '-', text)
        return text.strip()
    
    def _check_conditions(self, text: str) -> bool:
        """Check if clause contains conditional language"""
        condition_words = ['if', 'provided', 'unless', 'subject to', 'when', 'where']
        return any(word in text.lower() for word in condition_words)
    
    def _check_exceptions(self, text: str) -> bool:
        """Check if clause contains exceptions"""
        exception_words = ['except', 'excluding', 'other than', 'notwithstanding', 'unless']
        return any(word in text.lower() for word in exception_words)

def get_document_summary(clauses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Get summary statistics for extracted clauses"""
    if not clauses:
        return {'total': 0, 'avg_length': 0, 'has_conditions': 0, 'has_exceptions': 0}
    
    total = len(clauses)
    avg_length = sum(c['metadata']['word_count'] for c in clauses) / total if total > 0 else 0
    has_conditions = sum(1 for c in clauses if c['metadata'].get('has_conditions', False))
    has_exceptions = sum(1 for c in clauses if c['metadata'].get('has_exceptions', False))
    
    return {
        'total': total,
        'avg_length': round(avg_length, 2),
        'has_conditions': has_conditions,
        'has_exceptions': has_exceptions
    }