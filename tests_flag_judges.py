import sys, os
APP="/Users/davidpoole/Documents/claude/Projects/10,000 websites/coach_audit_app"
sys.path.insert(0, APP); os.chdir(APP)
for line in open(".env"):
    line=line.strip()
    if line and "=" in line and not line.startswith("#"):
        k,v=line.split("=",1); os.environ[k]=v.strip().strip('"').strip("'")
from audit import judge_specificity, judge_clarity, _flag, _as_int, FLAG_CRIT

print("=== GATES: generic phrase 'I help individuals overcome overwhelm and unlock potential' ===")
gspec={"specific_demographic":False,"demographic_quote":"","concrete_pain":False,"pain_quote":"",
       "unique_mechanism":False,"mechanism_quote":"","generic_tokens":["individuals","overwhelm","potential"],
       "distinct_audiences_or_problems":1}
gclar={"hero_quote":"I help individuals overcome overwhelm and unlock potential","hero_specific_audience":False,
       "hero_concrete_problem_or_outcome":False,"hero_names_field_or_category":True,
       "hero_is_metaphor_or_feeling_only":False,"hero_is_broad_everyone_appeal":True}
print(f"  specificity -> {judge_specificity(gspec)}  (expect 3: named-but-generic)")
print(f"  clarity     -> {judge_clarity(gclar)}  (expect 3: broad everyone-appeal)")
sspec={"specific_demographic":True,"demographic_quote":"newly-promoted eng managers","concrete_pain":True,
       "pain_quote":"work 70-hr weeks, can't delegate","unique_mechanism":True,"mechanism_quote":"90-day system",
       "generic_tokens":[],"distinct_audiences_or_problems":1}
print(f"  (counter) SPECIFIC -> {judge_specificity(sspec)}  (expect 9)")
bspec=dict(sspec, distinct_audiences_or_problems=4)
print(f"  (counter) BREADTH=4 -> {judge_specificity(bspec)}  (expect 3: hard cap)")

print("\n=== SAFEGUARD 1: malformed JSON never crashes + string coercion ===")
for t in [None,{},"not a dict",{"specific_demographic":"false"},{"specific_demographic":"true","concrete_pain":"yes"},
          {"distinct_audiences_or_problems":"3"},{"distinct_audiences_or_problems":None}]:
    try: print(f"  judge_specificity({str(t)[:42]:42}) -> {judge_specificity(t)}  (no crash)")
    except Exception as e: print(f"  CRASH on {t}: {e}")
print(f"  _flag('false')={_flag('false')} (must be False — naive bool('false') would be True); _flag('true')={_flag('true')}; _as_int('3')={_as_int('3')}")

print("\n=== SAFEGUARD 2: integration fail-safe keeps the proxy on bad/empty flags ===")
def merge(ai, proxy):
    scores={"specificity":proxy,"clarity_5sec":proxy}
    for c,(fk,j) in FLAG_CRIT.items():
        try:
            fl=ai.get(fk)
            if isinstance(fl,dict) and fl: scores[c]=max(0,min(10,int(j(fl))))
        except Exception: pass
    return scores
print(f"  empty AI payload {{}}        -> {merge({}, 4)}  (keeps proxy 4)")
print(f"  valid flags present        -> {merge({'specificity_flags':gspec,'clarity_flags':gclar}, 4)}  (judge fires)")
print(f"  malformed flags (str/None) -> {merge({'specificity_flags':'junk','clarity_flags':None}, 4)}  (keeps proxy 4)")
