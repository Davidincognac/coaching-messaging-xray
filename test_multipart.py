"""Adversarial tests for the multipart parser. Every one of these is a thing a stranger can send."""
import multipart as mp

B = b"----WebKitFormBoundaryAbC123"
CT = 'multipart/form-data; boundary=----WebKitFormBoundaryAbC123'
ok = fail = 0


def check(label, cond):
    global ok, fail
    if cond:
        ok += 1; print(f"  pass  {label}")
    else:
        fail += 1; print(f"  FAIL  {label}")


def refuses(label, fn):
    global ok, fail
    try:
        fn(); fail += 1; print(f"  FAIL  {label}  (accepted it)")
    except mp.BadForm:
        ok += 1; print(f"  pass  {label}")
    except Exception as e:
        fail += 1; print(f"  FAIL  {label}  (wrong error {type(e).__name__}: {e})")


def part(name, value, filename=None):
    d = f'form-data; name="{name}"'
    if filename is not None:
        d += f'; filename="{filename}"'
    return (b"--" + B + b"\r\nContent-Disposition: " + d.encode()
            + b"\r\n\r\n" + (value if isinstance(value, bytes) else value.encode()))


def body(*parts):
    return b"\r\n".join(parts) + b"\r\n--" + B + b"--\r\n"


print("=== the normal case ===")
f, files = mp.parse(body(part("bio", "I coach women"), part("banner", b"\x89PNG\x00\x01", "shot.png")), B)
check("text field read", f.get("bio") == "I coach women")
check("file bytes read exactly", files.get("banner") == b"\x89PNG\x00\x01")
check("file is not in fields", "banner" not in f)

print("\n=== the boundary header ===")
check("plain boundary", mp.boundary_from(CT) == B)
check("quoted boundary", mp.boundary_from('multipart/form-data; boundary="abc"') == b"abc")
check("charset after boundary", mp.boundary_from('multipart/form-data; boundary=abc; charset=utf-8') == b"abc")
refuses("no boundary at all", lambda: mp.boundary_from("multipart/form-data"))
refuses("not multipart", lambda: mp.boundary_from("application/x-www-form-urlencoded"))
refuses("empty content-type", lambda: mp.boundary_from(""))
refuses("boundary over 70 chars", lambda: mp.boundary_from("multipart/form-data; boundary=" + "a"*71))
refuses("boundary with newline", lambda: mp.boundary_from('multipart/form-data; boundary="a\r\nb"'))
refuses("boundary with null", lambda: mp.boundary_from('multipart/form-data; boundary="a\x00b"'))

print("\n=== bodies built to hurt ===")
refuses("empty body", lambda: mp.parse(b"", B))
refuses("no boundary present", lambda: mp.parse(b"just some bytes", B))
refuses("10,000 parts", lambda: mp.parse(body(*[part(f"f{i}", "x") for i in range(10000)]), B))
refuses("4MB part header", lambda: mp.parse(
    b"--" + B + b"\r\nContent-Disposition: form-data; name=\"a\"" + b"X"*(4*1024*1024)
    + b"\r\n\r\nv\r\n--" + B + b"--\r\n", B))
refuses("1MB text field", lambda: mp.parse(body(part("bio", "x"*(1024*1024))), B))
check("exactly at the part cap is allowed",
      len(mp.parse(body(*[part(f"f{i}", "x") for i in range(mp.MAX_PARTS)]), B)[0]) == mp.MAX_PARTS)

print("\n=== things that must be ignored, not obeyed ===")
f, files = mp.parse(body(part("bio", "first"), part("bio", "second")), B)
check("duplicate field keeps the first", f.get("bio") == "first")
f, files = mp.parse(body(part("banner", b"one", "a.png"), part("banner", b"two", "b.png")), B)
check("duplicate file keeps the first", files.get("banner") == b"one")
f, files = mp.parse(body(part("banner", b"data", "../../../etc/passwd")), B)
check("traversal filename is never surfaced", files.get("banner") == b"data" and len(files) == 1)
f, _ = mp.parse(body(b"--" + B + b"\r\nContent-Type: text/plain\r\n\r\nno disposition"), B)
check("part with no Content-Disposition skipped", f == {})
f, _ = mp.parse(body(b"--" + B + b"\r\nContent-Disposition: form-data\r\n\r\nno name"), B)
check("part with no name skipped", f == {})
f, _ = mp.parse(body(part("a"*500, "v")), B)
check("absurd field name is capped", len(list(f)[0]) == 64)

print("\n=== the empty-file case a browser really sends ===")
f, files = mp.parse(body(part("bio", "hi"), part("banner", b"", "")), B)
check("no file chosen gives empty bytes, not an error", files.get("banner") == b"")
check("caller can tell the difference with a truthiness check", not files.get("banner"))

print("\n=== text cleaning ===")
f, _ = mp.parse(body(part("bio", "hello\x00\x07 there\x1f")), B)
check("control characters stripped", mp.text(f, "bio", 200) == "hello there")
f, _ = mp.parse(body(part("bio", "line one\r\nline two")), B)
check("newlines flattened by default", mp.text(f, "bio", 200) == "line one line two")
check("newlines kept when asked", mp.text(f, "bio", 200, keep_newlines=True) == "line one\nline two")
f, _ = mp.parse(body(part("bio", "  padded  ")), B)
check("trimmed", mp.text(f, "bio", 200) == "padded")
f, _ = mp.parse(body(part("bio", "abcdefghij")), B)
check("capped to the limit", mp.text(f, "bio", 4) == "abcd")
check("missing field gives empty string", mp.text({}, "nope", 10) == "")
f, _ = mp.parse(body(part("bio", "café ☕ naïve")), B)
check("unicode survives", mp.text(f, "bio", 200) == "café ☕ naïve")
f, _ = mp.parse(body(part("bio", b"\xff\xfe invalid utf8")), B)
check("invalid utf-8 does not crash", isinstance(mp.text(f, "bio", 200), str))

print("\n=== malformed but must not crash ===")
for label, raw in [("truncated mid-part", b"--" + B + b"\r\nContent-Disposition: form-data; name=\"a\"\r\n\r\nval"),
                   ("no closing boundary", body(part("a", "v"))[:-10]),
                   ("LF line endings only", body(part("a", "v")).replace(b"\r\n", b"\n")),
                   ("boundary-like text inside a value", body(part("a", "--" + B.decode() + "x"))),
                   ("just the closing boundary", b"--" + B + b"--\r\n")]:
    try:
        mp.parse(raw, B); print(f"  pass  {label} (parsed, no crash)"); ok += 1
    except mp.BadForm: print(f"  pass  {label} (refused cleanly)"); ok += 1
    except Exception as e: print(f"  FAIL  {label} -> {type(e).__name__}: {e}"); fail += 1

print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
