import re
import threading
import time

from hardware.buzzer import (
    get_buzzer,
)


class CookingTimer:
    def __init__(
        self,
        duration_seconds: int,
        label: str,
    ):

        self.duration_seconds = (
            duration_seconds
        )

        self.label = label

        self.started_at = (
            time.time()
        )

        self.cancelled = False

        self.finished = False


class TimerManager:
    def __init__(self):

        self.active_timers: list[
            CookingTimer
        ] = []

        self.lock = (
            threading.Lock()
        )

    def start_timer(
        self,
        duration_seconds: int,
        label: str,
        display=None,
    ) -> CookingTimer:

        timer = CookingTimer(
            duration_seconds=(
                duration_seconds
            ),
            label=label,
        )

        with self.lock:

            self.active_timers.append(
                timer
            )

        thread = threading.Thread(
            target=self._run_timer,
            args=(timer,display,),
            daemon=True,
        )

        thread.start()

        return timer

    def _run_timer(
        self,
        timer: CookingTimer,
        display=None,
    ) -> None:

        print(
            f"\n[TIMER] Started: "
            f"{timer.label}"
        )

        end_time = (
            time.time()
            + timer.duration_seconds
        )

        last_display_second = None

        while True:

            if timer.cancelled:

                print(
                    f"[TIMER] Cancelled: "
                    f"{timer.label}"
                )

                return

            remaining = (
                end_time
                - time.time()
            )

            if remaining <= 0:
                break

            remaining_seconds = (
                int(
                    remaining
                )
                + 1
            )

            if (
                display is not None
                and remaining_seconds
                != last_display_second
            ):

                display.show_timer(
                    remaining_seconds
                )

                last_display_second = (
                    remaining_seconds
                )

            time.sleep(
                0.1
            )

        timer.finished = True

        print(
            f"\n[TIMER COMPLETE] "
            f"{timer.label}"
        )

        if display is not None:

            display.show_timer_done()

        buzzer = get_buzzer()

        buzzer.timer_finished_alert()

    if display is not None:

        display.show_timer_done()

    buzzer = get_buzzer()

    buzzer.timer_finished_alert()

    if display is not None:

        time.sleep(
            2.0
        )

        display.restore_previous_screen()

    def get_active_timers(
        self,
    ) -> list[CookingTimer]:

        with self.lock:

            return [
                timer
                for timer
                in self.active_timers

                if (
                    not timer.finished
                    and not timer.cancelled
                )
            ]


_timer_manager = None


def get_timer_manager(
) -> TimerManager:

    global _timer_manager

    if _timer_manager is None:

        _timer_manager = (
            TimerManager()
        )

    return _timer_manager


# ============================================================
# Duration extraction
# ============================================================

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def replace_number_words(
    text: str,
) -> str:
    """
    Convert common written numbers into digits.

    Examples:
        three minutes
            -> 3 minutes

        twenty five minutes
            -> 25 minutes

        one hour and thirty minutes
            -> 1 hour and 30 minutes
    """


    text = re.sub(
        r"(?<=[A-Za-z])-(?=[A-Za-z])",
        " ",
        text,
    )
    
    words = text.split()

    result = []

    index = 0

    while index < len(words):

        word = (
            words[index]
            .lower()
            .strip(".,!?;:")
        )

        if word not in NUMBER_WORDS:

            result.append(
                words[index]
            )

            index += 1

            continue

        value = NUMBER_WORDS[
            word
        ]

        # Handle:
        # twenty five
        # thirty two
        # forty five
        if (
            value >= 20
            and value % 10 == 0
            and index + 1 < len(words)
        ):

            next_word = (
                words[index + 1]
                .lower()
                .strip(".,!?;:")
            )

            if (
                next_word
                in NUMBER_WORDS
                and 0
                < NUMBER_WORDS[
                    next_word
                ]
                < 10
            ):

                value += (
                    NUMBER_WORDS[
                        next_word
                    ]
                )

                index += 1

        result.append(
            str(value)
        )

        index += 1

    return " ".join(
        result
    )

def extract_duration(
    text: str,
):
    """
    Extract cooking durations.

    Examples:
        "3 minutes"
        "three minutes"
        "30-35 minutes"
        "30–35 minutes"
        "thirty-five minutes"
        "1 hour 30 minutes"
    """

    normalized = text.lower().strip()

    # Convert PDF dash variants to normal hyphen.
    normalized = (
        normalized
        .replace("–", "-")
        .replace("—", "-")
    )

    # Convert written numbers such as:
    # "three" -> "3"
    # "thirty-five" -> "35"
    normalized = replace_number_words(
        normalized
    )

    normalized = re.sub(
        r"\b(?:about\s+)?a\s+minute\b",
        "1 minute",
        normalized,
    )

    normalized = re.sub(
        r"\b(?:about\s+)?an\s+hour\b",
        "1 hour",
        normalized,
    )

    # ========================================================
    # 1. RANGE MUST BE CHECKED FIRST
    #
    # 30-35 minutes
    # 30 - 35 minutes
    #
    # We intentionally use the LOWER value.
    # ========================================================

    match = re.search(
        r"(?<!\d)"
        r"(\d+)"
        r"\s*-\s*"
        r"(\d+)"
        r"\s*"
        r"(?:minutes?|mins?)"
        r"\b",
        normalized,
    )

    if match:

        lower_minutes = int(
            match.group(1)
        )

        upper_minutes = int(
            match.group(2)
        )

        print(
            f"[TIMER PARSER] "
            f"Detected range: "
            f"{lower_minutes}-"
            f"{upper_minutes} minutes"
        )

        return {
            "seconds":
                lower_minutes * 60,

            "spoken":
                (
                    f"{lower_minutes} minute"
                    f"{'s' if lower_minutes != 1 else ''}"
                ),
        }

    # ========================================================
    # 2. HOURS + OPTIONAL MINUTES
    #
    # 1 hour
    # 1 hour 30 minutes
    # 1 hour and 30 minutes
    # ========================================================

    match = re.search(
        r"(?<!\d)"
        r"(\d+)"
        r"\s*"
        r"(?:hours?|hrs?)"
        r"(?:"
        r"\s*(?:and\s*)?"
        r"(\d+)"
        r"\s*"
        r"(?:minutes?|mins?)"
        r")?",
        normalized,
    )

    if match:

        hours = int(
            match.group(1)
        )

        minutes = int(
            match.group(2)
            or 0
        )

        seconds = (
            hours * 3600
            + minutes * 60
        )

        if minutes:

            spoken = (
                f"{hours} hour"
                f"{'s' if hours != 1 else ''} "
                f"{minutes} minute"
                f"{'s' if minutes != 1 else ''}"
            )

        else:

            spoken = (
                f"{hours} hour"
                f"{'s' if hours != 1 else ''}"
            )

        return {
            "seconds":
                seconds,

            "spoken":
                spoken,
        }

    # ========================================================
    # 3. SINGLE MINUTES
    #
    # This comes AFTER range detection.
    # ========================================================

    match = re.search(
        r"(?<!\d)"
        r"(\d+)"
        r"\s*"
        r"(?:minutes?|mins?)"
        r"\b",
        normalized,
    )

    if match:

        minutes = int(
            match.group(1)
        )

        return {
            "seconds":
                minutes * 60,

            "spoken":
                (
                    f"{minutes} minute"
                    f"{'s' if minutes != 1 else ''}"
                ),
        }

    # ========================================================
    # 4. SECONDS
    # ========================================================

    match = re.search(
        r"(?<!\d)"
        r"(\d+)"
        r"\s*"
        r"(?:seconds?|secs?)"
        r"\b",
        normalized,
    )

    if match:

        seconds = int(
            match.group(1)
        )

        return {
            "seconds":
                seconds,

            "spoken":
                (
                    f"{seconds} second"
                    f"{'s' if seconds != 1 else ''}"
                ),
        }

    return None