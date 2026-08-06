AVAILABLE_CUISINES = {
    "american": "American",
    "chinese": "Chinese",
    "egyptian": "Egyptian",
    "french": "French",
    "indian": "Indian",
    "italian": "Italian",
    "japanese": "Japanese",
    "korean": "Korean",
    "mediterranean": "Mediterranean",
    "mexican": "Mexican",
    "thai": "Thai",
}


def detect_cuisine(user_query: str) -> str | None:
    """
    Detect whether the user explicitly mentions a cuisine.
    """

    query = user_query.lower()

    for keyword, cuisine in AVAILABLE_CUISINES.items():
        if keyword in query:
            return cuisine

    return None