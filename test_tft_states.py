import time

from ui.display_manager import (
    DisplayManager,
)


display = DisplayManager()

print("Showing IDLE...")
display.show_idle()
time.sleep(3)

print("Showing LISTENING...")
display.show_listening()
time.sleep(3)

print("Showing THINKING...")
display.show_thinking()
time.sleep(3)

print("Showing COOKING STEP...")
display.show_cooking_step(
    recipe_title="Tomato Pasta",
    step_number=2,
    total_steps=6,
    step_text=(
        "Add the tomatoes and cook "
        "for ten minutes."
    ),
)

print(
    "TFT state test complete."
)

while True:
    time.sleep(1)