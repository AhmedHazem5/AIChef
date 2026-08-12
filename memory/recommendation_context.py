_pending_recipe = None


def set_pending_recipe(
    recipe: dict,
):
    global _pending_recipe

    _pending_recipe = recipe


def get_pending_recipe():
    return _pending_recipe


def clear_pending_recipe():
    global _pending_recipe

    _pending_recipe = None