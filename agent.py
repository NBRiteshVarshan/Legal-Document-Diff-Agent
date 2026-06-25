from concurrent.futures import ThreadPoolExecutor, as_completed
from parser import extract_text, split_clauses
from llm import compare_clause

def run_diff(file_a, file_b) -> dict:
    """Orchestrates structural checking and concurrent local LLM semantic comparisons."""
    bytes_a = file_a.getvalue()
    bytes_b = file_b.getvalue()
    
    text_a = extract_text(file_a.name, bytes_a)
    text_b = extract_text(file_b.name, bytes_b)

    doc_a = split_clauses(text_a)
    doc_b = split_clauses(text_b)

    keys_a = set(doc_a.keys())
    keys_b = set(doc_b.keys())

    report = {
        "added": [],
        "removed": [],
        "modified": {}
    }

    # 1. Structural Changes Tracking
    for k in sorted(keys_a - keys_b):
        report["removed"].append({"clause": k, "content": doc_a[k]})

    for k in sorted(keys_b - keys_a):
        report["added"].append({"clause": k, "content": doc_b[k]})

    # 2. Parallelized Local Semantic Diff Engine via Thread Pools
    shared_keys = sorted(keys_a & keys_b)
    mismatched_tasks = []

    for k in shared_keys:
        if doc_a[k].strip() != doc_b[k].strip():
            mismatched_tasks.append((k, doc_a[k], doc_b[k]))

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(compare_clause, task[0], task[1], task[2]): task[0] 
            for task in mismatched_tasks
        }
        
        for future in as_completed(futures):
            clause_key = futures[future]
            try:
                analysis_result = future.result()
                
                # --- TERMINAL TERMINAL DEBUG SYSTEM LOGS ---
                print(f"\n[DEBUG LOG] LLM Evaluation Processed for: {clause_key}")
                print(f" -> Change Type: {analysis_result.get('change_type')}")
                print(f" -> Summary: {analysis_result.get('summary')}")
                print(f" -> Risk Level: {analysis_result.get('risk')}")
                # --------------------------------------------
                
                raw_risk = analysis_result.get("risk", "Low")
                analysis_result["risk"] = raw_risk.strip().capitalize() if raw_risk else "None"
                
                # Render to UI if any actual variance exists
                if analysis_result.get("change_type") != "No Material Change":
                    report["modified"][clause_key] = analysis_result
            except Exception as e:
                print(f"[ERROR] Thread Worker crashed for {clause_key}: {e}")
                report["modified"][clause_key] = {
                    "change_type": "Wording Modified",
                    "summary": f"Worker thread crashed: {str(e)}",
                    "risk": "High"
                }

    return report