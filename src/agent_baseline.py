from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    """Student TODO: implement Agent A.

    Requirements:
    - Within-session memory only
    - No persistent `User.md`
    - Should forget long-term facts across new threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}
        self.langchain_agent = self._maybe_build_langchain_agent() if not force_offline else None

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        if self.force_offline or not self.langchain_agent:
            return self._reply_offline(thread_id, message)
            
        from langchain_core.messages import HumanMessage, AIMessage
        
        if thread_id not in self.sessions:
            self.sessions[thread_id] = SessionState()
        session = self.sessions[thread_id]
        
        session.messages.append({"role": "user", "content": message})
        
        lc_messages = []
        for m in session.messages:
            if m["role"] == "user":
                lc_messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                lc_messages.append(AIMessage(content=m["content"]))
                
        response = self.langchain_agent.invoke(lc_messages)
        reply_text = str(response.content)
        
        # calculate token usage
        tokens = response.response_metadata.get("token_usage", {}) if hasattr(response, "response_metadata") else {}
        if tokens and "prompt_tokens" in tokens:
            prompt_tokens = tokens.get("prompt_tokens", 0)
            completion_tokens = tokens.get("completion_tokens", 0)
        else:
            prompt_tokens = sum(estimate_tokens(m["content"]) for m in session.messages)
            completion_tokens = estimate_tokens(reply_text)
            
        session.token_usage += prompt_tokens + completion_tokens
        session.prompt_tokens_processed += prompt_tokens
        
        session.messages.append({"role": "assistant", "content": reply_text})
        return {"content": reply_text}

    def token_usage(self, thread_id: str) -> int:
        session = self.sessions.get(thread_id)
        return session.token_usage if session else 0

    def prompt_token_usage(self, thread_id: str) -> int:
        session = self.sessions.get(thread_id)
        return session.prompt_tokens_processed if session else 0

    def compaction_count(self, thread_id: str) -> int:
        # Baseline has no compact memory.
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        if thread_id not in self.sessions:
            self.sessions[thread_id] = SessionState()
        
        session = self.sessions[thread_id]
        
        # User message
        session.messages.append({"role": "user", "content": message})
        user_tokens = estimate_tokens(message)
        session.token_usage += user_tokens
        
        # Prompt load: sum of all messages in thread BEFORE we reply + system prompt roughly
        prompt_tokens = sum(estimate_tokens(m["content"]) for m in session.messages)
        session.prompt_tokens_processed += prompt_tokens
        
        # Deterministic offline response based purely on in-thread context
        context_text = " ".join(m["content"].lower() for m in session.messages)
        
        if "tên" in message.lower() and "gì" in message.lower():
            import re
            name_match = re.search(r"(?:tên(?: là| mình là| tôi là)|tôi là)\s+([A-ZÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴa-záàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ\s]+)", context_text)
            if name_match:
                reply_text = f"Tên của bạn là {name_match.group(1).strip()}"
            else:
                reply_text = "Tôi không biết tên của bạn"
        elif "nghề" in message.lower() and "gì" in message.lower():
            import re
            prof_match = re.search(r"(?:làm nghề|làm|nghề nghiệp là)\s+([A-ZÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴa-záàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ\s]+)", context_text)
            if prof_match:
                reply_text = f"Bạn làm nghề {prof_match.group(1).strip()}"
            else:
                reply_text = "Tôi không biết nghề của bạn"
        elif "chào" in message.lower():
            reply_text = "Chào bạn!"
        elif "kể chuyện" in message.lower() or "dài" in message.lower():
            reply_text = "Đây là một câu trả lời dài để test." * 10
        else:
            reply_text = "Tôi nhận được tin nhắn của bạn."
            
        session.messages.append({"role": "assistant", "content": reply_text})
        reply_tokens = estimate_tokens(reply_text)
        session.token_usage += reply_tokens
        
        return {"content": reply_text}

    def _maybe_build_langchain_agent(self):
        # Build simple chat model instead of full graph for direct API calls
        return build_chat_model(self.config.model)
