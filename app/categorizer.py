"""Expense categorization: trust the LLM's choice, fall back to keyword rules."""
from .config import CATEGORIES

KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("personnel", ["salary", "payroll", "wage", "contractor fee", "freelance",
                   "consulting", "intern", "stipend", "hr "]),
    ("travel", ["flight", "airline", "hotel", "train", "taxi", "uber", "grab",
                "airport", "airfare", "bus ", "ferry", "car rental", "lodging"]),
    ("equipment", ["hardware", "camera", "laptop", "monitor", "desk", "chair",
                   "cable", "adapter", "server", "illuminat", "electronic",
                   "battery", "microphone", "printer"]),
    ("software", ["subscription", "saas", "license", "cloud", "api credit",
                  "hosting", "openai", "anthropic", "adobe", "microsoft",
                  "google cloud", "aws", "figma", "slack", "zoom", "plan"]),
    ("events", ["event", "workshop", "conference", "catering", "venue",
                "meetup", "hackathon", "tickets", "seminar", "training"]),
    ("operational", ["office supplies", "rent", "utilities", "electricity",
                     "internet", "water", "cleaning", "stationery", "shipping",
                     "insurance", "legal", "bank fee", "marketing", "meal",
                     "coffee", "restaurant", "grocery", "water bottles"]),
]


def categorize(llm_category: str | None, context_text: str) -> str:
    """Pick the best category. LLM wins when valid; else keyword scoring."""
    if llm_category:
        llm = llm_category.strip().lower().replace(" ", "_").replace("-", "_")
        for cat in CATEGORIES:
            if cat == llm:
                return cat
        # fuzzy: llm said "operational expenses" -> "operational"
        for cat in CATEGORIES:
            if cat in llm or llm.rstrip("s") in cat:
                return cat

    text = (context_text or "").lower()
    best, best_score = "operational", 0
    for cat, words in KEYWORD_RULES:
        score = sum(1 for w in words if w in text)
        if score > best_score:
            best, best_score = cat, score
    return best
