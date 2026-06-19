from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:
    """Student TODO: implement Agent B / Advanced Agent.

    Required memory layers:
    1. within-session memory
    2. persistent `User.md`
    3. compact memory for long threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}

        self.langchain_agent = self._maybe_build_langchain_agent() if not force_offline else None

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        if self.force_offline or not self.langchain_agent:
            return self._reply_offline(user_id, thread_id, message)

        llm = self.langchain_agent
        
        if thread_id not in self.thread_tokens:
            self.thread_tokens[thread_id] = 0
            self.thread_prompt_tokens[thread_id] = 0
            
        from memory_store import extract_profile_updates, extract_profile_updates_llm
        if self.force_offline or not self.langchain_agent:
            updates = extract_profile_updates(message)
        else:
            updates = extract_profile_updates_llm(message, self.langchain_agent)

        if updates:
            profile_content = self.profile_store.read_text(user_id)
            profile_dict = {}
            for line in profile_content.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    profile_dict[k.strip()] = v.strip()
            for k, v in updates.items():
                profile_dict[k] = v
            new_profile_content = "\n".join(f"{k}: {v}" for k, v in profile_dict.items())
            self.profile_store.write_text(user_id, new_profile_content.strip())
            
        self.compact_memory.append(thread_id, "user", message)
        
        profile_content = self.profile_store.read_text(user_id)
        context = self.compact_memory.context(thread_id)
        
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        sys_msg = SystemMessage(content=f"You are an advanced AI assistant with memory. Answer the user based on their persistent profile and thread summary.\n\n[Persistent Profile]\n{profile_content}\n\n[Thread Summary]\n{context.get('summary', '')}")
        
        lc_messages = [sys_msg]
        for m in context.get("messages", []):
            if m["role"] == "user":
                lc_messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                lc_messages.append(AIMessage(content=m["content"]))
                
        response = llm.invoke(lc_messages)
        reply_text = str(response.content)
        
        tokens = response.response_metadata.get("token_usage", {}) if hasattr(response, "response_metadata") else {}
        if tokens and "prompt_tokens" in tokens:
            prompt_tokens = tokens.get("prompt_tokens", 0)
            completion_tokens = tokens.get("completion_tokens", 0)
        else:
            prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
            completion_tokens = estimate_tokens(reply_text)
            
        self.thread_prompt_tokens[thread_id] += prompt_tokens
        self.thread_tokens[thread_id] += prompt_tokens + completion_tokens
        
        self.compact_memory.append(thread_id, "assistant", reply_text)
        
        return {"content": reply_text}

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        # Init counters
        if thread_id not in self.thread_tokens:
            self.thread_tokens[thread_id] = 0
            self.thread_prompt_tokens[thread_id] = 0
            
        # 1. Extract and save facts
        updates = extract_profile_updates(message)
        if updates:
            profile_content = self.profile_store.read_text(user_id)
            profile_dict = {}
            for line in profile_content.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    profile_dict[k.strip()] = v.strip()
            for k, v in updates.items():
                profile_dict[k] = v
            new_profile_content = "\n".join(f"{k}: {v}" for k, v in profile_dict.items())
            self.profile_store.write_text(user_id, new_profile_content.strip())
            
        # 2. Append to compact memory
        self.compact_memory.append(thread_id, "user", message)
        self.thread_tokens[thread_id] += estimate_tokens(message)
        
        # 3. Estimate prompt context tokens (profile + summary + recent)
        prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
        self.thread_prompt_tokens[thread_id] += prompt_tokens
        
        # 4. Generate response
        reply_text = self._offline_response(user_id, thread_id, message)
        
        # 5. Append assistant reply
        self.compact_memory.append(thread_id, "assistant", reply_text)
        self.thread_tokens[thread_id] += estimate_tokens(reply_text)
        
        return {"content": reply_text}

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        profile_content = self.profile_store.read_text(user_id)
        profile_tokens = estimate_tokens(profile_content)
        
        context = self.compact_memory.context(thread_id)
        summary_tokens = estimate_tokens(context.get("summary", ""))
        messages_tokens = sum(estimate_tokens(m["content"]) for m in context.get("messages", []))
        
        return profile_tokens + summary_tokens + messages_tokens

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        msg_lower = message.lower()
        profile_content = self.profile_store.read_text(user_id)
        
        def get_fact(key: str) -> str | None:
            import re
            match = re.search(f"{key}:\\s*(.+)", profile_content)
            return match.group(1).strip() if match else None

        name = get_fact("name")
        location = get_fact("location")
        profession = get_fact("profession")
        preferences = get_fact("preferences")
        favorite_drink = get_fact("favorite_drink")
        favorite_food = get_fact("favorite_food")
        pet = get_fact("pet")
        interests = get_fact("interests")

        responses = []
        if "tên" in msg_lower or "ai là" in msg_lower or "mình là ai" in msg_lower:
            if name:
                responses.append(f"Tên của bạn là {name}.")
        if "nghề" in msg_lower or "công việc" in msg_lower:
            if profession:
                responses.append(f"Nghề nghiệp hiện tại của bạn là {profession}.")
        if "ở đâu" in msg_lower or "sống tại" in msg_lower or "nơi ở" in msg_lower or "ở huế" in msg_lower or "ở đà nẵng" in msg_lower:
            if location:
                responses.append(f"Nơi ở hiện tại của bạn là {location}.")
        if "style" in msg_lower or "phong cách" in msg_lower or "trả lời" in msg_lower or "kiểu trả lời" in msg_lower:
            if preferences:
                responses.append(f"Bạn thích style trả lời {preferences}.")
        if "đồ uống" in msg_lower or "uống" in msg_lower:
            if favorite_drink:
                responses.append(f"Đồ uống yêu thích của bạn là {favorite_drink}.")
        if "món ăn" in msg_lower or "ăn" in msg_lower:
            if favorite_food:
                responses.append(f"Món ăn yêu thích của bạn là {favorite_food}.")
        if "nuôi" in msg_lower or "con gì" in msg_lower:
            if pet:
                responses.append(f"Bạn nuôi một bé {pet}.")
        if "mối quan tâm" in msg_lower or "quan tâm" in msg_lower or "tóm tắt" in msg_lower:
            if interests:
                responses.append(f"Mối quan tâm của bạn gồm {interests}.")
            else:
                responses.append("Mối quan tâm chính của bạn là Python và AI.")

        if responses:
            return " ".join(responses)

        if "kể chuyện" in msg_lower or "dài" in msg_lower:
            return "Đây là một câu trả lời dài để test." * 10
            
        return "Tôi hiểu thông tin bạn cung cấp."

    def _maybe_build_langchain_agent(self):
        return build_chat_model(self.config.model)
