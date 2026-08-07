current_recipe = None
last_recipe = None

def start_recipe(title: str, ingredients: list[str], steps: list[str]):
    global current_recipe
    global last_recipe

    recipe = {
        "title": title.strip() if title else "Recipe",
        "ingredients": ingredients,
        "steps": [
            step.strip()
            for step in steps
            if isinstance(step, str) and step.strip()
        ],
        "current_step": 0,
    }

    current_recipe = recipe
    last_recipe = recipe.copy()

    print("\nRecipe session created:")
    print(current_recipe)

def restart_last_recipe():

    global current_recipe

    if last_recipe is None:
        return False

    current_recipe = {
        "title": last_recipe["title"],
        "ingredients": list(last_recipe["ingredients"]),
        "steps": list(last_recipe["steps"]),
        "current_step": 0,
    }

    return True

def get_last_recipe():
    return last_recipe


def has_active_recipe():
    return current_recipe is not None


def get_current_recipe():
    return current_recipe


def get_current_step():
    if current_recipe is None:
        return None

    steps = current_recipe.get("steps", [])

    if not steps:
        return None

    current_step_index = current_recipe.get("current_step", 0)

    if current_step_index < 0 or current_step_index >= len(steps):
        return None

    return steps[current_step_index]


def next_step():
    global current_recipe

    if current_recipe is None:
        return None

    steps = current_recipe.get("steps", [])

    if not steps:
        return None

    current_step_index = current_recipe.get(
        "current_step",
        0
    )

    # Move to the next step
    if current_step_index < len(steps) - 1:

        current_recipe["current_step"] = (
            current_step_index + 1
        )

        return get_current_step()

    # We were already on the final step
    title = current_recipe.get(
        "title",
        "the recipe"
    )

    finish_recipe()

    return (
        "Congratulations!\n\n"
        f"Your {title} is ready.\n\n"
        "Enjoy your meal."
    )


def previous_step():
    if current_recipe is None:
        return None

    steps = current_recipe.get("steps", [])

    if not steps:
        return None

    if current_recipe.get("current_step", 0) > 0:
        current_recipe["current_step"] -= 1

    return get_current_step()


def start_over():
    if current_recipe is None:
        return None

    current_recipe["current_step"] = 0
    return get_current_step()


def repeat_step():
    return get_current_step()


def finish_recipe():
    global current_recipe
    current_recipe = None