"""Post automation results to #kp-events tagging Kate."""

import os
from slack_sdk import WebClient

SLACK_CHANNEL = "C0434HK1077"  # #kp-events
KATE = "<@U037CLF5N5P>"


def notify(task_name, summary_lines):
    """Post a short automation result summary to Slack tagging Kate.

    Args:
        task_name: e.g. "Weekly Metro Sweep", "Contact Enrichment"
        summary_lines: list of strings, each a bullet point result
    """
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("[Notify] No SLACK_BOT_TOKEN — skipping Slack notification")
        return

    lines = [f":gear: *{task_name} — Results* {KATE}", ""]
    lines.extend(f"• {line}" for line in summary_lines)

    client = WebClient(token=token)
    try:
        client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text="\n".join(lines),
            mrkdwn=True,
        )
        print(f"[Notify] Posted to #kp-events")
    except Exception as e:
        print(f"[Notify] Slack error: {e}")
