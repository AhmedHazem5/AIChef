import time

import board
import digitalio

from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import st7735


spi = board.SPI()

dc_pin = digitalio.DigitalInOut(
    board.D24
)

reset_pin = digitalio.DigitalInOut(
    board.D25
)


display = st7735.ST7735R(
    spi,
    cs=None,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=24000000,
    width=128,
    height=160,
    rotation=0,
)


image = Image.new(
    "RGB",
    (display.width, display.height),
    "black",
)

draw = ImageDraw.Draw(
    image
)

font = ImageFont.load_default()

draw.rectangle(
    (
        2,
        2,
        display.width - 3,
        display.height - 3,
    ),
    outline="white",
    width=2,
)

draw.text(
    (40, 40),
    "ChefAI",
    font=font,
    fill="white",
)

draw.text(
    (30, 70),
    "TFT WORKING",
    font=font,
    fill="white",
)

draw.text(
    (34, 100),
    "128 x 160",
    font=font,
    fill="white",
)

display.image(
    image
)

print("TFT test image displayed.")

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nTFT test stopped.")
