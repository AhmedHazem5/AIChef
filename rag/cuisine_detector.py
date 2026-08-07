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


CUISINE_DISHES = {
    "American": [
        "burger",
        "hamburger",
        "hot dog",
        "fried chicken",
        "mac and cheese",
    ],

    "Chinese": [
        "fried rice",
        "dumplings",
        "spring rolls",
        "sweet and sour",
        "kung pao",
        "chow mein",
    ],

    "Egyptian": [
        "koshari",
        "molokhia",
        "mahshi",
        "ful",
        "falafel",
    ],

    "French": [
        "ratatouille",
        "croissant",
        "quiche",
        "crepe",
        "coq au vin",
    ],

    "Indian": [
        "butter chicken",
        "biryani",
        "tikka",
        "masala",
        "naan",
        "curry",
        "dal",
    ],

    "Italian": [
        "pizza",
        "pasta",
        "lasagna",
        "risotto",
        "spaghetti",
        "carbonara",
        "alfredo",
    ],

    "Japanese": [
        "sushi",
        "ramen",
        "udon",
        "tempura",
        "teriyaki",
        "yakisoba",
    ],

    "Korean": [
        "kimchi",
        "bibimbap",
        "bulgogi",
        "tteokbokki",
    ],

    "Mediterranean": [
        "hummus",
        "tabbouleh",
        "shawarma",
        "kebab",
    ],

    "Mexican": [
        "taco",
        "tacos",
        "burrito",
        "quesadilla",
        "enchilada",
        "guacamole",
    ],

    "Thai": [
        "pad thai",
        "green curry",
        "tom yum",
        "massaman",
    ],
}


def detect_cuisine(user_query: str) -> str | None:
    """
    Detect the cuisine from either:
    - Explicit cuisine names
    - Famous dish names
    """

    query = user_query.lower()

    # Check explicit cuisine names
    for keyword, cuisine in AVAILABLE_CUISINES.items():
        if keyword in query:
            return cuisine

    # Check famous dishes
    for cuisine, dishes in CUISINE_DISHES.items():
        for dish in dishes:
            if dish in query:
                return cuisine

    return None