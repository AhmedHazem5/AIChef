from langgraph.graph import StateGraph, START, END

from graph.state import ChefState

from graph.cooking_node import cooking_node
from graph.memory_node import memory_node
from graph.recipe_node import recipe_node
from graph.chat_node import chat_node

from memory.memory_manager import load_memory
from memory.cooking_session import has_active_recipe
from memory.recommendation_context import get_pending_recipe

from routing.intent_classifier import classify_with_qwen

import re


# ============================================================
# Cooking commands
# ============================================================

COOKING_COMMANDS = {
    "next",
    "next step",
    "continue",
    "continue recipe",
    "go on",
    "go to next step",

    "repeat",
    "repeat that",
    "repeat step",
    "repeat current step",
    "say that again",

    "previous",
    "previous step",
    "go back",
    "back",
    "go to previous step",

    "pause",
    "pause recipe",

    "finish",
    "finish recipe",
    "stop recipe",
    "end recipe",

    "start over",
    "restart",
    "restart recipe",
    "start recipe over",
    "start from beginning",
    "start from step one",
    "start the recipe from step one",

    "make it again",
    "cook it again",
}


# ============================================================
# Questions about the active recipe
# ============================================================

RECIPE_QUESTION_PHRASES = {
    "can i",
    "can we",
    "could i",
    "could we",
    "should i",
    "should we",
    "do i need",
    "does it need",
    "is it okay",
    "is it ok",
    "what if",
    "why do i",
    "why should i",
    "why does",
    "how long",
    "how much",
    "what temperature",
    "what heat",
    "what can i use instead",
    "what can i replace",
    "what should i use instead",
    "can i replace",
    "can i substitute",
    "replace",
    "substitute",
    "instead",
    "don't have",
    "do not have",
    "skip",
    "omit",
    "how many calories",
    "how many carbs",
    "how many carbohydrates",
    "how many grams of protein",
    "how much protein",
    "how much fat",
    "how much nutrition",
    "what are the macros",
    "what is the nutrition",
    "nutrition information",
}


# ============================================================
# Normalize speech-recognized text
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize text coming from speech recognition.

    Examples:

        "Next."       -> "next"
        "NEXT!"       -> "next"
        "Repeat?"     -> "repeat"
        "Go back."    -> "go back"
        "Next, please" -> "next please"
    """

    if not text:
        return ""

    text = text.lower().strip()

    # Remove quotation marks
    text = text.replace('"', "")
    text = text.replace("'", "")

    # Replace punctuation with spaces
    text = re.sub(r"[.!?,;:]+", " ", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# Determine whether the user is asking about the active recipe
# ============================================================

def looks_like_recipe_question(text: str) -> bool:

    # Explicit request for a NEW recipe should always win.
    new_recipe_phrases = {
        "give me a recipe",
        "give me another recipe",
        "find me a recipe",
        "recommend a recipe",
        "suggest a recipe",
        "give me a meal",
        "recommend a meal",
        "suggest a meal",
        "what should i eat",
    }

    if any(
        phrase in text
        for phrase in new_recipe_phrases
    ):
        return False

    return any(
        phrase in text
        for phrase in RECIPE_QUESTION_PHRASES
    )


# ============================================================
# Intent Classification
# ============================================================

def classify_request(state: ChefState):

    # Normalize speech-recognized input
    text = normalize_text(
        state["user_message"]
    )

    # --------------------------------------------------------
    # 1. Simple affirmative follow-up to a blocked request
    #
    # Keep this deterministic so we do NOT call the full
    # follow-up classifier twice.
    #
    # recipe_node will run is_similar_recipe_followup() once
    # and handle richer replies such as:
    # "recommend something similar".
    # --------------------------------------------------------

    pending_recipe = get_pending_recipe()

    affirmative_replies = {
        "yes",
        "yes please",
        "yeah",
        "yeah sure",
        "yep",
        "sure",
        "okay",
        "ok",
        "please",
        "go ahead",
        "sounds good",
    }

    if (
        pending_recipe
        and text in affirmative_replies
    ):

        return {
            "intent": "RECIPE_SEARCH"
        }

    # --------------------------------------------------------
    # 2. Cooking commands
    # --------------------------------------------------------

    if (
        has_active_recipe()
        and text in COOKING_COMMANDS
    ):
        return {
            "intent": "COOKING_COMMAND"
        }

    # --------------------------------------------------------
    # 3. Questions about active recipe
    # --------------------------------------------------------

    if (
        has_active_recipe()
        and looks_like_recipe_question(text)
    ):
        return {
            "intent": "RECIPE_QUESTION"
        }

    # --------------------------------------------------------
    # 4. Everything else goes to Qwen
    # --------------------------------------------------------

    intent = classify_with_qwen(
        state["user_message"]
    )

    return {
        "intent": intent
    }


# ============================================================
# Routing
# ============================================================

def route_by_intent(state: ChefState):

    intent = state["intent"]

    if intent == "MEMORY_UPDATE":
        return "memory_node"

    if intent == "MEMORY_QUERY":
        return "chat_node"

    if intent == "RECIPE_SEARCH":
        return "recipe_node"

    if intent == "COOKING_COMMAND":
        return "cooking_node"

    if intent == "RECIPE_QUESTION":
        return "chat_node"

    return "chat_node"


# ============================================================
# Build LangGraph
# ============================================================

builder = StateGraph(ChefState)


# ============================================================
# Nodes
# ============================================================

builder.add_node(
    "classify_request",
    classify_request,
)

builder.add_node(
    "memory_node",
    memory_node,
)

builder.add_node(
    "recipe_node",
    recipe_node,
)

builder.add_node(
    "chat_node",
    chat_node,
)

builder.add_node(
    "cooking_node",
    cooking_node,
)


# ============================================================
# Start
# ============================================================

builder.add_edge(
    START,
    "classify_request",
)


# ============================================================
# Conditional routing
# ============================================================

builder.add_conditional_edges(
    "classify_request",
    route_by_intent,
    {
        "memory_node": "memory_node",
        "recipe_node": "recipe_node",
        "cooking_node": "cooking_node",
        "chat_node": "chat_node",
    },
)


# ============================================================
# End
# ============================================================

builder.add_edge(
    "memory_node",
    END,
)

builder.add_edge(
    "recipe_node",
    END,
)

builder.add_edge(
    "chat_node",
    END,
)

builder.add_edge(
    "cooking_node",
    END,
)


# ============================================================
# Compile
# ============================================================

chef_graph = builder.compile()


# ============================================================
# Public entry point
# ============================================================

def run_chef_graph(
    user_message: str,
    conversation_history: list[dict[str, str]],
):

    result = chef_graph.invoke(
        {
            "user_message": user_message,
            "answer": "",
            "intent": "",
            "conversation_history": conversation_history,
            "memory": load_memory(),
        }
    )

    return result