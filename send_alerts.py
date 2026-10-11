"""Send this morning's Mise alerts.

    python send_alerts.py            # build alerts from outputs/ and send to configured channels
    python send_alerts.py --dry-run  # only print them

Channels are set with environment variables (see src/mise/alerts.py):
TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, SLACK_WEBHOOK_URL, DISCORD_WEBHOOK_URL.
Run `python run_pipeline.py` first so outputs/dashboard_data.json exists.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from mise import alerts  # noqa: E402


def main():
    dry = "--dry-run" in sys.argv
    res = alerts.run(send_messages=not dry)
    print(res["text"])
    print()
    if dry:
        print("Dry run: nothing sent.")
    elif res["channels"]:
        print("Sent to:", ", ".join(res["channels"]))
    else:
        print("No channel configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, or SLACK_WEBHOOK_URL), so nothing was sent.")


if __name__ == "__main__":
    main()
