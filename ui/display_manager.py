import board
import digitalio

from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import st7735


class DisplayManager:
    def __init__(self):
        self.spi = board.SPI()

        self.dc_pin = digitalio.DigitalInOut(
            board.D24
        )

        self.reset_pin = digitalio.DigitalInOut(
            board.D25
        )

        self.display = st7735.ST7735R(
            self.spi,
            cs=None,
            dc=self.dc_pin,
            rst=self.reset_pin,
            baudrate=24_000_000,
            width=128,
            height=160,
            rotation=0,
        )

        self.width = self.display.width
        self.height = self.display.height

        self.font = ImageFont.load_default()

        self.show_idle()

    def _new_image(self):
        return Image.new(
            "RGB",
            (self.width, self.height),
            "black",
        )

    def _draw_centered(
        self,
        draw,
        text,
        y,
    ):
        bbox = draw.textbbox(
            (0, 0),
            text,
            font=self.font,
        )

        text_width = (
            bbox[2] - bbox[0]
        )

        x = (
            self.width
            - text_width
        ) // 2

        draw.text(
            (x, y),
            text,
            font=self.font,
            fill="white",
        )

    def _show(self, image):
        self.display.image(
            image
        )

    def show_idle(self):
        image = Image.new(
            "RGB",
            (self.width, self.height),
            "blue",
        )

        draw = ImageDraw.Draw(image)

        self._draw_centered(
            draw,
            "ChefAI",
            30,
        )

        self._draw_centered(
            draw,
            'Say "Hey Chef"',
            70,
        )

        self._show(image)


    def show_listening(self):
        image = Image.new(
            "RGB",
            (self.width, self.height),
            "green",
        )

        draw = ImageDraw.Draw(image)

        self._draw_centered(
            draw,
            "LISTENING",
            70,
        )

        self._show(image)


    def show_thinking(self):
        image = Image.new(
            "RGB",
            (self.width, self.height),
            "red",
        )

        draw = ImageDraw.Draw(image)

        self._draw_centered(
            draw,
            "THINKING",
            70,
        )

        self._show(image)

    def show_cooking_step(
        self,
        recipe_title: str,
        step_number: int,
        total_steps: int,
        step_text: str,
    ):
        image = Image.new(
            "RGB",
            (self.width, self.height),
            "purple",
        )
        draw = ImageDraw.Draw(image)

        draw.text(
            (5, 5),
            recipe_title[:18],
            font=self.font,
            fill="white",
        )

        draw.text(
            (5, 25),
            f"Step {step_number}/{total_steps}",
            font=self.font,
            fill="white",
        )

        # Very simple wrapping for now.
        words = step_text.split()

        lines = []
        current_line = ""

        for word in words:
            test_line = (
                current_line
                + " "
                + word
            ).strip()

            if len(test_line) <= 20:
                current_line = (
                    test_line
                )

            else:
                lines.append(
                    current_line
                )

                current_line = word

        if current_line:
            lines.append(
                current_line
            )

        y = 50

        for line in lines[:6]:
            draw.text(
                (5, y),
                line,
                font=self.font,
                fill="white",
            )

            y += 16

        self._show(image)