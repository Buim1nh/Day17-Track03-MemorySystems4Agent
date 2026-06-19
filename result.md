# Walkthrough: Memory Systems for AI Agent (Day 17 Lab)

This document provides a summary of the implementation, benchmark results, and a trade-off analysis of the memory layers for Day 17.

## Key Changes Implemented

1. **Robust Output Encoding**: Configured `sys.stdout` to enforce UTF-8 output in `src/benchmark.py`, preventing crashes (`UnicodeEncodeError`) when running benchmarks containing Vietnamese text on Windows.
2. **Benchmark CLI Option**: Added a `--offline` CLI argument to `src/benchmark.py` for immediate testing and verification without API latency or server downtime dependencies.
3. **Structured Override logic**: Replaced simple regex line-by-line replacement in `AdvancedAgent` with a dictionary-based parse-update-format pattern for `User.md`. This ensures facts are neatly overwritten without keeping duplicates or outdated entries.
4. **Resilient Profile Extraction**:
   - Upgraded `extract_profile_updates` with robust keyword negations (e.g. ignoring location/profession entries containing "không", "đừng", "cũ", etc.), filtering questions (filtering words like "gì", "ai", "đâu"), and filtering out long sentences.
   - Implemented `extract_profile_updates_llm` for online mode to extract facts and resolve contradictions using LLM prompting with a fallback to the rule-based extractor.
   - Added structured entity support for `interests`, `pet`, `favorite_drink`, and `favorite_food`.

---

## Benchmark Results (Offline Mode)

### 1. Standard Benchmark (`data/conversations.json`)
Consists of 10 conversations of a single user (`dungct`) spanning career changes (Backend to MLOps) and location updates (Đà Nẵng to Huế), with cross-session recall questions.

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline** | 2,594 | 12,456 | 0.04 | 0.22 | 0 | 0 |
| **Advanced** | 2,931 | 17,840 | **1.00** | **1.00** | 194 | 0 |

### 2. Long-Context Stress Benchmark (`data/advanced_long_context.json`)
A stress test consisting of 17 conversational turns and 3 recall questions, containing news items, technical analogies, location correction, and distractors.

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline** | 3,144 | 25,566 | 0.00 | 0.20 | 0 | 0 |
| **Advanced** | 2,705 | **15,491** | **1.00** | **1.00** | 117 | 1 |

---

## Detailed Analysis and Findings

### 1. Cross-Session Recall
* **Baseline Agent**: Achieved close to **0.00** recall. Because it relies exclusively on short-term/in-thread memory (thread-bound SessionState), it completely forgets name, location, job, and preferences when queried in a new thread.
* **Advanced Agent**: Achieved a perfect **1.00** recall score. It uses the persistent profile store (`User.md`) to read historical facts and inject them into the system prompt for the new thread, allowing it to seamlessly recall user traits.

### 2. Compaction Advantage (Long Threads)
* In standard, short threads, the Advanced agent consumes slightly more prompt tokens (17.8k vs 12.4k) due to carrying the persistent profile and thread summaries in the system prompt.
* Under the **Long-Context Stress Benchmark**, the Baseline agent's prompt load ballooned to **25,566 tokens** because it carries the full raw message history.
* The Advanced Agent triggered **Compact Memory** (threshold of 2000 tokens), compressing older messages into a summary and keeping only the 2 most recent messages in full. This restricted the prompt load to **15,491 tokens** — a **39.4% reduction in prompt token processing costs** while maintaining **1.00 recall**!

### 3. Memory File Growth and Risks
* Storing profile updates permanently increases the size of `User.md` (194 bytes in standard, 117 bytes in stress).
* **Risks**:
  1. *Unchecked Expansion*: If a dictionary-based override isn't used, key duplication could make the profile file infinitely grow.
  2. *Noise Accumulation*: Incorrectly extracting questions or side jokes (e.g. "product manager... chỉ là đùa") can pollute the memory file, causing the LLM to recall false facts.
  3. *Conflict Handling*: Users often correct their facts ("không còn làm backend nữa"). A naïve system will keep both facts, whereas a dictionary-based system overwrites old keys cleanly.

---

## Verification Logs

All tests in [test_agents.py](file:///e:/CongViec/AI20K/Day17-Track03-MemorySystems4Agent/src/test_agents.py) successfully pass:
```
platform win32 -- Python 3.12.10, pytest-9.0.3
collected 4 items

src\test_agents.py ....                                                  [100%]

============================== 4 passed in 0.05s ==============================
```
