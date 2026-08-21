import json
import ollama
import time

MODEL_NAME = "qwen3:4b-instruct"


MEMORY_EXTRACTION_PROMPT = """
You extract long-term personal food preferences from user messages.

Extract ONLY information the user explicitly states about themselves.

Allowed categories:
- likes
- dislikes
- allergies
- dietary_preferences
- goals

Return valid JSON only.

The exact structure must be:

{
  "likes": [],
  "dislikes": [],
  "allergies": [],
  "dietary_preferences": [],
  "goals": []
}

Rules:
- Do not guess.
- Do not infer information that was not explicitly stated.
- Keep values short and normalized.
- Do not include temporary requests.
- Do not include recipe ingredients unless the user expresses a personal preference.
- A user can provide multiple memories in one sentence.
- If no long-term memory is present, return empty arrays.

Examples:

User:
"I love spicy food but I hate mushrooms."

Output:
{
  "likes": ["spicy food"],
  "dislikes": ["mushrooms"],
  "allergies": [],
  "dietary_preferences": [],
  "goals": []
}

User:
"I'm allergic to peanuts and I don't eat pork."

Output:
{
  "likes": [],
  "dislikes": [],
  "allergies": ["peanuts"],
  "dietary_preferences": ["no pork"],
  "goals": []
}

User:
"I want chicken pasta tonight."

Output:
{
  "likes": [],
  "dislikes": [],
  "allergies": [],
  "dietary_preferences": [],
  "goals": []
}

Dietary preferences should use these normalized values when applicable:

- halal
- vegetarian
- vegan

Examples:

User:
"I eat halal."

Output:
{
  "likes": [],
  "dislikes": [],
  "allergies": [],
  "dietary_preferences": ["halal"],
  "goals": []
}

User:
"I'm vegetarian."

Output:
{
  "likes": [],
  "dislikes": [],
  "allergies": [],
  "dietary_preferences": ["vegetarian"],
  "goals": []
}

User:
"Remember that I'm vegan."

Output:
{
  "likes": [],
  "dislikes": [],
  "allergies": [],
  "dietary_preferences": ["vegan"],
  "goals": []
}
"""


def extract_memory(user_message: str) -> dict:
    start = time.perf_counter()
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": MEMORY_EXTRACTION_PROMPT,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        format="json",
        options={
            "temperature": 0,
        },
        think=False,
        keep_alive="30m",
    )

    elapsed = time.perf_counter() - start

    print(
        f"[TIMING] memory extractor: "
        f"{elapsed:.2f} seconds"
    )

    content = response["message"]["content"]

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {
            "likes": [],
            "dislikes": [],
            "allergies": [],
            "dietary_preferences": [],
            "goals": [],
        }

    return data