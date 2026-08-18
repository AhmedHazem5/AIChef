import time
import board
import digitalio

BUZZER_PIN = board.D17

buzzer = digitalio.DigitalInOut(BUZZER_PIN)
buzzer.direction = digitalio.Direction.OUTPUT

try:
    print("Buzzer ON")
    buzzer.value = True
    time.sleep(2)

    print("Buzzer OFF")
    buzzer.value = False
    time.sleep(1)

    print("Three short beeps")

    for _ in range(3):
        buzzer.value = True
        time.sleep(0.3)

        buzzer.value = False
        time.sleep(0.3)

    print("Done")

finally:
    buzzer.value = False
    buzzer.deinit()