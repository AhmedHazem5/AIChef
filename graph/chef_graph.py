from langgraph.graph import StateGraph, START, END

from graph.state import ChefState

from llm.local_llm import ask_chef

from memory.memory_extractor import extract_memory
from memory.memory_manager import (
    merge_memory_updates,
    load_memory,
)


from routing.intent_classifier import classify_with_qwen


def classify_request(state: ChefState):
    text = state["user_message"].lower().strip()

    obvious_cooking_commands = {
        "next",
        "next step",
        "repeat",
        "repeat that",
        "go back",
        "previous step",
        "pause",
        "continue",
    }

    if text in obvious_cooking_commands:
        return {
            "intent": "COOKING_COMMAND"
        }

    intent = classify_with_qwen(
        state["user_message"]
    )

    return {
        "intent": intent
    }

def memory_update_node(state: ChefState):
    """
    Use Qwen to extract long-term memory from natural language,
    then safely merge that information into user_memory.json.
    """

    updates = extract_memory(
        state["user_message"]
    )

    updated_memory = merge_memory_updates(
        updates
    )

    saved_items = []

    for category, values in updates.items():
        if not isinstance(values, list):
            continue

        for value in values:
            if isinstance(value, str) and value.strip():
                saved_items.append(
                    f"{category}: {value}"
                )

    if not saved_items:
        return {
            "answer": (
                "I understood that this may contain a preference, "
                "but I couldn't find anything useful to save."
            ),
            "memory": load_memory(),
        }

    print("\nMemory saved:")

    for item in saved_items:
        print(f"- {item}")

    return {
        "answer": "Got it. I'll remember that.",
        "memory": updated_memory,
    }


def generate_answer(state: ChefState):
    """
    Normal Qwen response.

    The user's saved long-term memory is included in the prompt
    so Qwen can already consider likes, dislikes, allergies, etc.

    Later:
    RECIPE_SEARCH will have its own RAG node instead.
    """

    memory = load_memory()

    memory_context = f"""
The following is verified long-term information about the user.

Likes:
{memory.get("likes", [])}

Dislikes:
{memory.get("dislikes", [])}

Allergies:
{memory.get("allergies", [])}

Dietary preferences:
{memory.get("dietary_preferences", [])}

Goals:
{memory.get("goals", [])}

Important:
Use this information when it is relevant.
Do not invent additional preferences or allergies.
"""

    enhanced_message = f"""
{memory_context}

User message:
{state["user_message"]}
"""

    answer = ask_chef(
        user_message=enhanced_message,
        conversation_history=state[
            "conversation_history"
        ],
    )

    return {
        "answer": answer,
        "memory": memory,
    }


def route_by_intent(state: ChefState):
    """
    Decide which LangGraph node should run after classification.
    """

    intent = state["intent"]

    if intent == "MEMORY_UPDATE":
        return "memory_update"

    # For now:
    # RECIPE_SEARCH
    # COOKING_COMMAND
    # GENERAL_QUESTION
    #
    # all still use Qwen normally.
    #
    # Later they will get their own nodes.
    return "generate_answer"


# ============================================================
# BUILD LANGGRAPH
# ============================================================

builder = StateGraph(ChefState)


# -----------------------------
# Nodes
# -----------------------------

builder.add_node(
    "classify_request",
    classify_request,
)

builder.add_node(
    "memory_update",
    memory_update_node,
)

builder.add_node(
    "generate_answer",
    generate_answer,
)


# -----------------------------
# Start
# -----------------------------

builder.add_edge(
    START,
    "classify_request",
)


# -----------------------------
# Conditional routing
# -----------------------------

builder.add_conditional_edges(
    "classify_request",
    route_by_intent,
    {
        "memory_update": "memory_update",
        "generate_answer": "generate_answer",
    },
)


# -----------------------------
# End
# -----------------------------

builder.add_edge(
    "memory_update",
    END,
)

builder.add_edge(
    "generate_answer",
    END,
)


# Compile graph once
chef_graph = builder.compile()


def run_chef_graph(
    user_message: str,
    conversation_history: list[dict[str, str]],
):
    """
    Entry point used by main.py.
    """

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