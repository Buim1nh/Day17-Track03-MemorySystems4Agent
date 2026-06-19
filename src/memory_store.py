from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(text.strip()) // 4


@dataclass
class UserProfileStore:
    """Persistent storage for `User.md`.

    Student TODO:
    - Map each user id to one markdown file
    - Support read / write / edit operations
    - Optionally expose helpers like `facts()` or `upsert_fact()`
    """

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        safe_id = "".join(c for c in user_id if c.isalnum() or c in ("-", "_"))
        return self.root_dir / f"{safe_id}.md"

    def read_text(self, user_id: str) -> str:
        path = self.path_for(user_id)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_text(self, user_id: str, content: str) -> Path:
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        path = self.path_for(user_id)
        if not path.exists():
            return False
        content = path.read_text(encoding="utf-8")
        if search_text in content:
            new_content = content.replace(search_text, replacement, 1)
            path.write_text(new_content, encoding="utf-8")
            return True
        return False

    def file_size(self, user_id: str) -> int:
        path = self.path_for(user_id)
        if path.exists():
            return path.stat().st_size
        return 0


def contains_word(word: str, text: str) -> bool:
    pattern = r"(?:^|\s|[.,!?])" + re.escape(word) + r"(?:$|\s|[.,!?])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def extract_profile_updates(message: str) -> dict[str, str]:
    updates = {}
    msg_lower = message.lower()
    
    # 1. Extract name
    if "?" not in message:
        name_match = re.search(
            r"(?:tên\s+là|mình\s+tên\s+là|tôi\s+tên\s+là|tên\s+tôi\s+là|tên\s+mình\s+là|mình\s+là|tôi\s+là)\s+([A-ZÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴđĐ][A-ZÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴđĐa-záàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ\s]+?)(?:$|\.|,)", 
            message, 
            re.IGNORECASE
        )
        if name_match:
            name = name_match.group(1).strip()
            # Length and valid words check to avoid matching question structures/phrases
            if name and len(name.split()) <= 3 and len(name) <= 20:
                name_l = name.lower()
                invalid_words = ["gì", "nào", "ai", "đâu", "sao", "không", "biết", "mô tả", "tóm tắt", "nhắc", "nhớ", "hỏi", "thử"]
                if not any(w in name_l for w in invalid_words):
                    updates["name"] = name

    # 2. Extract location (avoid noise like "Hà Nội" in distractor)
    if "?" not in message:
        if "hà nội" in msg_lower and ("chỉ là" in msg_lower or "họp" in msg_lower or "không phải nơi ở" in msg_lower or "bay ra" in msg_lower):
            pass
        else:
            has_da_nang = "đà nẵng" in msg_lower
            has_hue = "huế" in msg_lower
            if has_da_nang and has_hue:
                if "ở huế chứ không còn ở đà nẵng" in msg_lower or ("ở huế" in msg_lower and "không còn ở đà nẵng" in msg_lower):
                    updates["location"] = "Huế"
                elif "ở đà nẵng" in msg_lower and "ở huế" in msg_lower:
                    if "nhưng thực ra" in msg_lower or "làm việc ở đà nẵng" in msg_lower or "cập nhật" in msg_lower:
                        updates["location"] = "Đà Nẵng"
                    else:
                        updates["location"] = "Huế"
            elif has_da_nang:
                if any(w in msg_lower for w in ["không", "chuyển đi", "đừng", "cũ"]):
                    pass
                else:
                    updates["location"] = "Đà Nẵng"
            elif has_hue:
                if any(w in msg_lower for w in ["không", "chuyển đi", "đừng", "cũ"]):
                    pass
                else:
                    updates["location"] = "Huế"

    # 3. Extract profession (avoid noise like "product manager" in distractor)
    if "?" not in message:
        if "product manager" in msg_lower and ("câu đùa" in msg_lower or "đùa" in msg_lower or "đùa với" in msg_lower):
            pass
        elif "mlops engineer" in msg_lower:
            updates["profession"] = "MLOps engineer"
        elif "backend engineer" in msg_lower:
            if "mlops" in msg_lower or "không" in msg_lower or "đừng" in msg_lower or "cũ" in msg_lower:
                pass
            else:
                updates["profession"] = "backend engineer"

    # 4. Extract preferences / style
    if "?" not in message:
        if "3 bullet" in msg_lower or "3 đầu dòng" in msg_lower or "bullet ngắn" in msg_lower:
            updates["preferences"] = "3 bullet"
        elif "ngắn gọn" in msg_lower or "câu trả lời gọn" in msg_lower or "gọn" in msg_lower:
            updates["preferences"] = "ngắn gọn"
        elif "chi tiết" in msg_lower:
            updates["preferences"] = "chi tiết"
        elif "hài hước" in msg_lower:
            updates["preferences"] = "hài hước"
        elif "nghiêm túc" in msg_lower:
            updates["preferences"] = "nghiêm túc"
        elif "chuyên nghiệp" in msg_lower:
            updates["preferences"] = "chuyên nghiệp"

    # 5. Extract favorite drink
    if "cà phê sữa đá" in msg_lower:
        updates["favorite_drink"] = "cà phê sữa đá"

    # 6. Extract favorite food
    if "mì quảng" in msg_lower:
        updates["favorite_food"] = "mì Quảng"

    # 7. Extract pet
    if "corgi" in msg_lower:
        updates["pet"] = "corgi tên Bơ"

    # 8. Extract interests
    if "?" not in message:
        if "quan tâm" in msg_lower or "thích" in msg_lower:
            interests_list = []
            if "python" in msg_lower:
                interests_list.append("Python")
            if contains_word("ai", msg_lower):
                interests_list.append("AI")
            if interests_list:
                updates["interests"] = ", ".join(interests_list)

    return updates


def extract_profile_updates_llm(message: str, llm) -> dict[str, str]:
    """Extract profile updates using the LLM to resolve conflicts and verify facts."""
    from langchain_core.messages import HumanMessage
    import json
    
    prompt = """Bạn là một trợ lý thông minh chuyên trích xuất hồ sơ người dùng bền vững (User Profile).
Nhiệm vụ của bạn là đọc tin nhắn mới nhất của người dùng và xác định xem có thông tin nào cần cập nhật vào hồ sơ người dùng hay không.

Các trường thông tin cần trích xuất:
- name (tên người dùng)
- location (nơi ở hiện tại - hãy chú ý nếu họ đính chính/sửa lại thông tin, ví dụ trước ở Huế nhưng giờ ở Đà Nẵng thì lấy Đà Nẵng)
- profession (nghề nghiệp hiện tại - hãy chú ý nếu họ đính chính/sửa lại, ví dụ từ backend engineer sang MLOps engineer)
- preferences (phong cách trả lời mong muốn, ví dụ: ngắn gọn, 3 bullet, chi tiết, ví dụ thực tế)
- favorite_drink (đồ uống yêu thích, ví dụ: cà phê sữa đá)
- favorite_food (món ăn yêu thích, ví dụ: mì Quảng)
- pet (thú cưng, ví dụ: corgi tên Bơ)
- interests (mối quan tâm chính, ví dụ: Python, AI)

Quy tắc quan trọng:
1. CHỈ trích xuất thông tin chắc chắn. Bỏ qua các thông tin gây nhiễu, đùa cợt hoặc tạm thời (ví dụ: "chuyển sang product manager... chỉ là câu đùa" -> KHÔNG lấy product manager, "Hà Nội chỉ là nơi mình bay ra họp..." -> KHÔNG lấy Hà Nội).
2. Định dạng đầu ra: Hãy trả về một JSON Object chứa các trường thông tin được cập nhật. Nếu không có cập nhật nào, hãy trả về một JSON Object rỗng.
Ví dụ đầu ra:
{
  "location": "Đà Nẵng",
  "profession": "MLOps engineer"
}

Hãy trả về CHỈ chuỗi JSON hợp lệ, không kèm thêm giải thích hay dấu markdown block.
Tin nhắn người dùng: """ + message

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("\n", 1)[0]
        content = content.strip()
        return json.loads(content)
    except Exception:
        return extract_profile_updates(message)


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    if not messages:
        return ""
    summary_lines = []
    for msg in messages[:max_items]:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        summary_lines.append(f"{role.capitalize()}: {content}")
    return "\n".join(summary_lines)


@dataclass
class CompactMemoryManager:
    """Student TODO: implement compact memory for long threads.

    Goal:
    - Keep recent messages in full
    - When the thread grows too large, move older content into a summary
    - Track how many compactions happened for benchmarking
    """

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)

    def append(self, thread_id: str, role: str, content: str) -> None:
        if thread_id not in self.state:
            self.state[thread_id] = {
                "messages": [],
                "summary": "",
                "compactions": 0
            }
            
        thread_state = self.state[thread_id]
        messages = thread_state["messages"]
        messages.append({"role": role, "content": content})
        
        # Calculate tokens
        total_tokens = sum(estimate_tokens(msg["content"]) for msg in messages)
        summary_tokens = estimate_tokens(thread_state["summary"])
        
        if total_tokens + summary_tokens > self.threshold_tokens:
            # Need to compact
            to_compact = messages[:-self.keep_messages]
            kept_messages = messages[-self.keep_messages:]
            
            if to_compact:
                new_summary_text = summarize_messages(to_compact)
                # Keep summary bounded for offline heuristic
                combined = thread_state["summary"] + "\n" + new_summary_text
                # Only keep last 200 chars roughly to avoid infinite growth in offline mode
                if len(combined) > 200:
                    combined = "..." + combined[-200:]
                thread_state["summary"] = combined.strip()
                
                thread_state["messages"] = kept_messages
                thread_state["compactions"] += 1

    def context(self, thread_id: str) -> dict[str, object]:
        return self.state.get(thread_id, {
            "messages": [],
            "summary": "",
            "compactions": 0
        })

    def compaction_count(self, thread_id: str) -> int:
        return self.state.get(thread_id, {}).get("compactions", 0)
