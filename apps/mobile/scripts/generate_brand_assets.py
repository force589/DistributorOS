from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
BLUE = "#155EEF"
WHITE = "#FFFFFF"


def draw_mark(image: Image.Image, *, inset: int, background: str | None) -> None:
    draw = ImageDraw.Draw(image)
    size = image.width
    if background:
        draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=size * 0.22, fill=background)
    scale = (size - inset * 2) / 1024

    def box(values: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
        return tuple(inset + value * scale for value in values)  # type: ignore[return-value]

    draw.rounded_rectangle(box((286, 248, 784, 776)), radius=120 * scale, fill=WHITE)
    draw.rounded_rectangle(box((402, 364, 664, 660)), radius=100 * scale, fill=BLUE)
    draw.rounded_rectangle(box((446, 410, 544, 492)), radius=18 * scale, fill=WHITE)
    draw.rounded_rectangle(box((544, 508, 642, 590)), radius=18 * scale, fill=WHITE)
    line_width = max(2, round(12 * scale))
    for line in (
        (446, 451, 544, 451),
        (495, 410, 495, 492),
        (544, 549, 642, 549),
        (593, 508, 593, 590),
    ):
        draw.line(box(line), fill=BLUE, width=line_width)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = Image.new("RGB", (1024, 1024), BLUE)
    draw_mark(icon, inset=0, background=BLUE)
    icon.save(ASSETS / "icon.png", optimize=True)

    foreground = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw_mark(foreground, inset=144, background=None)
    foreground.save(ASSETS / "adaptive-icon.png", optimize=True)

    splash = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw_mark(splash, inset=150, background=BLUE)
    splash.save(ASSETS / "splash-icon.png", optimize=True)

    favicon = icon.resize((64, 64), Image.Resampling.LANCZOS)
    favicon.save(ASSETS / "favicon.png", optimize=True)


if __name__ == "__main__":
    main()
