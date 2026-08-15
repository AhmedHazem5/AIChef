import ollama

import time

MODEL_NAME = "qwen3:0.6b"


def rewrite_query(user_query: str) -> str:
    """
    Rewrite the user's recipe request into a better search query
    for vector retrieval.
    """

    prompt = f"""
Rewrite the user's request into a concise recipe search query.

Rules:
- Keep it under 12 words.
- Preserve cuisine if mentioned.
- Preserve ingredients if mentioned.
- Preserve dish names if mentioned.
- Do not answer the question.
- Return ONLY the rewritten search query.

User request:
{user_query}
"""
    start = time.perf_counter()
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        options={
            "temperature": 0,
        },
        think=False,
        keep_alive="30m",
    )
    elapsed = (
        time.perf_counter()
        - start
    )
    print(
        f"[TIMING] query rewriter: "
        f"{elapsed:.2f} seconds"
    )

    return response["message"]["content"].strip()
