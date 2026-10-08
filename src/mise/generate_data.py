"""Step 1: create realistic synthetic data for 10 cloud kitchens over 8 weeks.

Why synthetic: real order data is confidential. The generator behaves like a
real kitchen: orders arrive through each meal slot, wait for a free cook, and
take longer when the line is busy. Five operational problems are planted so the
dashboard has something real to find:

  P1  Whitefield runs dinner with half the usual cooks from 28 Sep (two resigned).
  P2  HSR Layout's new packer misses Olio Pizza dips and sachets from 24 Sep.
  P3  Electronic City demand drops ~28% from 20 Sep (a competitor opened nearby).
  P4  Koramangala late-night biryani waits for riders and arrives cold.
  P5  Jayanagar runs out of CakeZone cakes at dinner on 6 and 8 Oct.

Outputs (in data/): orders.csv.gz, complaints.csv.gz, stockouts.csv,
calendar.csv, roster_tomorrow.csv
"""
import heapq
import numpy as np
import pandas as pd

from . import config as C

rng = np.random.default_rng(C.SEED)

HOLIDAYS = {"2026-08-15": "Independence Day", "2026-09-14": "Ganesh Chaturthi", "2026-10-02": "Gandhi Jayanti"}

# line stations ("cooks") per slot; the queue model below turns these into wait times
STATIONS = [2, 6, 3, 7, 3]

DISH = {
    "EatFit": ["thali", "dal-rice bowl", "protein meal"],
    "Olio Pizza": ["pizza", "farmhouse pizza", "garlic bread"],
    "Sharief Bhai": ["biryani", "chicken biryani", "mutton biryani"],
    "CakeZone": ["cake", "truffle cake", "jar cake"],
    "Frozen Bottle": ["shake", "ice cream", "thick shake"],
    "Millet Express": ["millet dosa", "idli plate", "ragi dosa"],
}
TEXTS = {
    "Late delivery": [
        "Order reached {m} minutes after the promised time.",
        "Waited almost an hour for a simple {dish}.",
        "Rider said the kitchen was still preparing when he arrived.",
        "App kept showing 'preparing' for 30 minutes. Very slow.",
        "Ordered for a team dinner, food came after everyone left.",
        "Slow again from this outlet, third time this week.",
        "Took forever. Rider waited outside the kitchen for 20 minutes.",
    ],
    "Cold food": [
        "The {dish} arrived cold, had to reheat it.",
        "Food was lukewarm by the time it reached.",
        "{Dish} completely cold and rubbery.",
        "Cold in the middle, clearly sat somewhere for a while.",
    ],
    "Missing item": [
        "Garlic dip was missing from my order.",
        "No oregano or chilli flakes sachets in the box.",
        "Paid for a combo, the drink was not in the bag.",
        "Raita not included with the {dish}.",
        "One of the two items was not delivered.",
        "Extra cheese charged but not added.",
    ],
    "Wrong item": [
        "Got veg instead of chicken.",
        "Received someone else's order.",
        "Ordered a {dish}, got something different.",
        "Wrong size delivered.",
    ],
    "Taste or quality": [
        "The {dish} was too salty today.",
        "{Dish} was soggy and undercooked.",
        "Tasted stale, not like usual.",
        "Overcooked and mushy, not good.",
        "Oily and heavy, not what I expect from this brand.",
    ],
    "Packaging or spill": [
        "Gravy leaked all over the bag.",
        "Container lid broken, everything spilled.",
        "Box was crushed and the {dish} was damaged.",
        "Leaked through the bag onto my bike.",
    ],
    "Quantity": [
        "Portion was much smaller than usual.",
        "Very little in the {dish} for the price.",
        "Half-filled container, felt cheated.",
    ],
}
# about a third of real complaints are messy: Hinglish, typos, two issues in one, no keywords
MESSY = {   # (text, brand it fits or None for any brand)
    "Late delivery": [("bhai 1 ghanta laga, kya kar rahe ho", None), ("food reached after ages, kids slept hungry", None),
                      ("ordered at 8.10 got it 9.05, unacceptable", None), ("eta kept increasing every 5 min", None),
                      ("delivery partner reached restaurant n waited 25 min for food", None)],
    "Cold food": [("pizza thanda tha, cheese hard", "Olio Pizza"), ("biryani was like room temp, no steam at all", "Sharief Bhai"),
                  ("had to microwave the whole thing again", None), ("everything ice-cold by the time it came", None)],
    "Missing item": [("dip nahi tha phir se", "Olio Pizza"), ("zero seasoning packets this time", "Olio Pizza"), ("my coke never came", None),
                     ("paid 40 rs for dip, where is it?", "Olio Pizza"), ("order was cancelled after accepting, no cake", "CakeZone"),
                     ("raita gayab tha", "Sharief Bhai")],
    "Wrong item": [("this is not what i ordered at all", None), ("got paneer, i asked for chicken", "Sharief Bhai"),
                   ("sent me a margherita, ordered farmhouse", "Olio Pizza")],
    "Taste or quality": [("namak bahut zyada", None), ("dosa was rubber, chutney sour", "Millet Express"), ("biryani smelled off", "Sharief Bhai"),
                         ("base was raw from inside", "Olio Pizza"), ("dal had no flavour at all", "EatFit")],
    "Packaging or spill": [("curry all over the bag, box was wet", None), ("lid popped open, half the dal gone", "EatFit"),
                           ("cake looked like it was dropped", "CakeZone")],
    "Quantity": [("sabzi was 2 spoons", "EatFit"), ("paid 349 for a handful of rice", "Sharief Bhai"), ("box half empty", None)],
}


BASE_MIX = {"Missing item": 0.28, "Wrong item": 0.10, "Taste or quality": 0.30,
            "Packaging or spill": 0.18, "Quantity": 0.14}


def _dow_factor(dow: int, slot: int) -> float:
    if dow >= 5:   # Sat, Sun
        return [0.70, 0.75, 1.15, 1.35, 1.40][slot]
    if dow == 4:   # Fri
        return [1.00, 1.00, 1.05, 1.25, 1.30][slot]
    return 1.0


def _text(defect: str, brand: str) -> str:
    dish = rng.choice(DISH[brand])
    t = rng.choice(TEXTS[defect])
    return t.format(dish=dish, Dish=dish.capitalize(), m=int(rng.integers(25, 60)))


def generate() -> dict:
    dates = pd.date_range(C.START_DATE, C.END_DATE, freq="D")
    cal = []
    for i, d in enumerate(dates):
        month_rain = {8: 0.45, 9: 0.35, 10: 0.20}[d.month]
        cal.append({"date": d.date().isoformat(), "dow": d.dayofweek, "weekday": d.strftime("%a"),
                    "holiday": HOLIDAYS.get(d.date().isoformat(), ""), "rain": int(rng.random() < month_rain),
                    "day_index": i})
    cal = pd.DataFrame(cal)

    orders, complaints, stockouts = [], [], []
    oid = 0
    for _, day in cal.iterrows():
        d = pd.Timestamp(day.date)
        for k, kitchen in enumerate(C.KITCHENS):
            for s, slot in enumerate(C.SLOTS):
                mean = C.SLOT_BASE[s] * C.KITCHEN_SIZE[k] * _dow_factor(day.dow, s)
                mean *= 1 + 0.001 * day.day_index                    # slow growth
                if day.rain and s in (1, 3, 4):
                    mean *= 1.12                                       # rain lifts delivery
                if day.holiday:
                    mean *= [0.8, 0.85, 1.1, 1.2, 1.2][s]
                if kitchen == "Electronic City" and d >= pd.Timestamp("2026-09-20"):
                    mean *= 0.66                                       # P3
                stations = max(STATIONS[s], round(STATIONS[s] * C.KITCHEN_SIZE[k]))
                if kitchen == "Whitefield" and s == 3 and d >= pd.Timestamp("2026-09-28"):
                    stations = 5                                       # P1
                stock_out = kitchen == "Jayanagar" and s == 3 and day.date in ("2026-10-06", "2026-10-08")
                if stock_out:
                    stockouts.append({"date": day.date, "kitchen": kitchen, "slot": slot, "brand": "CakeZone",
                                      "item": "Cake bases, 500 g", "minutes_switched_off": int(rng.integers(90, 150)),
                                      "reason": "Central kitchen dispatch short by 18 bases"})
                elif rng.random() < 0.012:
                    b = rng.choice([b for b in range(6) if C.BRAND_SHARE[s][b] > 0])
                    stockouts.append({"date": day.date, "kitchen": kitchen, "slot": slot, "brand": C.BRANDS[b],
                                      "item": C.PREP_RECIPE[C.BRANDS[b]][0][0], "minutes_switched_off": int(rng.integers(20, 70)),
                                      "reason": "Ran out during service"})

                # orders for this kitchen-slot-day
                arrivals = []
                for b, brand in enumerate(C.BRANDS):
                    lam = mean * C.BRAND_SHARE[s][b]
                    if lam <= 0:
                        continue
                    n = rng.poisson(lam)
                    cancelled = 0
                    if stock_out and brand == "CakeZone":
                        cancelled = min(n, int(rng.integers(6, 10)))
                    for j in range(n):
                        # arrivals bunch towards the middle of the slot
                        t = rng.beta(2.2, 2.4) * C.SLOT_LEN_MIN[s]
                        items = int(min(6, 1 + rng.poisson(0.8)))
                        work = C.BRAND_WORK_MIN[b] * (0.75 + 0.25 * items) * rng.lognormal(0, 0.15)
                        arrivals.append([t, b, items, work, j < cancelled])
                arrivals.sort(key=lambda a: a[0])

                # queue model: each order waits for the first free station
                free = [0.0] * stations
                heapq.heapify(free)
                finished = []   # (finish_time, prep) of earlier orders
                for t, b, items, work, cancelled in arrivals:
                    brand = C.BRANDS[b]
                    in_progress = sum(1 for f, _ in finished if f > t)
                    done = [p for f, p in finished if f <= t][-5:]
                    recent = float(np.mean(done)) if done else np.nan
                    if cancelled:
                        prep = np.nan
                    else:
                        start = max(t, heapq.heappop(free))
                        end = start + work
                        heapq.heappush(free, end)
                        prep = end - t + 1.0                            # +1 min packing
                        finished.append((end, prep))
                    hh = C.SLOT_START_HOUR[s] + int(t // 60)
                    placed = d + pd.Timedelta(hours=hh % 24, minutes=int(t % 60)) + (pd.Timedelta(days=1) if hh >= 24 else pd.Timedelta(0))
                    channel = rng.choice(["Swiggy", "Zomato", "Own app", "Takeaway"], p=[0.37, 0.33, 0.12, 0.18])
                    value = round(C.BRAND_AOV[b] * (0.7 + 0.3 * items) * rng.lognormal(0, 0.12))
                    o = {"order_id": oid, "date": day.date, "kitchen": kitchen, "slot": slot, "brand": brand,
                         "placed_at": placed.strftime("%Y-%m-%d %H:%M"), "channel": channel, "items": items,
                         "order_value_inr": value, "stations_on_shift": stations, "orders_in_progress": in_progress,
                         "recent_avg_prep_min": None if np.isnan(recent) else round(recent, 2),
                         "prep_minutes": None if cancelled else round(prep, 2), "cancelled": int(cancelled)}
                    orders.append(o)

                    # complaints
                    late = (not cancelled) and prep > C.PROMISE_MIN
                    p, defect = 0.0055, None
                    if cancelled:
                        if rng.random() < 0.85:
                            defect = "Missing item"
                            text = rng.choice(["Cake order cancelled after 20 minutes, said out of stock.",
                                               "They called to say the cake is not available. Why accept the order?",
                                               "Cake cancelled at the last minute, birthday ruined."])
                    elif late and rng.random() < 0.06 + 0.006 * (prep - C.PROMISE_MIN):
                        defect = "Late delivery" if rng.random() < 0.75 else "Cold food"
                    elif kitchen == "HSR Layout" and brand == "Olio Pizza" and s in (3, 4) and d >= pd.Timestamp("2026-09-24") and rng.random() < 0.09:
                        defect, text = "Missing item", rng.choice(["Garlic dip was missing again.", "No oregano or chilli flakes sachets in the box.",
                                                                    "Dip and seasoning both missing from the pizza order.", "Paid for extra dip, not in the bag."])
                    elif kitchen == "Koramangala" and brand == "Sharief Bhai" and s == 4 and rng.random() < 0.22:
                        defect = "Cold food"
                    elif rng.random() < p:
                        defect = rng.choice(list(BASE_MIX), p=list(BASE_MIX.values()))
                    if defect:
                        if not (cancelled or (defect == "Missing item" and kitchen == "HSR Layout" and brand == "Olio Pizza" and s in (3, 4) and d >= pd.Timestamp("2026-09-24"))):
                            text = _text(defect, brand)
                        fits = [t for t, b in MESSY[defect] if b is None or b == brand]
                        if fits and rng.random() < 0.33:
                            text = str(rng.choice(fits))
                        complaints.append({"complaint_id": len(complaints), "order_id": oid, "date": day.date,
                                           "kitchen": kitchen, "slot": slot, "brand": brand,
                                           "source": rng.choice(["Swiggy", "Zomato", "Call centre"], p=[0.45, 0.42, 0.13]),
                                           "text": text, "true_defect": defect})
                    oid += 1

    orders = pd.DataFrame(orders)
    complaints = pd.DataFrame(complaints)
    stockouts = pd.DataFrame(stockouts)

    # tomorrow's roster: same as usual, Whitefield dinner still short
    roster = [{"date": C.TOMORROW, "kitchen": kn, "slot": sl,
               "stations_planned": 5 if (kn == "Whitefield" and sl == "Dinner") else max(STATIONS[s], round(STATIONS[s] * C.KITCHEN_SIZE[C.KITCHENS.index(kn)]))}
              for kn in C.KITCHENS for s, sl in enumerate(C.SLOTS)]
    roster = pd.DataFrame(roster)
    tomorrow = pd.Timestamp(C.TOMORROW)
    cal_tom = {"date": C.TOMORROW, "dow": tomorrow.dayofweek, "weekday": tomorrow.strftime("%a"),
               "holiday": "", "rain": 0, "day_index": len(cal)}

    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    orders.to_csv(C.DATA_DIR / "orders.csv.gz", index=False)
    complaints.to_csv(C.DATA_DIR / "complaints.csv.gz", index=False)
    stockouts.to_csv(C.DATA_DIR / "stockouts.csv", index=False)
    pd.concat([cal, pd.DataFrame([cal_tom])]).to_csv(C.DATA_DIR / "calendar.csv", index=False)
    roster.to_csv(C.DATA_DIR / "roster_tomorrow.csv", index=False)
    return {"orders": len(orders), "complaints": len(complaints), "stockouts": len(stockouts)}


if __name__ == "__main__":
    print(generate())
