"""Turning a coach's uploaded screenshot into something we can store and show.

Measured against nine real coach banners (David's own plus eight he collected). At 1600px on the
long edge and WebP quality 80 they went from 14.7MB to 584KB, roughly thirty times smaller, and
the hardest cases were checked by eye at magnification: fine gold linework on dark purple, a
serif over a pink gradient, condensed caps with a tiny trademark symbol, and a sunset photo. None
of them showed a visible difference against the original. WebP beat JPEG about two to one on
every single file.

1600 rather than 1400 because a phone upload arrives portrait. A tall screenshot capped on its
long edge ends up narrow, and the width is what carries the text. 1600 costs about 10KB per
image and gives a phone shot 739px of width instead of 647px.

Two things this does beyond shrinking. It applies the rotation a phone records in EXIF, so a
photo taken sideways is stored the right way up. And because it re-encodes rather than copies,
every scrap of EXIF is dropped, which matters because a phone photo can carry the location it
was taken at, and we have no business storing that.
"""
import io
import os

from PIL import Image, ImageOps

MAX_UPLOAD_BYTES = 10 * 1024 * 1024    # generous: the biggest real one we saw was 2.8MB
LONG_EDGE = 1600
QUALITY = 80


class BadImage(Exception):
    """The upload was not an image we can use. The message is safe to show the coach."""


def process(raw):
    """Take the raw bytes of an upload, hand back WebP bytes ready to store.

    Raises BadImage with a sentence a coach can understand, never a stack trace.
    """
    if not raw:
        raise BadImage("That file was empty. Try the upload again.")
    if len(raw) > MAX_UPLOAD_BYTES:
        mb = len(raw) / 1024 / 1024
        raise BadImage(f"That image is {mb:.0f}MB, which is bigger than we can take. "
                       "A screenshot is usually well under 10MB.")
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:
        raise BadImage("We couldn't read that file as an image. A PNG or a JPG works best.")

    im = ImageOps.exif_transpose(im)          # a sideways phone photo comes out the right way up
    im = im.convert("RGB")                    # also drops any transparency WebP would keep
    w, h = im.size
    if max(w, h) > LONG_EDGE:
        s = LONG_EDGE / max(w, h)
        im = im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)

    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=QUALITY, method=6)
    return buf.getvalue()


def save_for(token, raw, uploads_dir):
    """Process and write it. Returns the bare filename, which is what goes in the database.

    Named from the token, so a coach who uploads twice replaces their own file rather than
    littering the disk, and one lead can never overwrite another's.
    """
    data = process(raw)
    safe = "".join(c for c in token if c.isalnum() or c in "-_")[:64]
    if not safe:
        raise BadImage("Something went wrong saving that. Try the upload again.")
    name = f"{safe}.webp"
    os.makedirs(uploads_dir, exist_ok=True)
    with open(os.path.join(uploads_dir, name), "wb") as f:
        f.write(data)
    return name
