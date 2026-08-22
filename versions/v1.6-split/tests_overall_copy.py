import sys, os
sys.path.insert(0, "/Users/davidpoole/Documents/claude/Projects/10,000 websites/coach_audit_app")
os.chdir("/Users/davidpoole/Documents/claude/Projects/10,000 websites/coach_audit_app")
from app import overall_copy
PASS = ["gets it fast", "gets who you help fast", "can tell who you help", "reads like the answer", "gets who it's for"]
FAIL = ["can't quickly tell", "can't tell that you're", "doesn't tell them in five seconds", "doesn't tell them who",
        "isn't landing in five seconds", "still isn't landing", "doesn't yet", "doesn't see themselves",
        "still doesn't tell", "can't tell it's for them"]
tiers = ["strong","decent","weak","poor"]; bad=[]; n=0
for clarity in range(0,11):
    for tier in tiers:
        for top in (True, False):
            v,d,g = overall_copy(clarity, tier, top)
            blob = (v+" "+d+" "+g).lower()
            hp = any(p in blob for p in PASS); hf = any(f in blob for f in FAIL); rf = clarity>=6; n+=1
            if hp and hf: bad.append((clarity,tier,top,"BOTH pass AND fail phrase (contradiction)"))
            if rf and hf: bad.append((clarity,tier,top,"reads-fast page but says can't-tell"))
            if (not rf) and hp: bad.append((clarity,tier,top,"not-fast page but says gets-it-fast"))
print(f"tested {n} combinations (clarity 0-10 x 4 tiers x top/not-top)")
print("CONTRADICTIONS:", len(bad))
for b in bad[:20]: print("  X", b)
print()
for lbl,args in [("believe (clarity 7, weak, top)",(7,"weak",True)),
                 ("Joy-ish (clarity 4, weak, not-top)",(4,"weak",False)),
                 ("strong+clear (9, strong, top)",(9,"strong",True)),
                 ("clear but low (7, poor, not-top)",(7,"poor",False)),
                 ("unclear but top (4, decent, top)",(4,"decent",True))]:
    v,d,g = overall_copy(*args)
    print(f"[{lbl}]\n  VERDICT: {v[:95]}\n  GAP: {g.replace(chr(60)+'p'+chr(62),'').replace(chr(60)+'/p'+chr(62),' ')[:95]}\n")
