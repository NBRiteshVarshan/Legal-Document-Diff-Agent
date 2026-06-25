import difflib
from concurrent.futures import ThreadPoolExecutor, as_completed
from parser import extract_text, split_clauses
from llm import compare_clause

def find_best_match(text_a: str, doc_b_dict: dict) -> tuple:
    """Finds the most structurally similar clause in Document B using fuzzy text matching."""
    best_match_key = None
    best_score = 0.0

    for key_b, text_b in doc_b_dict.items():
        # difflib compares text similarity on a scale of 0.0 to 1.0
        score = difflib.SequenceMatcher(None, text_a, text_b).ratio()
        if score > best_score:
            best_score = score
            best_match_key = key_b

    return best_match_key, best_score

def run_diff(file_a, file_b) -> dict:
    """Orchestrates fuzzy structural alignment and concurrent LLM semantic comparisons."""
    bytes_a = file_a.getvalue()
    bytes_b = file_b.getvalue()
    
    text_a = extract_text(file_a.name, bytes_a)
    text_b = extract_text(file_b.name, bytes_b)

    doc_a = split_clauses(text_a)
    doc_b = split_clauses(text_b)

    report = {
        "added": [],
        "removed": [],
        "moved": [],  # NEW: Tracks clauses that changed section numbers
        "modified": {}
    }

    matched_b_keys = set()
    mismatched_tasks = []

    # 1. Map Document A to Document B based on content similarity, NOT headers
    for key_a, text_a in doc_a.items():
        best_key_b, score = find_best_match(text_a, doc_b)

        # Threshold for considering it the "same" clause (55% similar)
        if best_key_b and score > 0.55:
            matched_b_keys.add(best_key_b)
            text_b = doc_b[best_key_b]

            # Track if the header/numbering changed
            if key_a != best_key_b:
                report["moved"].append({"from": key_a, "to": best_key_b})

            # Check if the text actually changed (ignoring exact matches)
            if text_a.strip() != text_b.strip():
                # Pass the context of the move to the LLM UI
                identifier = f"{key_a} (Moved to {best_key_b})" if key_a != best_key_b else key_a
                mismatched_tasks.append((identifier, text_a, text_b))
        else:
            # If no match > 55% similarity is found, it was completely removed
            report["removed"].append({"clause": key_a, "content": text_a})

    # 2. Identify Added Clauses (Anything in B that wasn't matched to A)
    for key_b, text_b in doc_b.items():
        if key_b not in matched_b_keys:
            report["added"].append({"clause": key_b, "content": text_b})

    # 3. Parallelized Local Semantic Diff Engine via Thread Pools
    if mismatched_tasks:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(compare_clause, task[0], task[1], task[2]): task[0] 
                for task in mismatched_tasks
            }
            
            for future in as_completed(futures):
                clause_key = futures[future]
                try:
                    analysis_result = future.result()
                    
                    # Sanitize schema literals
                    raw_risk = analysis_result.get("risk", "Low")
                    analysis_result["risk"] = raw_risk.strip().capitalize() if raw_risk else "None"
                    
                    if analysis_result.get("change_type") != "No Material Change":
                        report["modified"][clause_key] = analysis_result
                except Exception as e:
                    print(f"[ERROR] Worker failed for {clause_key}: {e}")
                    report["modified"][clause_key] = {
                        "change_type": "Wording Modified",
                        "summary": f"Worker thread crashed: {str(e)}",
                        "risk": "High"
                    }

    return report