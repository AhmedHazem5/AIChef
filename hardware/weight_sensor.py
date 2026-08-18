import time

from gpiozero import (
    DigitalInputDevice,
    DigitalOutputDevice,
)


DOUT_PIN = 5
SCK_PIN = 6

CALIBRATION_FACTOR = -192.5709


class WeightSensor:
    def __init__(
        self,
        calibration_factor: float = CALIBRATION_FACTOR,
    ):

        self.calibration_factor = (
            calibration_factor
        )

        self.dout = DigitalInputDevice(
            DOUT_PIN,
            pull_up=False,
        )

        self.sck = DigitalOutputDevice(
            SCK_PIN,
            initial_value=False,
        )

        self.zero_offset = 0.0

    def read_raw(
        self,
    ) -> int:

        timeout = (
            time.time()
            + 2.0
        )

        while self.dout.value == 1:

            if (
                time.time()
                > timeout
            ):

                raise TimeoutError(
                    "HX711 did not become ready."
                )

            time.sleep(
                0.001
            )

        value = 0

        for _ in range(24):

            self.sck.on()

            value <<= 1

            self.sck.off()

            if self.dout.value:

                value += 1

        # 25th clock:
        # Channel A
        # Gain 128
        self.sck.on()
        self.sck.off()

        # Convert from signed
        # 24-bit value.
        if value & 0x800000:

            value -= (
                1 << 24
            )

        return value

    def average_raw(
        self,
        samples: int = 15,
    ) -> float:

        values = []

        for _ in range(
            samples
        ):

            values.append(
                self.read_raw()
            )

            time.sleep(
                0.02
            )

        return (
            sum(values)
            / len(values)
        )

    def tare(
        self,
        samples: int = 25,
    ) -> None:

        print(
            "[SCALE] Taring..."
        )

        self.zero_offset = (
            self.average_raw(
                samples=samples
            )
        )

        print(
            f"[SCALE] Zero offset: "
            f"{self.zero_offset:.2f}"
        )

    def get_weight(
        self,
        samples: int = 10,
    ) -> float:

        raw = self.average_raw(
            samples=samples
        )

        grams = (
            raw
            - self.zero_offset
        ) / self.calibration_factor

        # Ignore tiny noise around zero.
        if abs(
            grams
        ) < 2.0:

            grams = 0.0

        return grams

    def wait_for_target(
        self,
        target_grams: float,
        tolerance_grams: float = 3.0,
        display=None,
    ) -> float:
        """
        Block until the measured weight
        reaches approximately the requested
        target.

        Returns the final measured weight.
        """

        print(
            f"[SCALE] Target: "
            f"{target_grams:.1f} g"
        )

        print(
            f"[SCALE] Tolerance: "
            f"±{tolerance_grams:.1f} g"
        )

        stable_hits = 0

        while True:

            weight = (
                self.get_weight(
                    samples=8
                )
            )

            if display is not None:
                display.show_weight_progress(
                    current_grams=weight,
                    target_grams=target_grams,
                )

            print(
                f"\r[SCALE] "
                f"{weight:.1f} g / "
                f"{target_grams:.1f} g",
                end="",
                flush=True,
            )

            difference = (
                abs(
                    weight
                    - target_grams
                )
            )

            if (
                difference
                <= tolerance_grams
            ):

                stable_hits += 1

            else:

                stable_hits = 0

            # Require several consecutive
            # readings to avoid accepting
            # a transient value.
            if stable_hits >= 3:

                print()

                print(
                    "[SCALE] "
                    "Target reached."
                )

                if display is not None:
                    display.show_weight_done(
                        final_grams=weight,
                    )

                    time.sleep(
                        2.0
                    )

                    display.restore_previous_screen()

                return weight

            time.sleep(
                0.15
            )

    def close(
        self,
    ) -> None:

        self.sck.close()
        self.dout.close()


_weight_sensor = None


def get_weight_sensor(
) -> WeightSensor:

    global _weight_sensor

    if (
        _weight_sensor
        is None
    ):

        _weight_sensor = (
            WeightSensor()
        )

    return _weight_sensor