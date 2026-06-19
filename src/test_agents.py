from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


from memory_store import UserProfileStore, CompactMemoryManager

def make_config(tmp_path: Path):
    config = load_config(tmp_path)
    config.state_dir = tmp_path / "state"
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.compact_threshold_tokens = 50
    config.compact_keep_messages = 2
    return config


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    store = UserProfileStore(tmp_path)
    uid = "test-user"
    
    # Write
    store.write_text(uid, "name: Alice")
    assert store.read_text(uid) == "name: Alice"
    
    # Edit
    changed = store.edit_text(uid, "Alice", "Bob")
    assert changed is True
    assert store.read_text(uid) == "name: Bob"
    
    # Size
    assert store.file_size(uid) > 0


def test_compact_trigger(tmp_path: Path) -> None:
    manager = CompactMemoryManager(threshold_tokens=20, keep_messages=1)
    
    # 20 tokens per message ~ 80 characters
    long_msg = "A" * 80
    manager.append("t1", "user", long_msg)
    assert manager.compaction_count("t1") == 0
    
    manager.append("t1", "assistant", long_msg)
    manager.append("t1", "user", long_msg)
    
    assert manager.compaction_count("t1") > 0
    ctx = manager.context("t1")
    assert "summary" in ctx
    assert len(ctx["messages"]) == 1


def test_cross_session_recall(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    base = BaselineAgent(config, force_offline=True)
    adv = AdvancedAgent(config, force_offline=True)
    
    msg = "Tên tôi là John Doe"
    base.reply("u1", "t1", msg)
    adv.reply("u1", "t1", msg)
    
    # New thread
    q = "Tôi tên là gì?"
    base_ans = base.reply("u1", "t2", q)["content"]
    adv_ans = adv.reply("u1", "t2", q)["content"]
    
    assert "John Doe" not in base_ans
    assert "John Doe" in adv_ans


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    base = BaselineAgent(config, force_offline=True)
    adv = AdvancedAgent(config, force_offline=True)
    
    # Generate 50 messages that trigger compaction in adv but not base
    for i in range(50):
        msg = f"Kể chuyện {i}"
        base.reply("u2", "t_long", msg)
        adv.reply("u2", "t_long", msg)
        
    base_load = base.prompt_token_usage("t_long")
    adv_load = adv.prompt_token_usage("t_long")
    
    # Advanced should be significantly lower because it compacted
    assert adv_load < base_load
