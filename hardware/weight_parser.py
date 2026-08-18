import re

from timers.timer_manager import (
    replace_number_words,
)


def grams_to_spoken_metric(
    grams: float,
) -> str:

    if grams >= 1000:

        kilograms = (
            grams / 1000.0
        )

        return (
            f"{kilograms:.2f}"
            .rstrip("0")
            .rstrip(".")
            + " kilograms"
        )

    return (
        f"{grams:.0f} grams"
    )



def extract_weight(
    text: str,
):
    """
    Detect a weight requirement.

    Examples:

        5 grams
        five grams
        200 g
        14 oz
        2 ounces
        1 pound
        half a pound
        0.5 kg

    Returns:

        {
            "grams": 50.0,
            "spoken": "50 grams",
            "original_value": 50.0,
            "unit": "g",
        }

    or None.
    """

    normalized = (
        text.lower()
        .replace("–", "-")
        .replace("—", "-")
    )

    # ----------------------------------------
    # Natural fractions
    # ----------------------------------------

    normalized = re.sub(
        r"\bhalf\s+(?:a\s+)?"
        r"(pound|pounds|lb|lbs)\b",
        r"0.5 \1",
        normalized,
    )

    normalized = re.sub(
        r"\ba\s+quarter\s+(?:of\s+)?"
        r"(?:a\s+)?"
        r"(pound|pounds|lb|lbs)\b",
        r"0.25 \1",
        normalized,
    )

    normalized = re.sub(
        r"\bquarter\s+(?:of\s+)?"
        r"(?:a\s+)?"
        r"(pound|pounds|lb|lbs)\b",
        r"0.25 \1",
        normalized,
    )

    # ----------------------------------------
    # Convert:
    #
    # five grams -> 5 grams
    # twenty grams -> 20 grams
    # ----------------------------------------

    normalized = (
        replace_number_words(
            normalized
        )
    )

    # ----------------------------------------
    # Find amount + unit
    # ----------------------------------------

    match = re.search(
        r"\b"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(kg|kilograms?|"
        r"g|grams?|"
        r"oz|ounces?|"
        r"lb|lbs|pounds?)"
        r"\b",
        normalized,
    )

    if not match:

        return None

    value = float(
        match.group(1)
    )

    unit = (
        match.group(2)
        .lower()
    )

    # ----------------------------------------
    # Convert everything to grams
    # ----------------------------------------

    if unit in {
        "g",
        "gram",
        "grams",
    }:

        grams = value

    elif unit in {
        "kg",
        "kilogram",
        "kilograms",
    }:

        grams = (
            value
            * 1000.0
        )

    elif unit in {
        "oz",
        "ounce",
        "ounces",
    }:

        grams = (
            value
            * 28.3495
        )

    elif unit in {
        "lb",
        "lbs",
        "pound",
        "pounds",
    }:

        grams = (
            value
            * 453.592
        )

    else:

        return None

    # ----------------------------------------
    # Spoken description
    # ----------------------------------------

    if unit in {
        "g",
        "gram",
        "grams",
    }:

        spoken = (
            f"{value:g} grams"
        )

    elif unit in {
        "kg",
        "kilogram",
        "kilograms",
    }:

        spoken = (
            f"{value:g} kilograms"
        )

    elif unit in {
        "oz",
        "ounce",
        "ounces",
    }:

        spoken = (
            grams_to_spoken_metric(
                grams
            )
        )

    else:

        spoken = (
            grams_to_spoken_metric(
                grams
            )
        )

    return {
        "grams":
            grams,

        "spoken":
            spoken,

        "original_value":
            value,

        "unit":
            unit,
    }