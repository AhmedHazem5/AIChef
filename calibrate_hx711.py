from gpiozero import DigitalInputDevice, DigitalOutputDevice
import time


DOUT_PIN = 5
SCK_PIN = 6

KNOWN_WEIGHT_GRAMS = 199.0

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

    # 25th pulse = Channel A, gain 128
    sck.on()
    sck.off()

    if value & 0x800000:
        value -= 1 << 24

    return value


def average_reading(samples=20):

    readings = []

    for _ in range(samples):

        readings.append(
            read_raw()
        )

        time.sleep(0.05)

    return sum(readings) / len(readings)


try:

    print("\nHX711 CALIBRATION")
    print("=================\n")

    print(
        "Remove everything from the scale."
    )

    input(
        "Press ENTER when the scale is empty..."
    )

    print("\nMeasuring zero...")

    zero = average_reading()

    print(
        f"Zero raw value: {zero:.2f}"
    )

    print(
        f"\nNow place the {KNOWN_WEIGHT_GRAMS:.0f} g "
        "known weight on the scale."
    )

    input(
        "Press ENTER when the weight is stable..."
    )

    print("\nMeasuring known weight...")

    loaded = average_reading()

    print(
        f"Loaded raw value: {loaded:.2f}"
    )

    difference = loaded - zero

    calibration_factor = (
        difference / KNOWN_WEIGHT_GRAMS
    )

    print("\n=================")
    print("CALIBRATION RESULT")
    print("=================")

    print(
        f"Zero offset: {zero:.2f}"
    )

    print(
        f"Raw difference: {difference:.2f}"
    )

    print(
        f"Calibration factor: "
        f"{calibration_factor:.4f} counts/gram"
    )

    print(
        "\nSave the calibration factor."
    )

finally:

    sck.close()
    dout.close()