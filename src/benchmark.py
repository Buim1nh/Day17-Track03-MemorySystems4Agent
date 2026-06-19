from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tabulate import tabulate

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def recall_points(answer: str, expected: list[str]) -> float:
    if not expected:
        return 1.0
        
    answer_lower = answer.lower()
    matches = 0
    for exp in expected:
        if exp.lower() in answer_lower:
            matches += 1
            
    return matches / len(expected)


def heuristic_quality(answer: str, expected: list[str]) -> float:
    # A simple length-based and recall-based heuristic for offline mode
    score = recall_points(answer, expected)
    if score == 0.0 and expected:
        return 0.2
    return max(0.5, score)


def run_agent_benchmark(agent_name: str, agent, conversations: list[dict[str, Any]], config) -> BenchmarkRow:
    total_recall = 0.0
    total_quality = 0.0
    recall_questions_count = 0
    
    for conv in conversations:
        user_id = conv["user_id"]
        thread_id = conv["id"]
        turns = conv["turns"]
        
        for text in turns:
            agent.reply(user_id, thread_id, text)
            
        if "recall_questions" in conv:
            test_thread_id = f"{thread_id}_test"
            for test in conv["recall_questions"]:
                response = agent.reply(user_id, test_thread_id, test["question"])
                answer = response["content"]
                
                expected = test.get("expected_contains", [])
                recall_score = recall_points(answer, expected)
                quality_score = heuristic_quality(answer, expected)
                
                total_recall += recall_score
                total_quality += quality_score
                recall_questions_count += 1

    # Aggregate metrics across all threads
    total_agent_tokens = sum(agent.token_usage(conv["id"]) for conv in conversations)
    total_prompt_tokens = sum(agent.prompt_token_usage(conv["id"]) for conv in conversations)
    
    # If there are test threads, also sum their tokens
    for conv in conversations:
        if "recall_questions" in conv:
            test_thread_id = f"{conv['id']}_test"
            try:
                total_agent_tokens += agent.token_usage(test_thread_id)
                total_prompt_tokens += agent.prompt_token_usage(test_thread_id)
            except Exception:
                pass
    
    avg_recall = total_recall / recall_questions_count if recall_questions_count > 0 else 0.0
    avg_quality = total_quality / recall_questions_count if recall_questions_count > 0 else 0.0
    
    total_compactions = sum(agent.compaction_count(conv["id"]) for conv in conversations)
    
    # Total memory growth (simplification: get size for all users)
    users = set(c["user_id"] for c in conversations)
    memory_growth = sum(agent.memory_file_size(u) if hasattr(agent, "memory_file_size") else 0 for u in users)

    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=total_agent_tokens,
        prompt_tokens_processed=total_prompt_tokens,
        recall_score=avg_recall,
        response_quality=avg_quality,
        memory_growth_bytes=memory_growth,
        compactions=total_compactions
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    headers = [
        "Agent", "Agent tokens only", "Prompt tokens processed", 
        "Cross-session recall", "Response quality", 
        "Memory growth (bytes)", "Compactions"
    ]
    table_data = [
        [
            r.agent_name, 
            r.agent_tokens_only, 
            r.prompt_tokens_processed, 
            f"{r.recall_score:.2f}", 
            f"{r.response_quality:.2f}", 
            r.memory_growth_bytes, 
            r.compactions
        ] 
        for r in rows
    ]
    return tabulate(table_data, headers=headers, tablefmt="pipe")


def main() -> None:
    import sys
    import argparse

    # Force UTF-8 encoding on stdout for Windows systems
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Run Memory Agent Benchmarks.")
    parser.add_argument("--offline", action="store_true", help="Run benchmark in offline mode.")
    args = parser.parse_args()
    force_offline = args.offline

    config = load_config(Path(__file__).resolve().parent.parent)

    print(f"Initializing agents (offline={force_offline})...")
    baseline = BaselineAgent(config, force_offline=force_offline)
    advanced = AdvancedAgent(config, force_offline=force_offline)

    # Clean state dir profiles
    import shutil
    profiles_dir = config.state_dir / "profiles"
    if profiles_dir.exists():
        shutil.rmtree(profiles_dir)
    
    # Run Standard Benchmark
    print("\nRunning Standard Benchmark...")
    conv_path = config.data_dir / "conversations.json"
    if conv_path.exists():
        standard_data = load_conversations(conv_path)
        res_base = run_agent_benchmark("Baseline", baseline, standard_data, config)
        res_adv = run_agent_benchmark("Advanced", advanced, standard_data, config)
        print(format_rows([res_base, res_adv]))
    else:
        print(f"File not found: {conv_path}")

    # Reset agents for next benchmark
    baseline = BaselineAgent(config, force_offline=force_offline)
    advanced = AdvancedAgent(config, force_offline=force_offline)
    if profiles_dir.exists():
        shutil.rmtree(profiles_dir)

    # Run Long-Context Stress Benchmark
    print("\nRunning Long-Context Stress Benchmark...")
    stress_path = config.data_dir / "advanced_long_context.json"
    if stress_path.exists():
        stress_data = load_conversations(stress_path)
        res_base_stress = run_agent_benchmark("Baseline", baseline, stress_data, config)
        res_adv_stress = run_agent_benchmark("Advanced", advanced, stress_data, config)
        print(format_rows([res_base_stress, res_adv_stress]))
    else:
        print(f"File not found: {stress_path}")


if __name__ == "__main__":
    main()
