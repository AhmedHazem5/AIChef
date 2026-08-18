from gpiozero import DigitalInputDevice, DigitalOutputDevice
import time


DOUT_PIN = 5
SCK_PIN = 6

ZERO_OFFSET = -308677.95
CALIBRATION_FACTOR = -192.5709


dout = DigitalInputDevice(
    DOUT_PIN,
    pull_up=False,
)

sck = DigitalOutputDevice(
    SCK_PIN,
    initial_value=False,
)


def read_raw():

    timeout = time.time() + 2

    while dout.value == 1:

        if time.time() > timeout:
            raise TimeoutError(
                "HX711 did not become ready."
            )

        time.sleep(0.001)

    value = 0

    for _ in range(24):

        sck.on()

        value <<= 1

        sck.off()

        if dout.value:
            value += 1

    sck.on()
    sck.off()

    if value & 0x800000:
        value -= 1 << 24

    return value


def average_raw(
    samples=20,
):

    values = []

    for _ in range(samples):

        values.append(
            read_raw()
        )

        time.sleep(
            0.02
        )

    return (
        sum(values)
        / len(values)
    )


def get_weight():

    raw = average_raw()

    grams = (
        raw - ZERO_OFFSET
    ) / CALIBRATION_FACTOR

    # Ignore tiny zero drift.
    if abs(grams) < 2:
        grams = 0.0

    return raw, grams


try:

    print(
        "HX711 WEIGHT TEST"
    )

    print(
        "Press Ctrl+C to stop.\n"
    )

    while True:

        raw, grams = (
            get_weight()
        )

        print(
            f"Raw: {raw:.0f} | "
            f"Weight: {grams:.1f} g"
        )

        time.sleep(
            0.25
        )

except KeyboardInterrupt:

    print(
        "\nStopped."
    )

finally:

    sck.close()
    dout.close()