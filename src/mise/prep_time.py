"""Step 3: predict how long each order will take to get ready, and flag late risk.

How it works, in plain words:
  * Every past order tells us: which brand, how many items, how many orders were
    already on the line, how many cooks were on shift, how long recent orders took,
    and how long this one actually took.
  * Two tree models learn from that: one predicts the typical time (median), one
    predicts a bad-case time (90th percentile).
  * Test: train on older weeks, predict the last 7 days, and compare with a simple
    rule ("this kitchen's usual time for this slot").
  * What-if for tomorrow: replay tomorrow's forecast orders through a model of the
    kitchen line with the planned cooks, then with one more cook, and predict prep
    times for each. That shows where one extra cook removes the late risk.
"""
import heapq
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from . import config as C

FEATURES = ["kitchen_c", "brand_c", "slot_c", "items", "orders_in_progress", "stations_on_shift",
            "load_per_station", "recent_avg_prep_min", "minute_of_slot", "dow"]


def _prep(df: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    df = df.merge(cal[["date", "dow"]], on="date", how="left")
    df["kitchen_c"] = df["kitchen"].map({k: i for i, k in enumerate(C.KITCHENS)})
    df["brand_c"] = df["brand"].map({b: i for i, b in enumerate(C.BRANDS)})
    df["slot_c"] = df["slot"].map({s: i for i, s in enumerate(C.SLOTS)})
    df["load_per_station"] = df["orders_in_progress"] / df["stations_on_shift"]
    if "minute_of_slot" not in df:
        t = pd.to_datetime(df["placed_at"])
        start = df["slot_c"].map(dict(enumerate(C.SLOT_START_HOUR)))
        mins = t.dt.hour * 60 + t.dt.minute - start * 60
        df["minute_of_slot"] = np.where(mins < 0, mins + 1440, mins)
    return df


def _model(q):
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=250, learning_rate=0.08,
                                         max_leaf_nodes=31, min_samples_leaf=40,
                                         categorical_features=[0, 1, 2], random_state=C.SEED)


def _simulate(arrivals, stations):
    """Queue model of one kitchen line. arrivals: list of (minute, brand_index, items, work_min)."""
    free = [0.0] * stations
    heapq.heapify(free)
    finished, rows = [], []
    for t, b, items, work in arrivals:
        in_progress = sum(1 for f, _ in finished if f > t)
        done = [p for f, p in finished if f <= t][-5:]
        start = max(t, heapq.heappop(free))
        end = start + work
        heapq.heappush(free, end)
        finished.append((end, end - t + 1.0))
        rows.append({"brand_c": b, "items": items, "orders_in_progress": in_progress,
                     "recent_avg_prep_min": np.mean(done) if done else np.nan, "minute_of_slot": t})
    return rows


def run(forecast_tomorrow: pd.DataFrame) -> dict:
    cal = pd.read_csv(C.DATA_DIR / "calendar.csv")
    orders = pd.read_csv(C.DATA_DIR / "orders.csv.gz")
    orders = orders[orders["cancelled"] == 0].copy()
    orders = _prep(orders, cal)
    dates = sorted(orders["date"].unique())
    test_dates = dates[-C.TEST_DAYS:]
    train = orders[orders["date"] < test_dates[0]]
    test = orders[orders["date"].isin(test_dates)].copy()

    m50, m90 = _model(0.5).fit(train[FEATURES], train["prep_minutes"]), _model(0.9).fit(train[FEATURES], train["prep_minutes"])
    test["pred_p50"] = m50.predict(test[FEATURES])
    test["pred_p90"] = m90.predict(test[FEATURES])
    base = train.groupby(["kitchen", "slot"])["prep_minutes"].median().rename("baseline")
    test = test.join(base, on=["kitchen", "slot"])
    mae_model = float((test["prep_minutes"] - test["pred_p50"]).abs().mean())
    mae_base = float((test["prep_minutes"] - test["baseline"]).abs().mean())
    test["late"] = test["prep_minutes"] > C.PROMISE_MIN
    test["flag"] = test["pred_p50"] > C.PROMISE_MIN
    tp = int((test["late"] & test["flag"]).sum())
    precision = tp / max(int(test["flag"].sum()), 1)
    recall = tp / max(int(test["late"].sum()), 1)

    # per day x kitchen x slot summary for the dashboard (test week)
    agg = test.groupby(["date", "kitchen", "slot"]).agg(
        orders=("order_id", "size"), pred_p50=("pred_p50", "mean"), pred_p90=("pred_p90", "mean"),
        actual=("prep_minutes", "mean"), late_share=("late", "mean"), pred_late_share=("flag", "mean"),
        stations=("stations_on_shift", "max"), peak_queue=("orders_in_progress", "max")).reset_index()

    # what-if for tomorrow: planned cooks vs one more cook
    roster = pd.read_csv(C.DATA_DIR / "roster_tomorrow.csv")
    rng = np.random.default_rng(C.SEED + 1)
    tdow = int(cal.loc[cal["date"] == C.TOMORROW, "dow"].iloc[0])
    whatif = []
    for (kitchen, slot), g in forecast_tomorrow.groupby(["kitchen", "slot"]):
        s = C.SLOTS.index(slot)
        planned = int(roster.loc[(roster["kitchen"] == kitchen) & (roster["slot"] == slot), "stations_planned"].iloc[0])
        res = {}
        for extra in (0, 1, 2):
            preds, lates = [], []
            for _ in range(12):                        # replay 12 possible versions of tomorrow
                arr = []
                for _, r in g.iterrows():
                    b = C.BRANDS.index(r["brand"])
                    for _ in range(rng.poisson(max(r["forecast"], 0))):
                        items = int(min(6, 1 + rng.poisson(0.8)))
                        work = C.BRAND_WORK_MIN[b] * (0.75 + 0.25 * items) * rng.lognormal(0, 0.15)
                        arr.append((rng.beta(2.2, 2.4) * C.SLOT_LEN_MIN[s], b, items, work))
                arr.sort()
                rows = pd.DataFrame(_simulate(arr, planned + extra))
                if rows.empty:
                    continue
                rows["kitchen_c"] = C.KITCHENS.index(kitchen); rows["slot_c"] = s; rows["dow"] = tdow
                rows["stations_on_shift"] = planned + extra
                rows["load_per_station"] = rows["orders_in_progress"] / rows["stations_on_shift"]
                p = m50.predict(rows[FEATURES])
                preds.append(p.mean()); lates.append((p > C.PROMISE_MIN).mean())
            res[extra] = (float(np.mean(preds)) if preds else 0.0, float(np.mean(lates)) if lates else 0.0)
        whatif.append({"kitchen": kitchen, "slot": slot, "stations_planned": planned,
                       "forecast_orders": float(g["forecast"].sum()),
                       "pred_prep_planned": res[0][0], "pred_late_planned": res[0][1],
                       "pred_prep_plus1": res[1][0], "pred_late_plus1": res[1][1],
                       "pred_prep_plus2": res[2][0], "pred_late_plus2": res[2][1]})
    whatif = pd.DataFrame(whatif)

    C.OUT_DIR.mkdir(exist_ok=True)
    agg.round(3).to_csv(C.OUT_DIR / "prep_time_by_slot.csv", index=False)
    whatif.round(3).to_csv(C.OUT_DIR / "staffing_whatif_tomorrow.csv", index=False)
    importances = _importance(m50, test)
    return {"mae_model": mae_model, "mae_baseline": mae_base, "precision": precision, "recall": recall,
            "late_orders_test": int(test["late"].sum()), "orders_test": len(test),
            "by_slot": agg, "whatif": whatif, "importance": importances, "train_rows": len(train)}


def _importance(model, test):
    """Which inputs matter most: how much the error grows when one input is shuffled."""
    sample = test.sample(min(6000, len(test)), random_state=C.SEED)
    base = (sample["prep_minutes"] - model.predict(sample[FEATURES])).abs().mean()
    out = {}
    rng = np.random.default_rng(C.SEED)
    for f in FEATURES:
        s = sample.copy()
        s[f] = rng.permutation(s[f].values)
        out[f] = float((s["prep_minutes"] - model.predict(s[FEATURES])).abs().mean() - base)
    return out
