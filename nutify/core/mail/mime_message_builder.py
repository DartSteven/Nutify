"""Helpers to build robust MIME email messages with inline images."""

from __future__ import annotations

import base64
import re
from email.charset import Charset, QP
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from typing import List, Tuple


_DATA_URI_RE = re.compile(
    r"""src=(?P<quote>["'])data:image/(?P<subtype>[a-zA-Z0-9.+-]+);base64,(?P<data>[^"']+)(?P=quote)""",
    re.IGNORECASE | re.DOTALL,
)

_UTF8_QP = Charset("utf-8")
_UTF8_QP.header_encoding = QP
_UTF8_QP.body_encoding = QP


def _extract_inline_images(html_content: str) -> Tuple[str, List[Tuple[str, str, bytes]]]:
    """Replace data-uri images with cid refs and return decoded image payloads."""
    attachments: List[Tuple[str, str, bytes]] = []
    cid_counter = 0

    def _replace(match: re.Match) -> str:
        nonlocal cid_counter
        subtype = str(match.group("subtype") or "png").lower()
        payload = str(match.group("data") or "").strip()
        if not payload:
            return match.group(0)
        try:
            decoded = base64.b64decode(payload, validate=False)
        except Exception:
            return match.group(0)
        if not decoded:
            return match.group(0)

        cid_counter += 1
        content_id = f"nutify-inline-{cid_counter}"
        attachments.append((content_id, subtype, decoded))
        quote = match.group("quote")
        return f"src={quote}cid:{content_id}{quote}"

    rendered_html = _DATA_URI_RE.sub(_replace, str(html_content or ""))
    return rendered_html, attachments


def build_html_email_message(
    *,
    to_addr: str,
    from_addr: str,
    subject: str,
    html_content: str,
) -> str:
    """Return full raw RFC822 message for msmtp with inline-image support."""
    safe_to = str(to_addr or "").strip()
    safe_from = str(from_addr or "").strip()
    safe_subject = str(subject or "").strip()
    html_rendered, attachments = _extract_inline_images(str(html_content or ""))

    message = MIMEMultipart("related")
    message["To"] = safe_to
    if safe_from:
        message["From"] = safe_from
    message["Subject"] = safe_subject
    message["Date"] = formatdate(localtime=True)

    alternative = MIMEMultipart("alternative")
    message.attach(alternative)

    plain_fallback = (
        "Nutify notification\n\n"
        "Your client cannot render HTML content.\n"
        "Open this message with an HTML-capable client."
    )
    alternative.attach(MIMEText(plain_fallback, "plain", _UTF8_QP))
    alternative.attach(MIMEText(html_rendered, "html", _UTF8_QP))

    for content_id, subtype, image_bytes in attachments:
        mime_image = MIMEImage(image_bytes, _subtype=subtype)
        mime_image.add_header("Content-ID", f"<{content_id}>")
        mime_image.add_header("Content-Disposition", "inline", filename=f"{content_id}.{subtype}")
        message.attach(mime_image)

    return message.as_string()
