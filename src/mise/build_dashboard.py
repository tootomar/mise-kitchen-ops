"""Step 5: package model outputs into one data file and write the dashboard page.

The dashboard is a single static HTML file (dashboard/index.html). It needs no
server, so it opens from a laptop, GitHub Pages or a Claude artifact link.
"""
import json
from datetime import datetime, timezone, timedelta

import pandas as pd

from . import config as C


def _r(x, n=2):
    return None if pd.isna(x) else round(float(x), n)


def build(fc: dict, pt: dict, cp: dict) -> dict:
    dates = fc["test_dates"]
    ks = fc["backtest_cells"].copy()
    pts = pt["by_slot"].copy()
    stock = pd.read_csv(C.DATA_DIR / "stockouts.csv")
    cal = pd.read_csv(C.DATA_DIR / "calendar.csv").set_index("date")

    # one row per day x kitchen x slot for the test week
    cells = ks.merge(pts, on=["date", "kitchen", "slot"], how="left", suffixes=("", "_p"))
    so = stock[stock["date"].isin(dates)].groupby(["date", "kitchen", "slot"]).size().rename("stockouts")
    cells = cells.join(so, on=["date", "kitchen", "slot"]).fillna({"stockouts": 0})
    # fields: day, kitchen, slot, orders, forecast, baseline, pred_p50, pred_p90, actual_prep,
    #         late_share, pred_late_share, stations, peak_queue, stockouts
    cell_rows = [[dates.index(r.date), C.KITCHENS.index(r.kitchen), C.SLOTS.index(r.slot),
                  int(r.orders), _r(r.forecast, 1), _r(r.baseline, 0), _r(r.pred_p50), _r(r.pred_p90), _r(r.actual),
                  _r(r.late_share, 3), _r(r.pred_late_share, 3), int(r.stations) if not pd.isna(r.stations) else None,
                  int(r.peak_queue) if not pd.isna(r.peak_queue) else None, int(r.stockouts)]
                 for r in cells.itertuples()]

    tom = fc["tomorrow"]
    tomorrow = [[C.KITCHENS.index(r.kitchen), C.SLOTS.index(r.slot), C.BRANDS.index(r.brand), _r(r.forecast, 1)] for r in tom.itertuples()]
    plan = fc["plan"].groupby(["kitchen", "slot", "brand", "item", "unit"])["quantity"].sum().reset_index()
    plan_rows = [[C.KITCHENS.index(r.kitchen), C.SLOTS.index(r.slot), C.BRANDS.index(r.brand), r.item, r.unit, _r(r.quantity, 2)] for r in plan.itertuples()]
    wi = pt["whatif"]
    whatif = [[C.KITCHENS.index(r.kitchen), C.SLOTS.index(r.slot), int(r.stations_planned), _r(r.forecast_orders, 0),
               _r(r.pred_prep_planned), _r(r.pred_late_planned, 3), _r(r.pred_prep_plus1), _r(r.pred_late_plus1, 3),
               _r(r.pred_prep_plus2), _r(r.pred_late_plus2, 3)] for r in wi.itertuples()]

    comp = cp["tagged"]
    week = comp[comp["date"].isin(dates)]
    complaints = [[int(r.complaint_id), dates.index(r.date), C.KITCHENS.index(r.kitchen), C.SLOTS.index(r.slot),
                   C.BRANDS.index(r.brand), C.TAGS.index(r.defect), r.text, r.source, _r(r.prep_minutes, 1)]
                  for r in week.itertuples()]
    prev_dates = [d for d in cal.index if d < dates[0]][-C.TEST_DAYS:]
    prev = comp[comp["date"].isin(prev_dates)].groupby(["kitchen", "defect"]).size()
    prev_rows = [[C.KITCHENS.index(k), C.TAGS.index(d), int(n)] for (k, d), n in prev.items()]
    ln = cp["last_night"]
    last_night = [[int(r.complaint_id), C.KITCHENS.index(r.kitchen), C.SLOTS.index(r.slot), C.BRANDS.index(r.brand),
                   r.text, C.TAGS.index(r.defect), C.TAGS.index(r.true_defect)] for r in ln.itertuples()]

    hist = fc["hist_daily"]
    daily = fc["daily"].set_index("date")
    trend = [[d, int(o), _r(daily.loc[d, "forecast"], 0) if d in daily.index else None,
              _r(daily.loc[d, "baseline"], 0) if d in daily.index else None] for d, o in zip(hist["date"], hist["orders"])]

    stock_rows = [[dates.index(r.date), C.KITCHENS.index(r.kitchen), C.SLOTS.index(r.slot), r.brand, r.item,
                   int(r.minutes_switched_off), r.reason] for r in stock[stock["date"].isin(dates)].itertuples()]

    ist = timezone(timedelta(hours=5, minutes=30))
    data = {
        "meta": {"area": C.AREA, "kitchens": C.KITCHENS, "brands": C.BRANDS, "slots": C.SLOTS, "slotHours": C.SLOT_HOURS,
                 "defects": C.DEFECTS, "tags": C.TAGS, "dates": dates, "weekday": {d: cal.loc[d, "weekday"] for d in list(cal.index)},
                 "tomorrow": C.TOMORROW, "breakEven": C.BREAK_EVEN_ORDERS, "strong": C.STRONG_ORDERS, "promise": C.PROMISE_MIN,
                 "historyStart": C.START_DATE, "builtAt": datetime.now(ist).strftime("%d %b %Y, %H:%M IST")},
        "cells": cell_rows, "tomorrow": tomorrow, "plan": plan_rows, "whatif": whatif,
        "complaints": complaints, "prevWeek": prev_rows, "lastNight": last_night, "hotspots": cp["hotspots"],
        "trend": trend, "stockouts": stock_rows,
        "models": {
            "forecast": {"wape": round(fc["wape_model"], 4), "baseline": round(fc["wape_baseline"], 4),
                         "bySlot": {k: {a: round(b, 4) for a, b in v.items()} for k, v in fc["by_slot"].items()},
                         "byKitchen": {k: {a: round(b, 4) for a, b in v.items()} for k, v in fc["by_kitchen"].items()},
                         "trainRows": fc["train_rows"], "testRows": fc["test_rows"]},
            "prep": {"mae": round(pt["mae_model"], 3), "baseline": round(pt["mae_baseline"], 3),
                     "precision": round(pt["precision"], 3), "recall": round(pt["recall"], 3),
                     "importance": {k: round(v, 3) for k, v in pt["importance"].items()},
                     "lateOrders": pt["late_orders_test"], "orders": pt["orders_test"], "trainRows": pt["train_rows"]},
            "tagger": {"method": cp["method"], "accuracy": round(cp["accuracy"], 4), "n": int(len(comp))},
        },
    }
    C.OUT_DIR.mkdir(exist_ok=True)
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    (C.OUT_DIR / "dashboard_data.json").write_text(payload, encoding="utf-8")
    template = (C.DASH_DIR / "template.html").read_text(encoding="utf-8")
    safe = payload.replace("</", "<\\/")
    (C.DASH_DIR / "index.html").write_text(template.replace("__MISE_DATA__", safe), encoding="utf-8")
    return data
