"""Ask Mise from the terminal: a chatbot over the pipeline's results, answered by Claude.

    export ANTHROPIC_API_KEY=...      # your key from console.anthropic.com
    python ask_mise.py                # chat; type 'quit' to stop
    python ask_mise.py "Which kitchens need cooks tomorrow?"

It sends Claude a compact summary of outputs/dashboard_data.json plus today's alerts,
and keeps the conversation so follow-up questions work. The dashboard has the same
assistant built in (the "Ask Mise" button).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from mise import alerts, config as C  # noqa: E402

MODEL = os.environ.get("MISE_MODEL", "claude-haiku-4-5")


def context(d: dict) -> str:
    m = d["meta"]
    K, S = m["kitchens"], m["slots"]
    days = len(m["dates"])
    out = [f"Area {m['area']}; kitchens {', '.join(K)}; brands {', '.join(m['brands'])}.",
           f"Last 7 days {m['dates'][0]} to {m['dates'][-1]}; tomorrow {m['tomorrow']}. Break-even {m['breakEven']} orders/day; "
           f"{m['strong']}+ clearly profitable; prep promise {m['promise']} min."]
    out.append("Kitchen | avg daily orders last 7 days | tomorrow forecast | dinner cooks, prep min, at risk, +1, +2:")
    for k, n in enumerate(K):
        avg = sum(c[3] for c in d["cells"] if c[1] == k) / days
        tom = sum(r[3] for r in d["tomorrow"] if r[0] == k)
        w = next(w for w in d["whatif"] if w[0] == k and w[1] == 3)
        out.append(f"- {n} | {avg:.0f} | {tom:.0f} | {w[2]}, {w[4]:.1f}, {w[5]:.0%}, {w[7]:.0%}, {w[9]:.0%}")
    out.append("Hotspots:")
    for h in d["hotspots"]:
        out.append(f"- {h['kitchen']} {h['defect']}: {h['n']} vs {h['typical']:.0f} typical; {'; '.join(h['evidence'][1:])}; "
                   f"owner {h['owner']}; action {h['action']}")
    counts = {t: sum(1 for c in d["complaints"] if c[5] == i) for i, t in enumerate(m["tags"])}
    out.append("Complaints last 7 days: " + ", ".join(f"{t} {n}" for t, n in counts.items()))
    out.append("Stock-outs: " + "; ".join(f"{m['dates'][s[0]]} {K[s[1]]} {S[s[2]]} {s[4]} {s[5]} min" for s in d["stockouts"]))
    f, p = d["models"]["forecast"], d["models"]["prep"]
    out.append(f"Models: forecast WAPE {f['wape']:.1%} vs {f['baseline']:.1%} baseline; prep MAE {p['mae']:.2f} vs {p['baseline']:.2f} min.")
    out.append("Alerts: " + "; ".join(f"[{a['severity']}] {a['title']}" for a in alerts.build_alerts(d)))
    return "\n".join(out)


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first (see the docstring). The dashboard's Ask Mise button works without it.")
    import anthropic

    d = json.loads((C.OUT_DIR / "dashboard_data.json").read_text(encoding="utf-8"))
    system = ("You are Mise, an operations assistant for an area manager running 10 multi-brand cloud kitchens in "
              "Bengaluru. Answer only from the data below; if it doesn't cover the question, say so. Be brief and "
              "practical, give numbers with units, and name the owner and first action when something needs doing. "
              "The data is synthetic.\n\nDATA\n" + context(d))
    client, history = anthropic.Anthropic(), []
    one_shot = " ".join(sys.argv[1:]).strip()
    while True:
        q = one_shot or input("\nYou: ").strip()
        if q.lower() in {"quit", "exit", ""}:
            break
        history.append({"role": "user", "content": q})
        msg = client.messages.create(model=MODEL, max_tokens=600, system=system, messages=history)
        answer = msg.content[0].text
        history.append({"role": "assistant", "content": answer})
        print("\nMise:", answer)
        if one_shot:
            break


if __name__ == "__main__":
    main()
