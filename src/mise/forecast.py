"""Step 2: forecast orders per kitchen, brand and meal slot, then turn them into a prep plan.

How it works, in plain words:
  * Count orders for every kitchen x brand x meal slot x day.
  * For each row, describe what we knew the day before: same day last week,
    the last 7 days' average, the same weekday over the last 4 weeks, rain, holidays.
  * A gradient-boosted tree model (many small decision trees added together)
    learns how those clues map to the next day's orders.
  * Test: hide the last 7 days, forecast them one day at a time, compare with
    what really happened, and compare with the simple rule "same as last week".
  * Then retrain on everything and forecast tomorrow. Multiply forecast orders by
    each brand's recipe to get the prep list.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from . import config as C

FEATURES = ["kitchen_c", "brand_c", "slot_c", "dow", "rain", "holiday",
            "lag_7", "lag_14", "roll_7", "same_dow_4", "ks_roll_7"]


def _panel() -> pd.DataFrame:
    orders = pd.read_csv(C.DATA_DIR / "orders.csv.gz", usecols=["date", "kitchen", "brand", "slot"])
    cal = pd.read_csv(C.DATA_DIR / "calendar.csv")
    counts = orders.groupby(["date", "kitchen", "brand", "slot"]).size().rename("orders")
    # every combination that can exist (a brand with zero share in a slot is left out)
    combos = [(k, C.BRANDS[b], C.SLOTS[s]) for k in C.KITCHENS for s in range(5) for b in range(6) if C.BRAND_SHARE[s][b] > 0]
    idx = pd.MultiIndex.from_tuples([(d, *c) for d in cal["date"] for c in combos], names=["date", "kitchen", "brand", "slot"])
    p = counts.reindex(idx).reset_index()
    p.loc[p["date"] <= C.END_DATE, "orders"] = p.loc[p["date"] <= C.END_DATE, "orders"].fillna(0)
    p = p.merge(cal[["date", "dow", "rain", "holiday"]], on="date")
    p["holiday"] = (p["holiday"].fillna("") != "").astype(int)
    p["kitchen_c"] = p["kitchen"].map({k: i for i, k in enumerate(C.KITCHENS)})
    p["brand_c"] = p["brand"].map({b: i for i, b in enumerate(C.BRANDS)})
    p["slot_c"] = p["slot"].map({s: i for i, s in enumerate(C.SLOTS)})
    p = p.sort_values(["kitchen", "brand", "slot", "date"]).reset_index(drop=True)

    g = p.groupby(["kitchen", "brand", "slot"])["orders"]
    p["lag_7"] = g.shift(7)
    p["lag_14"] = g.shift(14)
    p["roll_7"] = g.transform(lambda x: x.shift(1).rolling(7).mean())
    p["same_dow_4"] = g.transform(lambda x: (x.shift(7) + x.shift(14) + x.shift(21) + x.shift(28)) / 4)
    ks = p.groupby(["date", "kitchen", "slot"])["orders"].transform("sum")
    p["_ks"] = ks
    p["ks_roll_7"] = p.groupby(["kitchen", "brand", "slot"])["_ks"].transform(lambda x: x.shift(1).rolling(7).mean())
    return p.drop(columns="_ks")


def _model():
    return HistGradientBoostingRegressor(loss="poisson", max_iter=300, learning_rate=0.06,
                                         max_leaf_nodes=31, min_samples_leaf=20,
                                         categorical_features=[0, 1, 2], random_state=C.SEED)


def _wape(actual, pred):
    return float(np.abs(actual - pred).sum() / max(actual.sum(), 1))


def run() -> dict:
    p = _panel()
    dates = sorted(p["date"].unique())
    hist_dates = [d for d in dates if d <= C.END_DATE]
    test_dates = hist_dates[-C.TEST_DAYS:]
    usable = p.dropna(subset=["same_dow_4", "roll_7"])

    # backtest: train once on data before the test week (features already use only past days)
    train = usable[usable["date"] < test_dates[0]]
    test = usable[usable["date"].isin(test_dates)].copy()
    m = _model().fit(train[FEATURES], train["orders"])
    test["forecast"] = m.predict(test[FEATURES])
    test["baseline"] = test["lag_7"]

    ks = test.groupby(["date", "kitchen", "slot"])[["orders", "forecast", "baseline"]].sum().reset_index()
    by_slot = {s: {"model": _wape(g["orders"], g["forecast"]), "baseline": _wape(g["orders"], g["baseline"])}
               for s, g in ks.groupby("slot")}
    by_kitchen = {k: {"model": _wape(g["orders"], g["forecast"]), "baseline": _wape(g["orders"], g["baseline"])}
                  for k, g in ks.groupby("kitchen")}
    daily = ks.groupby("date")[["orders", "forecast", "baseline"]].sum().reset_index()

    # history of daily totals (actual) for the trend chart, plus test-week forecasts
    hist_daily = p[p["date"] <= C.END_DATE].groupby("date")["orders"].sum().reset_index()

    # tomorrow: retrain on everything up to yesterday
    full = usable[usable["date"] <= C.END_DATE]
    m2 = _model().fit(full[FEATURES], full["orders"])
    tom = p[p["date"] == C.TOMORROW].copy()
    tom["forecast"] = m2.predict(tom[FEATURES])
    tom["forecast_orders"] = tom["forecast"].round().astype(int)

    plan = []
    for _, r in tom.iterrows():
        for item, unit, per in C.PREP_RECIPE[r["brand"]]:
            plan.append({"kitchen": r["kitchen"], "slot": r["slot"], "brand": r["brand"], "item": item, "unit": unit,
                         "quantity": per * r["forecast"]})
    plan = pd.DataFrame(plan)

    C.OUT_DIR.mkdir(exist_ok=True)
    test[["date", "kitchen", "brand", "slot", "orders", "forecast", "baseline"]].round(2).to_csv(C.OUT_DIR / "forecast_backtest.csv", index=False)
    tom[["date", "kitchen", "brand", "slot", "forecast_orders"]].to_csv(C.OUT_DIR / "forecast_tomorrow.csv", index=False)
    plan.round(2).to_csv(C.OUT_DIR / "prep_plan_tomorrow.csv", index=False)

    return {
        "test_dates": test_dates,
        "wape_model": _wape(ks["orders"], ks["forecast"]),
        "wape_baseline": _wape(ks["orders"], ks["baseline"]),
        "by_slot": by_slot, "by_kitchen": by_kitchen,
        "backtest_cells": ks, "daily": daily, "hist_daily": hist_daily,
        "tomorrow": tom[["kitchen", "brand", "slot", "forecast"]], "plan": plan,
        "train_rows": len(train), "test_rows": len(test),
    }


if __name__ == "__main__":
    r = run()
    print("WAPE model", round(r["wape_model"], 3), "baseline", round(r["wape_baseline"], 3))
