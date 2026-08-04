from typing import TypedDict


class ChefState(TypedDict):
    user_message: str
    answer: str
    intent: str
    conversation_history: list[dict[str, str]]
    memory: dict