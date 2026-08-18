import time

import board
import digitalio


class BuzzerController:
    def __init__(self):

        self.pin = digitalio.DigitalInOut(
            board.D17
        )

        self.pin.direction = (
            digitalio.Direction.OUTPUT
        )

        self.pin.value = False

    def _beep(
        self,
        duration: float,
    ) -> None:

        self.pin.value = True

        time.sleep(
            duration
        )

        self.pin.value = False

    def timer_finished_alert(
        self,
    ) -> None:
        """
        One long beep followed by
        three short beeps.
        """

        # Long beep
        self._beep(
            2.0
        )

        time.sleep(
            0.5
        )

        # Three short beeps
        for index in range(3):

            self._beep(
                0.3
            )

            if index < 2:

                time.sleep(
                    0.3
                )

    def close(
        self,
    ) -> None:

        self.pin.value = False

        self.pin.deinit()


_buzzer = None


def get_buzzer() -> BuzzerController:

    global _buzzer

    if _buzzer is None:

        _buzzer = (
            BuzzerController()
        )

    return _buzzer