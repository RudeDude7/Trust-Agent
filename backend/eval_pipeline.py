import sys
import argparse
import pandas as pd

# Create a dummy module to satisfy the import for ragas 0.1.7 compatibility with langchain_community 0.4.x
import types
_vx = types.ModuleType("langchain_community.chat_models.vertexai")
class ChatVertexAI:
    pass
_vx.ChatVertexAI = ChatVertexAI
sys.modules["langchain_community.chat_models.vertexai"] = _vx
_cm = types.ModuleType("langchain_community.chat_models")
_cm.ChatVertexAI = ChatVertexAI
sys.modules["langchain_community.chat_models"] = _cm

# We need to import evaluating elements from Ragas
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, context_precision, context_recall, answer_relevancy
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

def main():
    parser = argparse.ArgumentParser(description="Run Tiered RAG Evaluation.")
    parser.add_argument("--tier", choices=["smoke", "nightly"], default="smoke", help="The evaluation tier to run.")
    args = parser.parse_args()

    print(f"Initializing LLM and Embedding models for {args.tier.upper()} Evaluation...")
    # Initialize the LLM evaluator (Gemini) and the Embedding model
    try:
        from ragas.llms.base import LangchainLLMWrapper
        
        _base_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            temperature=0.0, 
            max_output_tokens=8192, 
            max_retries=5
        )
        
        # Ragas 0.2.x strictly checks for finish_reason == 'stop', but Gemini returns 'STOP'.
        # We supply a custom is_finished_parser that defaults to True for Gemini.
        eval_llm = LangchainLLMWrapper(
            langchain_llm=_base_llm,
            is_finished_parser=lambda _: True
        )
        
        eval_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    except Exception as e:
        print(f"Failed to initialize models. Check your API keys. Error: {e}")
        sys.exit(1)

    # Tiered Datasets
    if args.tier == "smoke":
        print("Loading Tier 1: Smoke Test Dataset (Fast, 1-2 items)...")
        data = {
            "question": ["Does TikTok have a data encryption policy?"],
            "answer": ["TikTok encrypts all data at rest using AES-256."],
            "contexts": [["The vendor TikTok ensures that all user data is protected and encrypted at rest using the advanced encryption standard (AES-256)."]],
            "ground_truth": ["TikTok encrypts data using AES-256."]
        }
        dataset = Dataset.from_dict(data)
    else:
        print("Loading Tier 2: Nightly Run Dataset from backend/tests/nightly_eval_dataset.jsonl...")
        try:
            # We load the JSONL file, which natively supports lists in the 'contexts' column
            df = pd.read_json("tests/nightly_eval_dataset.jsonl", lines=True)
            dataset = Dataset.from_pandas(df)
            print(f"Loaded {len(dataset)} robust test cases for thorough evaluation.")
        except Exception as e:
            print(f"Failed to load the nightly dataset: {e}")
            sys.exit(1)

    # Select metrics based on tier
    if args.tier == "smoke":
        # Smoke: generation metrics only (fast, 1-2 items, no ground_truth needed for these)
        metrics = [faithfulness, answer_relevancy]
        print(f"Running SMOKE metrics: Faithfulness, Answer Relevancy")
    else:
        # Nightly: full retrieval + generation metrics
        metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
        print(f"Running FULL metrics: Faithfulness, Answer Relevancy, Context Precision, Context Recall")

    from ragas.run_config import RunConfig
    run_config = RunConfig(timeout=300, max_workers=1)

    try:
        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=eval_llm,
            embeddings=eval_embeddings,
            run_config=run_config
        )
    except Exception as e:
        print(f"Ragas evaluation failed: {e}")
        sys.exit(1)

    print(f"\nEvaluation Results (Raw):\n{result}")
    
    # Print the full dataframe to debug Faithfulness scoring
    try:
        import pandas as pd
        df = result.to_pandas()
        print("\n=== DEBUG: Full Evaluation DataFrame ===")
        for record in df.to_dict('records'):
            print(record)
        print("========================================\n")
    except Exception as e:
        print(f"Failed to print debug dataframe: {e}")
        
    # Extract the scores safely
    def safe_get(res, key):
        try:
            val = res[key]
            import math
            # Ragas 0.2.x returns a list of scores for each row
            if isinstance(val, list):
                valid_scores = [v for v in val if not math.isnan(v)]
                if not valid_scores:
                    return 0.0
                return sum(valid_scores) / len(valid_scores)
            # Fallback if it returns a single float
            return 0.0 if math.isnan(val) else val
        except Exception:
            return 0.0

    f_score = safe_get(result, "faithfulness")
    ar_score = safe_get(result, "answer_relevancy")

    print("\n" + "=" * 50)
    print("  RAGAS BENCHMARK SCORES")
    print("=" * 50)
    print(f"  Faithfulness (Generation):      {f_score:.2f}")
    print(f"  Answer Relevancy (Generation):  {ar_score:.2f}")

    scores = [f_score, ar_score]

    if args.tier == "nightly":
        cp_score = safe_get(result, "context_precision")
        cr_score = safe_get(result, "context_recall")
        print(f"  Context Precision (Retrieval):  {cp_score:.2f}")
        print(f"  Context Recall (Retrieval):     {cr_score:.2f}")
        scores.extend([cp_score, cr_score])

    avg_score = sum(scores) / len(scores)
    print(f"\n  Pipeline Average:               {avg_score:.2f}")
    print("=" * 50 + "\n")

    # Quality Gate
    gate_passed = True
    if f_score < 0.80:
        print(f"FAIL: Faithfulness {f_score:.2f} is below 0.80 threshold.")
        gate_passed = False
    if ar_score < 0.80:
        print(f"FAIL: Answer Relevancy {ar_score:.2f} is below 0.80 threshold.")
        gate_passed = False

    if args.tier == "nightly":
        if cp_score < 0.70:
            print(f"FAIL: Context Precision {cp_score:.2f} is below 0.70 threshold.")
            gate_passed = False
        if cr_score < 0.70:
            print(f"FAIL: Context Recall {cr_score:.2f} is below 0.70 threshold.")
            gate_passed = False

    if not gate_passed:
        print("\nQuality Gate FAILED.")
        sys.exit(1)

    print("Quality Gate PASSED.")
    sys.exit(0)

if __name__ == "__main__":
    main()
