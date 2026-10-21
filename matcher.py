"""The three-question matcher behind the Buying Triggers page.

A coach answers three questions in their own words. After each one the model reads the answer back
in a line or two that describes the BUYER, and says whether the answer is too thin to match on. After
the third, the model picks the three or four closest markets off OUR list and gives one plain reason
each.

Two rules sit over everything here.

The model never invents a finding. It only ever routes a coach to research we already hold, so it is
handed the list of complete markets and can answer with nothing but ids off that list. Anything that
comes back off-list, or names a market we hold back, is dropped before it reaches a page.

And the model never speaks to the coach. Every line it writes is about the buyer. The prompts say so,
and the page copy around it says so, and check_copy.py polices the fixed copy. What the model writes
is scrubbed of the marks that give a machine away (asterisks, dashes) before it is shown.

Every call is a single request with a JSON schema on the output, so there is nothing to parse by
hand. The market list goes in the system prompt with a cache breakpoint on it, so the second coach
of the hour reads it off the cache at a tenth of the price. The logs print the usage of every call so
the cost is measured rather than guessed.
"""
import json
import os
import re
import time

import triggers as _t

_HERE = os.path.dirname(os.path.abspath(__file__))

# The app loads .env in audit.py. This module has to work on its own too (the cost measurement
# runs it from a shell), so it does the same cheap load here. setdefault means a real environment
# always wins.
_ENVF = os.path.join(_HERE, ".env")
if os.path.exists(_ENVF):
    for _line in open(_ENVF, encoding="utf-8"):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# The model the audit uses, or the current Sonnet when nothing is set.
MODEL = os.getenv("AUDIT_MODEL") or "claude-sonnet-5-5"

QUESTIONS = [
    {
        "key": "q_who",
        "ask": "Who do you coach?",
        "note": "Say it like you would to a friend, not how your website says it.",
        "hint": "mums going back to work after ten years off, blokes who just got divorced…",
    },
    {
        "key": "q_problem",
        "ask": "What do they come to you with?",
        "note": "Use the words they use, not yours.",
        "hint": "“I can’t switch off”, “I’ve tried everything”…",
    },
    {
        "key": "q_fix",
        "ask": "What do they think will fix it?",
        "note": "Not what you know they need. What they believe they are buying.",
        "hint": "a plan, someone to keep them on track, a way to stop the arguments…",
    },
]
KEYS = [q["key"] for q in QUESTIONS]

# Every answer is capped at this before it goes anywhere. A coach has no reason to type more, and a
# stranger has every reason to try.
ANSWER_LIMIT = 600


# ---------------------------------------------------------------------------------------------------
# The market list. Built once at import from the markets that pass is_complete(), and the ids are
# positions in that list, so an id can never point at a market we hold back.

def _build_markets():
    names = sorted(n for n in list(_t.NICHES) + list(_t.SUBNICHES) if _t.is_complete(n))
    out = []
    for i, name in enumerate(names):
        rec = _t.report_data(name)
        out.append({"id": i, "name": name, "audience": rec.get("audience", "") or "",
                    "parent": rec.get("parent", "") or ""})
    return out


# Built on first use, not at import: triggers.py imports this module for the question list, so
# building here at import would read triggers' data before triggers has finished loading.
_STATE = {}


def _ensure():
    if "markets" not in _STATE:
        markets = _build_markets()
        _STATE["markets"] = markets
        _STATE["by_id"] = {m["id"]: m for m in markets}
        _STATE["by_name"] = {m["name"].lower(): m for m in markets}
        lines = []
        for m in markets:
            extra = f" (inside {m['parent']})" if m["parent"] else ""
            lines.append(f"{m['id']}\t{m['name']}{extra}\t{m['audience']}")
        _STATE["list_text"] = "\n".join(lines)
    return _STATE


def markets():
    """Every market we can offer: complete ones only, best-known order, stable ids."""
    return _ensure()["markets"]


def market_by_name(name):
    """The market record for a name, or None. Only ever a complete market."""
    return _ensure()["by_name"].get((name or "").strip().lower())


# ---------------------------------------------------------------------------------------------------
# Prompts. The buyer is the subject of every sentence the model writes. It never advises the coach,
# never judges the coach, never names a source or a method, and keeps the buyer's own words as typed.

_VOICE = """How you write, every time:
- Plain English a twelve-year-old follows. Short sentences. No jargon.
- The buyer is the subject of every sentence. Write "They" or "These people", never "You".
- Never advise, correct, praise or judge the coach. Never say what they should do or write.
- Keep the coach's own words for the buyer exactly as typed, typos included. Do not tidy them.
- No dashes of any kind. Use a comma or a full stop. No asterisks, no bullet points, no headings.
- Never use the word "matter" in any form.
- Never name a book, a study, a method, a framework, a company or an AI.
- British spelling."""

_REFLECT_SYSTEM = _VOICE + """

A coach is answering three questions about the people they coach, one at a time. After each answer
you read it back in one or two short sentences that describe the BUYER the coach just described.
You are showing the coach that their buyer has been understood. You are not summarising the coach.

You also decide whether the answer is too thin to tell which market this buyer belongs to. An answer
is thin when it could describe almost anyone: "women", "business owners", "people who feel stuck",
"they want to be happier". A thin answer gets one plain question asking for the missing piece, in
one line. The question is about the buyer, not about the coach. For example: "Which women? What is
going on in their lives when they come looking?" An answer that names a kind of person, a situation
or a problem is not thin, even when it is short.

Question 1 asks who they coach. Question 2 asks what those people come with, in the buyer's words.
Question 3 asks what those people think will fix it.

Return JSON with:
- "reflection": one or two sentences about the buyer, from the answer. Empty string if thin is true.
- "thin": true or false.
- "ask": the one-line question when thin is true, otherwise an empty string."""

_REFLECT_SCHEMA = {
    "type": "object",
    "properties": {
        "reflection": {"type": "string"},
        "thin": {"type": "boolean"},
        "ask": {"type": "string"},
    },
    "required": ["reflection", "thin", "ask"],
    "additionalProperties": False,
}

_MATCH_SYSTEM = _VOICE + """

A coach has answered three questions about the people they coach. Below is the list of markets we
hold research for. One market per line: an id, a tab, the market name, a tab, who the buyers are.

Pick the three or four markets off this list that best fit the buyer the coach described. Use all
three answers. The second and third answers often say more than the first. A smaller market inside
a bigger one (marked "inside") beats the bigger one when the answers fit it. Never pick a market that
is not on the list. Never pick the same market twice. Order them best fit first.

For each one, give one short reason, in one sentence, that says what the buyer in that market has in
common with the buyer the coach described. The reason is about the buyer. It does not address the
coach, and it does not mention the list or any research.

Return JSON with "matches": a list of three or four objects, each with "id" (the number off the list)
and "why" (the one-sentence reason).

The list:
"""

_PAIR_SYSTEM = _VOICE + """

A coach has answered three questions about the people they coach. After the answers is a numbered
list of things real buyers in that market have said about their own problem, in their own words.

Do two things.

First, copy ONE short run of words out of the coach's second or third answer that says what the
coach thinks these buyers come with or want. Copy it letter for letter as typed, typos and all. Do
not tidy it, shorten words, or fix spelling. Keep it under twelve words. It must appear in the answer
exactly as you copy it. Prefer the coach's own description of the buyer over a description of the
coach or the coaching.

Second, pick the ONE line off the numbered list that is closest in topic to that run of words. The
closest line is the one about the same worry, the same want or the same situation. If no line on
the list is anywhere near it, answer -1.

Return JSON with "you_said" (the copied run of words) and "quote" (the number off the list, or -1).

The list:
"""

_PAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "you_said": {"type": "string"},
        "quote": {"type": "integer"},
    },
    "required": ["you_said", "quote"],
    "additionalProperties": False,
}

_MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "why": {"type": "string"},
                },
                "required": ["id", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["matches"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------------------------------
# Scrubbing. The model is told not to write these. This is for the day it does anyway.

def scrub(text):
    t = str(text or "")
    t = t.replace("—", ",").replace("–", ",").replace(" -- ", ", ").replace(" - ", ", ")
    t = re.sub(r"[*_`#>]+", "", t)
    t = re.sub(r"\s*,\s*", ", ", t)
    t = re.sub(r",\s*([.;:,!?])", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def clean_answer(text):
    """What a coach typed, kept as typed, but capped and with control characters out."""
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(text or ""))
    return t.replace("\r\n", "\n").replace("\r", "\n").strip()[:ANSWER_LIMIT]


# ---------------------------------------------------------------------------------------------------
# The calls.

def _client():
    import anthropic
    return anthropic.Anthropic(timeout=40.0, max_retries=1)


def _kwargs(system_blocks, user_text, schema, max_tokens):
    kw = dict(
        model=MODEL, max_tokens=max_tokens,
        system=system_blocks,
        messages=[{"role": "user", "content": user_text}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    # Haiku 4.5 and the 3.x models take a temperature and no effort setting. Everything newer takes
    # effort and rejects a temperature. Low effort: this is routing and read-back, not reasoning.
    if "haiku-4" in MODEL or "claude-3" in MODEL:
        kw["temperature"] = 0
    else:
        kw["output_config"]["effort"] = "low"
    return kw


def _log_usage(what, resp, started):
    u = getattr(resp, "usage", None)
    if u is None:
        return
    print(f"[matcher] {what} model={MODEL} in={u.input_tokens} "
          f"cache_write={getattr(u, 'cache_creation_input_tokens', 0) or 0} "
          f"cache_read={getattr(u, 'cache_read_input_tokens', 0) or 0} "
          f"out={u.output_tokens} secs={time.time() - started:.1f}", flush=True)


def _json_of(resp):
    if getattr(resp, "stop_reason", "") == "refusal":
        raise RuntimeError("refused")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)


def reflect(step, answers, answer):
    """One answer read back. step is 1, 2 or 3. answers holds the earlier ones, by key.

    Returns {"reflection": str, "thin": bool, "ask": str}. On any failure it returns an empty
    reflection with thin False, so the page carries on and the coach never sees an error.
    """
    answer = clean_answer(answer)
    empty = {"reflection": "", "thin": False, "ask": ""}
    if not answer:
        return empty
    earlier = ""
    for i, q in enumerate(QUESTIONS[:step - 1]):
        a = clean_answer(answers.get(q["key"], ""))
        if a:
            earlier += f"Question {i + 1}: {q['ask']}\nAnswer: {a}\n\n"
    q = QUESTIONS[step - 1]
    user = (earlier + f"Question {step}: {q['ask']} {q['note']}\nAnswer: {answer}")
    started = time.time()
    try:
        resp = _client().messages.create(**_kwargs(
            [{"type": "text", "text": _REFLECT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            user, _REFLECT_SCHEMA, 300))
        _log_usage(f"reflect q{step}", resp, started)
        data = _json_of(resp)
    except Exception as e:
        print(f"[matcher] reflect q{step} failed: {type(e).__name__}: {e}", flush=True)
        return empty
    thin = bool(data.get("thin"))
    ask = scrub(data.get("ask", "")) if thin else ""
    out = {"reflection": "" if thin else scrub(data.get("reflection", "")),
           "thin": thin and bool(ask), "ask": ask}
    return out


def _squash(text):
    """Lower case, one space between words, for a does-this-appear-in-that check that does not
    trip on a line break or a double space."""
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def pair(answers, quotes):
    """The coach's own words about their buyer next to a real buyer's words.

    answers: the three answers by key. quotes: the market's buyer quotes, already cleaned, as a list
    of strings. Returns {"you_said": str, "they_say": str} or None. None means the report shows no
    pair, and nothing else changes.

    Two gates on the way out, so the model can only ever choose, never write. The coach phrase must
    appear in what the coach actually typed, and the buyer line must be one off the list we gave it.
    Anything else is dropped and the block is left off.
    """
    answers = {k: clean_answer(answers.get(k, "")) for k in KEYS}
    quotes = [q for q in (str(x or "").strip() for x in quotes) if q][:24]
    if not quotes or not (answers.get("q_problem") or answers.get("q_fix")):
        return None
    user = ""
    for i, q in enumerate(QUESTIONS):
        user += f"Question {i + 1}: {q['ask']}\nAnswer: {answers[q['key']] or '(no answer)'}\n\n"
    listing = "\n".join(f"{i}\t{q}" for i, q in enumerate(quotes))
    started = time.time()
    try:
        resp = _client().messages.create(**_kwargs(
            [{"type": "text", "text": _PAIR_SYSTEM + listing}],
            user, _PAIR_SCHEMA, 200))
        _log_usage("pair", resp, started)
        data = _json_of(resp)
    except Exception as e:
        print(f"[matcher] pair failed: {type(e).__name__}: {e}", flush=True)
        return None
    said = re.sub(r"\s+", " ", str(data.get("you_said", ""))).strip().strip('"“”\'').strip()
    try:
        idx = int(data.get("quote", -1))
    except (TypeError, ValueError):
        idx = -1
    if not said or len(said.split()) > 14 or idx < 0 or idx >= len(quotes):
        return None
    # The phrase has to be the coach's, as typed. Case and spacing aside, it must sit inside one of
    # the answers. The model copying it is the instruction; this is the check.
    typed = _squash(answers["q_problem"]) + " \n " + _squash(answers["q_fix"]) + " \n " + _squash(answers["q_who"])
    if _squash(said) not in typed:
        return None
    return {"you_said": said, "they_say": quotes[idx]}


def _keyword_match(answers, exclude_ids=()):
    """The fallback when the model is unreachable. Words in the answers against words in the market
    names and audience labels. Crude, but it always offers something we hold."""
    words = set()
    for v in answers.values():
        for w in re.findall(r"[a-z][a-z'-]{2,}", str(v or "").lower()):
            words.add(w)
    words -= {"the", "and", "they", "them", "their", "who", "what", "with", "that", "this", "for",
              "are", "not", "but", "have", "has", "want", "wants", "think", "need", "needs", "come",
              "people", "coach", "coaching", "someone", "something", "about", "into", "from"}
    scored = []
    for m in markets():
        if m["id"] in exclude_ids:
            continue
        hay = set(re.findall(r"[a-z][a-z'-]{2,}", (m["name"] + " " + m["audience"]).lower()))
        n = len(words & hay)
        if n:
            scored.append((n, -len(m["name"]), m))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [dict(x[2], why="") for x in scored[:4]]


def match(answers, exclude_ids=(), extra=""):
    """The three answers against our list. Returns up to four market records, best first, each with
    a "why". Every one is a complete market: the list only ever held complete markets, and every id
    that comes back is checked against it again before it is used.

    exclude_ids are markets the coach has already said no to. extra is the coach's answer to the
    one more question we ask when none of the cards fit.
    """
    answers = {k: clean_answer(answers.get(k, "")) for k in KEYS}
    user = ""
    for i, q in enumerate(QUESTIONS):
        user += f"Question {i + 1}: {q['ask']}\nAnswer: {answers[q['key']] or '(no answer)'}\n\n"
    if extra:
        user += ("The coach was shown some markets and said none of them fit. Asked what they would "
                 f"call their market in their own words, they said: {clean_answer(extra)}\n\n")
    if exclude_ids:
        user += "Do not pick these ids, the coach has already said no to them: " + \
                ", ".join(str(i) for i in exclude_ids) + "\n"
    started = time.time()
    try:
        resp = _client().messages.create(**_kwargs(
            [{"type": "text", "text": _MATCH_SYSTEM + _ensure()["list_text"],
              "cache_control": {"type": "ephemeral"}}],
            user, _MATCH_SCHEMA, 600))
        _log_usage("match", resp, started)
        data = _json_of(resp)
        picks = data.get("matches") or []
    except Exception as e:
        print(f"[matcher] match failed: {type(e).__name__}: {e}", flush=True)
        picks = []
    out, seen = [], set()
    for p in picks:
        try:
            mid = int(p.get("id"))
        except (TypeError, ValueError):
            continue
        m = _ensure()["by_id"].get(mid)
        # The gate again, on the way out. The list was built from complete markets, and this makes
        # sure nothing else can ride through on a bad id.
        if not m or mid in seen or mid in exclude_ids or not _t.is_complete(m["name"]):
            continue
        seen.add(mid)
        out.append(dict(m, why=scrub(p.get("why", ""))))
        if len(out) == 4:
            break
    if not out:
        merged = dict(answers)
        if extra:
            merged["extra"] = extra
        out = [m for m in _keyword_match(merged, exclude_ids) if _t.is_complete(m["name"])]
    return out[:4]
