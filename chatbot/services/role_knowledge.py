import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from django.conf import settings


class RoleKnowledgeBase:
    def __init__(self):
        self.path = Path(settings.BASE_DIR) / "chatbot" / "data" / "role_faq.json"
        self.data = self.load_data()

    def load_data(self):
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as error:
            print(f"Role knowledge base load failed: {error}")
            return {"common": [], "traveller": [], "guide": [], "admin": []}

    def normalize(self, text):
        text = str(text or "").lower().strip()
        text = re.sub(r"[^\w\s\u0980-\u09FF]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def tokens(self, text):
        return set(self.normalize(text).split())

    def score(self, user_message, pattern):
        user_text = self.normalize(user_message)
        pattern_text = self.normalize(pattern)

        if not user_text or not pattern_text:
            return 0

        if user_text == pattern_text:
            return 100

        if pattern_text in user_text or user_text in pattern_text:
            return 90

        user_tokens = self.tokens(user_text)
        pattern_tokens = self.tokens(pattern_text)

        if not user_tokens or not pattern_tokens:
            return 0

        overlap = len(user_tokens & pattern_tokens)
        token_score = (overlap / max(len(pattern_tokens), 1)) * 70

        ratio_score = SequenceMatcher(None, user_text, pattern_text).ratio() * 60

        return max(token_score, ratio_score)

    def card(self, item):
        return {
            "title": str(item.get("title", "")),
            "description": str(item.get("description", "")),
            "url": str(item.get("url", "")),
            "link": str(item.get("url", "")),
        }

    def answer(self, message, role):
        role = role or "guest"

        search_items = []
        search_items.extend(self.data.get("common", []))

        if role in ["traveller", "guide", "admin"]:
            search_items.extend(self.data.get(role, []))

        best_item = None
        best_score = 0

        for item in search_items:
            for question in item.get("questions", []):
                current_score = self.score(message, question)

                if current_score > best_score:
                    best_score = current_score
                    best_item = item

        if not best_item or best_score < 45:
            return None

        return {
            "reply": best_item.get("answer", "I can help with Colo Ghuri."),
            "cards": [self.card(card) for card in best_item.get("cards", [])],
            "quick_replies": best_item.get("quick_replies", []),
            "requires_confirmation": False,
            "pending_action": None,
            "nlu": {
                "source": "role_knowledge_base",
                "intent": best_item.get("intent"),
                "confidence": round(best_score / 100, 4),
                "role": role,
                "is_confident": True,
            },
        }