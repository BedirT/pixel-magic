from PIL import Image, ImageDraw

from pixel_magic.extract import extract_sprites


def _sprite_color(sprite: Image.Image) -> tuple[int, int, int, int]:
    for y in range(sprite.height):
        for x in range(sprite.width):
            pixel = sprite.getpixel((x, y))
            if pixel[3] > 0:
                return pixel
    raise AssertionError("sprite had no non-transparent pixels")


def test_extract_sprites_uses_row_major_order_for_centered_second_row() -> None:
    image = Image.new("RGBA", (360, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    boxes = [
        ((20, 20, 60, 100), (255, 0, 0, 255)),
        ((130, 24, 170, 104), (0, 255, 0, 255)),
        ((240, 18, 280, 98), (0, 0, 255, 255)),
        ((75, 128, 115, 208), (255, 255, 0, 255)),
        ((185, 132, 225, 212), (255, 0, 255, 255)),
    ]

    for (x0, y0, x1, y1), color in boxes:
        draw.rectangle((x0, y0, x1, y1), fill=color)

    sprites = extract_sprites(image, expected_count=5)

    assert [_sprite_color(sprite) for sprite in sprites] == [
        (255, 0, 0, 255),
        (0, 255, 0, 255),
        (0, 0, 255, 255),
        (255, 255, 0, 255),
        (255, 0, 255, 255),
    ]
