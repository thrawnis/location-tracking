"""Self-contained image CAPTCHA for registration.

No third-party service, keys, or outbound calls — renders distorted text with
Pillow (already a dependency) and checks the answer against the session. It
won't stop a determined OCR attacker, but it makes scripted mass account
creation costly, which is the point (each new account is the only way past the
login wall that fronts all data).
"""

import io
import random
import secrets

from PIL import Image, ImageDraw, ImageFont

# Ambiguous characters (0/O, 1/I/L) are excluded so the challenge is readable.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CAPTCHA_LEN = 5
CAPTCHA_TTL = 600          # seconds a served challenge stays valid
SESSION_ANSWER = "captcha_answer"
SESSION_TIME = "captcha_time"


def make_text():
    """A fresh challenge string (cryptographically random)."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(CAPTCHA_LEN))


def render_image(text):
    """Render `text` as a noisy, per-character-rotated PNG; return the bytes."""
    W, H = 200, 70
    img = Image.new("RGB", (W, H), (243, 244, 246))
    draw = ImageDraw.Draw(img)

    # Background noise lines.
    for _ in range(6):
        draw.line(
            [(random.randint(0, W), random.randint(0, H)),
             (random.randint(0, W), random.randint(0, H))],
            fill=(random.randint(150, 205),) * 3, width=1,
        )

    try:
        font = ImageFont.load_default(size=40)   # Pillow >= 10 bundles a scalable default
    except TypeError:
        font = ImageFont.load_default()

    x = 14
    for ch in text:
        cell = Image.new("RGBA", (46, 62), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(cell)
        color = (random.randint(20, 90), random.randint(20, 90), random.randint(90, 170))
        cdraw.text((7, 4), ch, font=font, fill=color)
        cell = cell.rotate(random.randint(-28, 28), expand=1, resample=Image.BICUBIC)
        img.paste(cell, (x, random.randint(0, 12)), cell)
        x += 34

    # Foreground speckle noise.
    for _ in range(200):
        draw.point((random.randint(0, W), random.randint(0, H)),
                   fill=(random.randint(120, 205),) * 3)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
