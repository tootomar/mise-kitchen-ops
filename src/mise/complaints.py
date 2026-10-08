"""Step 4: read complaints, tag each with a defect type, and find where problems concentrate.

How it works, in plain words:
  * Tagging. Two options:
      - AI tagging: a language model (Claude) reads each complaint and picks the
        defect type, a severity and a likely cause. Used when an Anthropic API key
        is set (ANTHROPIC_API_KEY), or live from the dashboard inside Claude.
      - Keyword tagging: a simple word-matching rule set. Always available, so the
        pipeline runs on any laptop with no key. Its accuracy is measured against
        reviewer labels so you can see what the AI adds.
  * Hotspots. Each complaint is linked back to its order, so we can ask "were these
    late orders actually slow in the kitchen?" and "is this one brand, one slot?".
    A kitchen x defect cell becomes a hotspot when it is far above what other
    kitchens see. Each hotspot gets evidence, an owner and a first action.
"""
import json
import os
import re

import pandas as pd

from . import config as C

RULES = [
    ("Wrong item", r"\b(wrong|someone else|instead of|different)\b"),
    ("Missing item", r"\b(missing|not included|not in the (bag|box)|no oregano|not delivered|not added|not available|out of stock|cancel)"),
    ("Cold food", r"\b(cold|lukewarm|reheat|rubbery)\b"),
    ("Packaging or spill", r"\b(leak|spill|broken|crushed|damaged)"),
    ("Quantity", r"\b(portion|very little|half-filled|smaller|quantity)\b"),
    ("Late delivery", r"\b(late|slow|forever|hour|minutes after|preparing|waited|after everyone)\b"),
    ("Taste or quality", r"\b(salty|soggy|stale|undercooked|overcooked|mushy|oily|tasted|taste|heavy)\b"),
]

OWNER = {
    "Late delivery": ("Kitchen manager", "Add a line cook or station for the slot; simplify the peak menu"),
    "Cold food": ("Area manager with platform", "Check rider wait at pickup; hot bags; hold orders until rider is near"),
    "Missing item": ("Packing lead", "Brand-wise checklist at the pass; dips and sachets pre-kitted per order"),
    "Wrong item": ("Packing lead", "Scan order ticket against bag label before handover"),
    "Taste or quality": ("Kitchen manager and R&D chef", "Recipe audit and tasting for the dish named in complaints"),
    "Packaging or spill": ("Central kitchen and packaging", "Check lid and container batch; seal gravies"),
    "Quantity": ("Kitchen manager", "Portion scoops and weigh-checks at the line"),
}


def tag_rules(text: str) -> str:
    t = text.lower()
    for defect, pattern in RULES:
        if re.search(pattern, t):
            return defect
    return "Needs review"      # no keyword matched: a person (or the AI) has to read it


def tag_llm(df: pd.DataFrame) -> pd.Series:
    """Tag with Claude when a key is available. Returns None when it is not."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic()
    out = {}
    for start in range(0, len(df), 40):
        chunk = df.iloc[start:start + 40]
        items = [{"id": int(r.complaint_id), "text": r.text} for r in chunk.itertuples()]
        msg = client.messages.create(
            model=os.environ.get("MISE_MODEL", "claude-haiku-4-5"), max_tokens=2000,
            messages=[{"role": "user", "content":
                       "Classify each food-delivery complaint into exactly one defect from "
                       f"{json.dumps(C.DEFECTS)}. Reply with only a JSON array of "
                       '{"id": number, "defect": string}.\n\n' + json.dumps(items)}])
        text = msg.content[0].text
        arr = json.loads(text[text.find("["): text.rfind("]") + 1])
        out.update({int(a["id"]): a["defect"] for a in arr if a.get("defect") in C.DEFECTS})
    return df["complaint_id"].map(out).fillna(df["text"].map(tag_rules))


def run() -> dict:
    comp = pd.read_csv(C.DATA_DIR / "complaints.csv.gz")
    orders_all = pd.read_csv(C.DATA_DIR / "orders.csv.gz", usecols=["order_id", "date", "kitchen", "slot", "prep_minutes", "items", "stations_on_shift", "cancelled"])
    orders = orders_all.drop(columns=["date", "kitchen", "slot"])
    stock = pd.read_csv(C.DATA_DIR / "stockouts.csv")

    llm = tag_llm(comp)
    comp["defect"] = llm if llm is not None else comp["text"].map(tag_rules)
    method = "Claude" if llm is not None else "keyword rules"
    accuracy = float((comp["defect"] == comp["true_defect"]).mean())
    comp = comp.merge(orders, on="order_id", how="left")
    comp["kitchen_late"] = comp["prep_minutes"] > C.PROMISE_MIN

    dates = sorted(comp["date"].unique())
    all_dates = sorted(pd.read_csv(C.DATA_DIR / "calendar.csv")["date"])
    test_dates = [d for d in all_dates if d <= C.END_DATE][-C.TEST_DAYS:]
    week = comp[comp["date"].isin(test_dates)]
    prev = comp[comp["date"].isin([d for d in all_dates if d < test_dates[0]][-C.TEST_DAYS:])]

    # hotspots: kitchen x defect cells far above the other kitchens
    cell = week[week["defect"] != "Needs review"].groupby(["kitchen", "defect"]).size().rename("n").reset_index()
    typical = cell.groupby("defect")["n"].median().rename("typical")
    cell = cell.join(typical, on="defect")
    prev_cell = prev.groupby(["kitchen", "defect"]).size().rename("prev")
    cell = cell.join(prev_cell, on=["kitchen", "defect"]).fillna({"prev": 0})
    cell["excess"] = cell["n"] - cell["typical"]
    hot = cell[(cell["n"] >= 6) & (cell["n"] >= 2.5 * cell["typical"])].sort_values("excess", ascending=False).head(5)

    hotspots = []
    for _, h in hot.iterrows():
        h_short = False
        g = week[(week["kitchen"] == h.kitchen) & (week["defect"] == h.defect)]
        top_slot = g["slot"].value_counts()
        top_brand = g["brand"].value_counts()
        ev = [f"{int(h.n)} complaints this week vs {h.typical:.0f} at a typical kitchen; {int(h.prev)} the week before",
              f"{top_slot.iloc[0] / len(g):.0%} at {top_slot.index[0]}, {top_brand.iloc[0] / len(g):.0%} on {top_brand.index[0]}"]
        if h.defect in ("Late delivery", "Cold food"):
            slow = g["kitchen_late"].mean()
            ev.append(f"{slow:.0%} of these orders took over {C.PROMISE_MIN} min in the kitchen"
                      + (" (so the delay is after the kitchen: rider wait)" if slow < 0.4 else " (so the delay is in the kitchen)"))
            st = g["stations_on_shift"].median()
            usual = orders_all[(orders_all["kitchen"] == h.kitchen) & (orders_all["slot"] == g["slot"].mode().iloc[0])
                               & (orders_all["date"] < "2026-09-01")]["stations_on_shift"].median()
            ev.append(f"Cooks on shift for these orders: {st:.0f} (usually {usual:.0f})" if st < usual else f"Cooks on shift: {st:.0f}, the normal level")
            h_short = st < usual
        stock_driven = False
        if h.defect == "Missing item":
            cancelled = int(g["cancelled"].fillna(0).sum())
            stock_driven = cancelled >= 0.3 * len(g)
            if stock_driven:
                so = stock[(stock["kitchen"] == h.kitchen) & (stock["date"].isin(test_dates)) & (stock["brand"] == top_brand.index[0])]
                ev.append(f"{cancelled} of {len(g)} are orders cancelled after acceptance")
                if len(so):
                    ev.append(f"{len(so)} stock-outs this week ({', '.join(so['item'].unique())}): {so['reason'].iloc[0]}")
            else:
                ev.append("Orders were delivered; the items were left out at packing")
        owner, action = OWNER[h.defect]
        if stock_driven:
            owner, action = "Central kitchen dispatch", "Fix the dispatch count for the brand; do not accept orders for items switched off"
        if h.defect in ("Late delivery", "Cold food") and h_short:
            owner, action = "Kitchen manager", f"Restore the missing cooks at {top_slot.index[0].lower()}; see the staffing what-if"
        hotspots.append({"kitchen": h.kitchen, "defect": h.defect, "n": int(h.n), "typical": float(h.typical),
                         "prev": int(h.prev), "evidence": ev, "owner": owner, "action": action,
                         "slot": top_slot.index[0], "brand": top_brand.index[0]})

    # newest 20 complaints (last night) for the live AI tagging demo
    last = comp[comp["date"] == C.END_DATE].sort_values("complaint_id").tail(20)

    C.OUT_DIR.mkdir(exist_ok=True)
    comp.drop(columns=["true_defect"]).to_csv(C.OUT_DIR / "complaints_tagged.csv", index=False)
    with open(C.OUT_DIR / "hotspots.json", "w") as f:
        json.dump(hotspots, f, indent=2)
    return {"tagged": comp, "method": method, "accuracy": accuracy, "hotspots": hotspots,
            "test_dates": test_dates, "last_night": last}
