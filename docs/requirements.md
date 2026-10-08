# Mise requirements, from an operations manager's point of view

## Who uses it

The primary user is the **area operations manager**: one person responsible for 8–12 cloud kitchens in a city zone, judged on orders, on-time food, complaints and food cost.

| Role | What they own | What they need from Mise | How often |
| --- | --- | --- | --- |
| Area operations manager (primary) | 10 kitchens' daily drivers: orders, speed, complaints, stock | One screen that says which kitchen, which slot, what to do today | 3–4 times a day |
| Kitchen manager | One kitchen's line, roster, hygiene | Tomorrow's prep list; whether the roster covers the rush | Morning and before dinner |
| Central kitchen planner | Daily dispatch of bases, gravies and kits | Forecast quantities per outlet and slot | Night before |
| Packing lead | The pass: what goes in each bag | Which items are missed, at which brand | After a complaint spike |
| City or regional head | Several areas | Which areas are off track and why | Weekly |

## The decisions it supports

| Decision | When | Without Mise | With Mise |
| --- | --- | --- | --- |
| How much should each kitchen prep per slot? | Night before, 7 am | Last week's numbers and gut feel | Forecast per kitchen, brand and slot, as kg and pieces |
| Is the roster enough for tonight? | Afternoon | Wait for the rush, then firefight | Predicted prep time with planned cooks, +1, +2 |
| Which kitchen is losing money? | Weekly | Monthly P&L, too late | Daily orders against the 180 break-even |
| What is the biggest complaint cause, and where? | After close | Read complaints one by one | Tagged complaints, Pareto, hotspots with evidence |
| Who fixes it, and did it work? | Next morning | WhatsApp follow-ups | Owner and first action per hotspot; week-on-week change |

## Requirements

| ID | Requirement | Why | How v1 meets it | Status |
| --- | --- | --- | --- | --- |
| R1 | Forecast orders per kitchen, brand and meal slot, one day ahead | Prep and dispatch are planned per slot; kitchens need 15–20 orders per slot | Gradient-boosted model, backtested on a held-out week | Met |
| R2 | Turn the forecast into a prep list | The central kitchen ships ingredients, not orders | Forecast × recipe quantity per brand | Met |
| R3 | Show kitchens against the 180-order break-even | Below 180 a kitchen loses money | Average daily orders with 180 and 250 lines | Met |
| R4 | Predict prep time; flag likely breaches of the 15-minute promise | About half of complaints are late deliveries | Prep-time model, typical and bad case | Met |
| R5 | Test staffing before the rush | Adding a cook is the fastest fix | Forecast replayed with 0, +1, +2 cooks | Met |
| R6 | Tag every complaint by defect type | Free text can't be counted | Keyword rules in the pipeline; Claude live | Met |
| R7 | Rank defects and find clusters | Fix the vital few first | Pareto, heat map, hotspot rule | Met |
| R8 | Link complaints to their orders | Separates kitchen delay from rider delay | Prep time per complaint; evidence per hotspot | Partly met |
| R9 | Owner and first action per hotspot | A finding without an owner is not acted on | Rule-based owner and action | Met |
| R10 | Show model quality | Managers trust numbers they can check | Model health tab against simple rules | Met |
| R11 | Live data and alerts during service | A 9 pm problem needs a 9 pm alert | Needs POS and platform integration | Next version |
| R12 | Track whether actions worked | Close the loop | Needs an action log; week-on-week change for now | Next version |
| R13 | Works on a phone | Managers are on the floor | Responsive layout | Partly met |

Non-functional: data no older than the last close (daily batch in v1); every number traceable to a source line; no personal customer data stored.

## Metric definitions

| Metric | How it is calculated | Target |
| --- | --- | --- |
| Orders | Count of orders, including those cancelled after acceptance | Forecast |
| Break-even | Average daily orders per kitchen | 180 a day; 250 is clearly profitable |
| Ready within 15 min | Orders with prep time ≤ 15 min ÷ all orders | Above 95% (proposed) |
| Prep time | Wait for a free cook + cooking + 1 min packing | Under 15 min |
| Complaints per 1,000 orders | Complaints ÷ orders × 1,000 | Company runs about 16–17 |
| Forecast error (WAPE) | Sum of absolute errors ÷ sum of actual orders | Below "same day last week" |
| Prep-time error (MAE) | Average absolute difference, minutes | Below "usual time" |
| Share at risk | Orders predicted over 15 min ÷ orders | Under 10% |
| Hotspot | ≥ 6 complaints in the week and ≥ 2.5 × the median kitchen | None |
