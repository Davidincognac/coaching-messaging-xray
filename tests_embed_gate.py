import sys, os, pathlib
APP="/Users/davidpoole/Documents/claude/Projects/10,000 websites/coach_audit_app"
sys.path.insert(0, APP); os.chdir(APP)
import audit as a
from playwright.sync_api import sync_playwright
uri = pathlib.Path("test_embed.html").resolve().as_uri()
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1200,"height":800})
    pg.goto(uri); pg.wait_for_timeout(800)
    html=pg.content(); bt=pg.inner_text("body")
    optin_af=bool(pg.evaluate(r"""() => {
      const el=document.querySelector('input[type=email], input[name*="email" i], input[placeholder*="email" i]');
      if(!el) return false;
      const r=el.getBoundingClientRect();
      const inModal=!!el.closest('[role=dialog], .modal, .popup, [class*="modal"], [class*="popup"], [class*="overlay"]');
      return r.top>=0 && r.top<(window.innerHeight||800) && !inModal && r.width>0 && r.height>0;
    }"""))
    b.close()
has_embed=bool(a._BOOKING_EMBED_RE.search(html))
print("=== DETECTION on the mock DOM (real regex + real position pass) ===")
print(f"  _BOOKING_EMBED_RE match (live calendar iframe): {has_embed}")
print(f"  optin_inline_above_fold (inline form, top viewport, not modal): {optin_af}")
row={"body_text":bt,"clean_text":bt,"has_booking_embed":has_embed,"optin_inline_above_fold":optin_af,"optin_present":"yes"}
bk=a.detect_booking(row); caps=a.build_captures(row); oc=caps.get("opt_in") or {}
bk_base=a.booking_score(bk); opt_base=a.opt_in_score(oc)
print("\n=== REAL DETECT FUNCTIONS ===")
print(f"  detect_booking -> kind={bk.get('kind') if bk else None}  booking_score(base)={bk_base}")
print(f"  opt_in cap -> kind={oc.get('kind')}  inline_above_fold={oc.get('inline_above_fold')}  buried={oc.get('buried')}  opt_in_score(base)={opt_base}")
def gate(base, is_tech, clar, spec):
    return base if not (is_tech and base==8) else (10 if (clar>=5 and spec>=5) else 5)
print("\n=== GATE (binary): VAGUE copy clarity=3, spec=3  vs  STRONG copy clarity=7, spec=7 ===")
for label,(cl,sp) in [("VAGUE (3,3)",(3,3)),("STRONG (7,7)",(7,7))]:
    bkf=gate(bk_base, bk and bk.get('kind')=='booking_live', cl, sp)
    opf=gate(opt_base, oc.get('kind')=='magnet' and oc.get('inline_above_fold'), cl, sp)
    print(f"  {label}: booking {bk_base}->{bkf}   opt_in {opt_base}->{opf}")
