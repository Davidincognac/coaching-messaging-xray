"""Parsing a multipart/form-data body without trusting a word of it.

This is the only place in the app where a stranger hands us raw bytes and we have to be right
about them, so everything here is bounded before it is read and checked before it is believed.

Python 3.13 removed cgi.FieldStorage, so there is no stdlib parser to lean on. That is not much
of a loss: FieldStorage would happily write attacker-named temporary files and had no useful caps.
What follows has a limit on every axis an attacker controls, which is the whole point.

The caps, and the reason for each:

  body        a body bigger than the cap is refused on Content-Length, before a byte is read,
              so nobody can make us allocate memory just by claiming a size
  parts       a body of ten thousand empty parts costs nothing to send and a lot to parse
  headers     a single part header of 10MB is the same attack wearing a hat
  field       text fields are names and short prose; 64KB is already absurdly generous
  files       exactly one, because we only ever want one, and the cap lives in banner_image

Two things this deliberately does NOT do. It never uses the filename the browser sent, for
anything, not even to pick an extension; banner_image names the file from the lead token. And it
never believes a part's Content-Type: an upload claiming image/png is still handed to Pillow to
open before we treat it as an image.
"""
import re

MAX_PARTS = 12
MAX_PART_HEADER_BYTES = 4096
MAX_FIELD_BYTES = 64 * 1024

# RFC 2046: 1 to 70 characters from a fixed set. Anything else is not a boundary we will honour.
_BOUNDARY_OK = re.compile(rb"^[0-9A-Za-z'()+_,\-./:=? ]{1,70}$")
_NAME = re.compile(r'name="([^"\r\n]*)"', re.I)
_FILENAME = re.compile(r'filename="([^"\r\n]*)"', re.I)


class BadForm(Exception):
    """The body was not a multipart form we can use. Message is safe to show a person."""


def boundary_from(content_type):
    """Pull the boundary out of a Content-Type header, or refuse.

    A missing or malformed boundary is a refusal rather than a guess. There is no safe default.
    """
    ct = (content_type or "")
    if not ct.lower().startswith("multipart/form-data"):
        raise BadForm("That form did not arrive in a format we can read.")
    m = re.search(r'boundary=(?:"([^"]+)"|([^\s;]+))', ct, re.I)
    if not m:
        raise BadForm("That form did not arrive in a format we can read.")
    b = (m.group(1) or m.group(2)).encode("latin-1", "replace")
    if not _BOUNDARY_OK.match(b):
        raise BadForm("That form did not arrive in a format we can read.")
    return b


def parse(raw, boundary):
    """Split the body into parts. Returns (fields, files).

    fields is {name: text} and files is {name: bytes}. A repeated name keeps the FIRST value,
    so nobody can smuggle a second value past a check that only looked at one.
    """
    if not raw:
        raise BadForm("That form arrived empty. Try again.")
    sep = b"--" + boundary
    # Prefixing CRLF means the opening boundary and every later one have the same shape, so one
    # split handles all of them and there is no special case to get wrong.
    chunks = (b"\r\n" + raw).split(b"\r\n" + sep)
    if len(chunks) < 2:
        raise BadForm("That form did not arrive in a format we can read.")
    if len(chunks) - 1 > MAX_PARTS + 1:
        raise BadForm("That form had too many fields in it.")

    fields, files = {}, {}
    for chunk in chunks[1:]:
        if chunk.startswith(b"--"):
            break                       # the closing boundary; anything after it is epilogue
        if not chunk.startswith(b"\r\n"):
            continue                    # not a part we recognise, so not a part we act on
        chunk = chunk[2:]
        split = chunk.find(b"\r\n\r\n")
        if split < 0 or split > MAX_PART_HEADER_BYTES:
            raise BadForm("That form did not arrive in a format we can read.")
        head = chunk[:split].decode("latin-1", "replace")
        body = chunk[split + 4:]

        disp = ""
        for line in head.split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                disp = line
                break
        if not disp:
            continue
        m = _NAME.search(disp)
        if not m:
            continue
        name = m.group(1)[:64]
        is_file = _FILENAME.search(disp) is not None

        if is_file:
            if name not in files:
                files[name] = body          # the size cap for a file lives in banner_image
        else:
            if len(body) > MAX_FIELD_BYTES:
                raise BadForm("One of those fields was far too long.")
            if name not in fields:
                fields[name] = body.decode("utf-8", "replace")
    return fields, files


# Control characters have no business in a name, an email or a line of a coach's bio. Tabs and
# newlines are stripped rather than refused, because a coach pasting a bio will bring newlines
# with them and that is not an attack, it is a paste.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def text(fields, name, limit, keep_newlines=False):
    """One text field, cleaned and capped. Always returns a string, never None."""
    v = fields.get(name, "") or ""
    v = _CONTROL.sub("", v)
    # Normalise line endings first. Replacing \r and \n separately turns one CRLF into two spaces,
    # which is how a pasted bio picks up double gaps it never had.
    v = v.replace("\r\n", "\n").replace("\r", "\n")
    if not keep_newlines:
        v = v.replace("\n", " ")
    return v.strip()[:limit]
