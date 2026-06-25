import time
import json
import numpy as np
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import ollama
from utils import generate_clause_id

class LegalClauseMatcher:
    """Match legal clauses using embeddings and LLM verification"""
    
    def __init__(self, embedding_model: str = 'nomic-ai/nomic-embed-text-v1.5'):
        """Initialize the matcher with embedding model"""
        print(f"Loading embedding model: {embedding_model}")
        self.embedder = SentenceTransformer(embedding_model)
        self.cache = {}  # Cache for embeddings
        self.llm_model = 'qwen2.5:7b'
        
    def get_embeddings(self, clauses: List[Dict], doc_name: str) -> np.ndarray:
        """Get embeddings for clauses with caching"""
        embeddings = []
        for clause in clauses:
            clause_id = generate_clause_id(clause['text'], doc_name)
            
            # Check cache
            if clause_id in self.cache:
                embeddings.append(self.cache[clause_id])
            else:
                # Generate new embedding
                embedding = self.embedder.encode(clause['text'])
                self.cache[clause_id] = embedding
                embeddings.append(embedding)
        
        return np.array(embeddings)
    
    def find_candidates(self, query_embedding: np.ndarray, 
                       target_embeddings: np.ndarray, 
                       k: int = 3) -> List[int]:
        """Find top-k candidate matches using cosine similarity"""
        similarities = cosine_similarity([query_embedding], target_embeddings)[0]
        top_indices = np.argsort(similarities)[-k:][::-1]
        return top_indices.tolist(), similarities[top_indices].tolist()
    
    def compare_with_llm(self, clause_a: str, clause_b: str) -> Dict[str, Any]:
        """Compare two clauses using LLM"""
        try:
            prompt = """You are comparing two legal clauses. They match if:
1. They create the same obligation (who must do what)
2. They grant the same right or power
3. They have the same conditions and exceptions
4. The consequences of violation are the same

They DO NOT match if:
- One has additional conditions the other lacks
- The scope is different (e.g., "worldwide" vs "US only")
- The obligation is stronger/weaker (e.g., "shall" vs "may")

Clause A: "{clause_a}"
Clause B: "{clause_b}"

Respond in JSON format with these keys:
- "match": true/false (boolean)
- "confidence": 0-1 (float)
- "key_differences": ["difference1", "difference2"] (list)
- "reason": "brief explanation" (string)"""
            
            response = ollama.chat(
                model=self.llm_model,
                messages=[
                    {'role': 'system', 'content': 'You are a legal text comparison expert. Respond only in JSON format.'},
                    {'role': 'user', 'content': prompt.format(clause_a=clause_a[:500], clause_b=clause_b[:500])}
                ]
            )
            
            # Parse JSON response
            result = json.loads(response['message']['content'])
            return result
            
        except Exception as e:
            print(f"LLM comparison error: {str(e)}")
            # Fallback to similarity-based decision
            return {
                'match': False,
                'confidence': 0.5,
                'key_differences': ['LLM comparison failed'],
                'reason': 'Fallback to embedding similarity'
            }
    
    def match_documents(self, doc1_clauses: List[Dict], doc2_clauses: List[Dict],
                       doc1_name: str = "Document 1", doc2_name: str = "Document 2",
                       similarity_threshold: float = 0.3) -> Dict[str, Any]:
        """Match clauses between two documents"""
        start_time = time.time()
        
        # Generate embeddings
        print("Generating embeddings...")
        doc1_embeddings = self.get_embeddings(doc1_clauses, doc1_name)
        doc2_embeddings = self.get_embeddings(doc2_clauses, doc2_name)
        
        # Track matches
        matched_doc2 = [False] * len(doc2_clauses)
        only_in_doc1 = []
        matching_details = []
        
        print("Comparing clauses...")
        total_clauses = len(doc1_clauses)
        
        for i, clause1 in enumerate(doc1_clauses):
            # Find top candidates in doc2
            candidates, similarities = self.find_candidates(
                doc1_embeddings[i], doc2_embeddings, k=3
            )
            
            found_match = False
            best_match = None
            
            # Check each candidate with LLM
            for j, (candidate_idx, similarity) in enumerate(zip(candidates, similarities)):
                if similarity < similarity_threshold:
                    continue
                    
                clause2 = doc2_clauses[candidate_idx]
                llm_result = self.compare_with_llm(clause1['text'], clause2['text'])
                
                if llm_result.get('match', False) and llm_result.get('confidence', 0) > 0.7:
                    found_match = True
                    best_match = {
                        'clause_idx': candidate_idx,
                        'similarity': similarity,
                        'confidence': llm_result.get('confidence', 0),
                        'reason': llm_result.get('reason', 'LLM match'),
                        'key_differences': llm_result.get('key_differences', [])
                    }
                    matched_doc2[candidate_idx] = True
                    break
            
            # Update progress (for UI)
            print(f"Progress: {i+1}/{total_clauses} clauses processed")
            
            # Record match status
            matching_details.append({
                'clause_number': clause1.get('number', str(i+1)),
                'clause_text': clause1['text'],
                'found_match': found_match,
                'best_match': best_match
            })
            
            if not found_match:
                # Find closest match for reporting
                closest_idx = np.argmax(cosine_similarity([doc1_embeddings[i]], doc2_embeddings)[0])
                closest_sim = cosine_similarity([doc1_embeddings[i]], doc2_embeddings)[0][closest_idx]
                
                only_in_doc1.append({
                    'text': clause1['text'],
                    'number': clause1.get('number', str(i+1)),
                    'closest_match': doc2_clauses[closest_idx]['text'],
                    'similarity': closest_sim,
                    'metadata': clause1.get('metadata', {})
                })
        
        # Find clauses only in doc2
        only_in_doc2 = []
        for j, (clause2, is_matched) in enumerate(zip(doc2_clauses, matched_doc2)):
            if not is_matched:
                # Find closest match in doc1
                closest_idx = np.argmax(cosine_similarity([doc2_embeddings[j]], doc1_embeddings)[0])
                closest_sim = cosine_similarity([doc2_embeddings[j]], doc1_embeddings)[0][closest_idx]
                
                only_in_doc2.append({
                    'text': clause2['text'],
                    'number': clause2.get('number', str(j+1)),
                    'closest_match': doc1_clauses[closest_idx]['text'],
                    'similarity': closest_sim,
                    'metadata': clause2.get('metadata', {})
                })
        
        # Calculate final statistics
        processing_time = time.time() - start_time
        
        return {
            'only_in_doc1': only_in_doc1,
            'only_in_doc2': only_in_doc2,
            'matching_details': matching_details,
            'total_doc1': len(doc1_clauses),
            'total_doc2': len(doc2_clauses),
            'matching_count': sum(1 for m in matching_details if m['found_match']),
            'processing_time': processing_time,
            'similarity_threshold': similarity_threshold
        }