"""Alert bot: turn the pipeline's results into a morning alert message and send it.

How it works, in plain words:
  * It reads outputs/dashboard_data.json (written by the pipeline) and applies four rules,
    the same ones the dashboard's bell uses:
      1. Staffing: a kitchen and slot tomorrow with more than 10% of orders at risk of
         passing 15 minutes -> "add 1 cook" or "add 2 cooks".
      2. Hotspots: every complaint hotspot, with its owner and first action.
      3. Break-even: a kitchen forecast below 180 orders tomorrow.
      4. Stock-outs: items switched off during yesterday's service.
  * It writes the alerts to outputs/alerts.json and outputs/alerts.md.
  * It sends them wherever a channel is configured with environment variables:
      TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID   -> a Telegram message
      SLACK_WEBHOOK_URL                       -> a Slack message
      DISCORD_WEBHOOK_URL                     -> a Discord message
    With none set it just prints the message, so it runs anywhere.
"""
import json
import os
import urllib.request

from . import config as C

RANK = {"critical": 0, "warning": 1, "info": 2}
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _day(meta, iso):
    return f"{meta['weekday'].get(iso, '')} {int(iso[8:])} {MON[int(iso[5:7]) - 1]}".strip()


def _rec(w):
    """Cooks to add: 0 if the roster keeps orders at risk at or under 10%, else 1 or 2."""
    if w[5] <= 0.10:
        return 0
    return 1 if w[7] <= 0.10 else 2


def build_alerts(data: dict) -> list:
    m = data["meta"]
    K, S = m["kitchens"], m["slots"]
    last = len(m["dates"]) - 1
    alerts = []

    for w in data["whatif"]:  # [kitchen, slot, cooks, orders, prep0, late0, prep1, late1, prep2, late2]
        n = _rec(w)
        if n:
            alerts.append({
                "severity": "critical", "kind": "staffing", "kitchen": K[w[0]],
                "title": f"Add {n} cook{'s' if n > 1 else ''} at {K[w[0]]} for {S[w[1]].lower()} tomorrow",
                "detail": f"{w[5]:.1%} of {w[3]:.0f} forecast orders at risk of passing 15 min with {w[2]} cooks; "
                          f"{(w[7] if n == 1 else w[9]):.1%} with +{n}.",
                "owner": "Kitchen manager"})

    for h in data["hotspots"]:
        crit = h["n"] / max(h["typical"], 1) >= 6
        alerts.append({
            "severity": "critical" if crit else "warning", "kind": "hotspot", "kitchen": h["kitchen"],
            "title": f"{h['kitchen']}: {h['defect'].lower()} hotspot",
            "detail": f"{h['n']} complaints this week vs {h['typical']:.0f} at a typical kitchen. {h['action']}.",
            "owner": h["owner"]})

    for k, name in enumerate(K):
        orders = sum(r[3] for r in data["tomorrow"] if r[0] == k)
        if orders < m["breakEven"]:
            alerts.append({
                "severity": "warning", "kind": "break-even", "kitchen": name,
                "title": f"{name} forecast below break-even tomorrow",
                "detail": f"{orders:.0f} orders forecast against the {m['breakEven']} needed to cover costs.",
                "owner": "Area manager"})

    for s in data["stockouts"]:  # [day, kitchen, slot, brand, item, minutes, reason]
        if s[0] == last:
            alerts.append({
                "severity": "warning", "kind": "stock-out", "kitchen": K[s[1]],
                "title": f"{s[4]} ran out at {K[s[1]]}",
                "detail": f"{S[s[2]]}, {s[3]}: switched off for {s[5]} min on {_day(m, m['dates'][last])}. {s[6]}.",
                "owner": "Central kitchen dispatch"})

    return sorted(alerts, key=lambda a: RANK[a["severity"]])


def format_message(alerts: list, data: dict, markdown: bool = True) -> str:
    m = data["meta"]
    b = (lambda t: f"*{t}*") if markdown else (lambda t: t)
    crit = sum(a["severity"] == "critical" for a in alerts)
    tomorrow = sum(r[3] for r in data["tomorrow"])
    lines = [b(f"Mise morning alerts for {_day(m, m['tomorrow'])}"),
             f"{m['area']}: {tomorrow:,.0f} orders forecast across {len(m['kitchens'])} kitchens. "
             f"{crit} critical, {len(alerts) - crit} warnings.", ""]
    for a in alerts:
        mark = "🔴" if a["severity"] == "critical" else "🟠"
        lines.append(f"{mark} {b(a['title'])}")
        lines.append(f"    {a['detail']} Owner: {a['owner']}.")
    lines += ["", "Evidence for each alert: " + os.environ.get("MISE_DASHBOARD_URL", "https://tootomar.github.io/mise-kitchen-ops/")]
    return "\n".join(lines)


def _post(url: str, payload: dict) -> None:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


def send(alerts: list, data: dict) -> list:
    """Send to every configured channel. Returns the channels that were used."""
    used = []
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        _post(f"https://api.telegram.org/bot{token}/sendMessage",
              {"chat_id": chat, "text": format_message(alerts, data), "parse_mode": "Markdown",
               "disable_web_page_preview": True})
        used.append("Telegram")
    if os.environ.get("SLACK_WEBHOOK_URL"):
        _post(os.environ["SLACK_WEBHOOK_URL"], {"text": format_message(alerts, data)})
        used.append("Slack")
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        _post(os.environ["DISCORD_WEBHOOK_URL"], {"content": format_message(alerts, data).replace("*", "**")[:1990]})
        used.append("Discord")
    return used


def run(send_messages: bool = True) -> dict:
    data = json.loads((C.OUT_DIR / "dashboard_data.json").read_text(encoding="utf-8"))
    alerts = build_alerts(data)
    (C.OUT_DIR / "alerts.json").write_text(json.dumps(alerts, indent=2, ensure_ascii=False), encoding="utf-8")
    (C.OUT_DIR / "alerts.md").write_text(format_message(alerts, data, markdown=False), encoding="utf-8")
    used = send(alerts, data) if send_messages else []
    return {"alerts": alerts, "channels": used, "text": format_message(alerts, data, markdown=False)}
