"""Shared support links rendered across notification channels."""

from __future__ import annotations

GITHUB_URL = "https://github.com/DartSteven/Nutify"
BUYMEACOFFEE_URL = "https://buymeacoffee.com/dartsteven"


def support_footer_text() -> str:
    return f"Support Nutify: GitHub {GITHUB_URL} | Buy me a coffee {BUYMEACOFFEE_URL}"


def support_footer_markdown() -> str:
    return f"Support: [GitHub]({GITHUB_URL}) • [Buy me a coffee]({BUYMEACOFFEE_URL})"


def support_footer_html() -> str:
    return (
        "<div style='margin-top:14px;text-align:center;font-size:12px;color:#94a3b8'>"
        f"<a href='{GITHUB_URL}' style='color:#60a5fa;text-decoration:none;font-weight:600'>GitHub</a>"
        " &nbsp;•&nbsp; "
        f"<a href='{BUYMEACOFFEE_URL}' style='color:#f59e0b;text-decoration:none;font-weight:600'>Buy me a coffee</a>"
        "</div>"
    )

