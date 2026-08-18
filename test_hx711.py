from gpiozero import DigitalInputDevice, DigitalOutputDevice
import time


# BCM GPIO numbers
DOUT_PIN = 5
SCK_PIN = 6


dout = DigitalInputDevice(
    DOUT_PIN,
    pull_up=False,
)

sck = DigitalOutputDevice(
    SCK_PIN,
    initial_value=False,
)


def read_raw():
    # Wait until HX711 says data is ready.
    # DOUT becomes LOW when a conversion is ready.
    timeout = time.time() + 2

    while dout.value == 1:
        if time.time() > timeout:
            raise TimeoutError(
                "HX711 did not become ready."
            )

        time.sleep(0.001)

    value = 0

    # Read 24 bits
    for _ in range(24):

        sck.on()

        value = (
            value << 1
        )

        sck.off()

        if dout.value:
            value += 1

    # 25th pulse:
    # select Channel A, gain 128
    sck.on()
    sck.off()

    # Convert 24-bit signed value
    if value & 0x800000:
        value -= 1 << 24

    return value


try:

    print("HX711 raw test")
    print("Press Ctrl+C to stop.\n")

    while True:

        raw = read_raw()

        print(
            f"Raw: {raw}"
        )

        time.sleep(0.3)

except KeyboardInterrupt:
    print("\nStopped.")

finally:
    sck.close()
    dout.close()