"""
Email Parser Service.
Parses raw .eml files and extracts structured fields.
"""

import email
import logging
import re
from email import policy
from email.parser import BytesParser, Parser
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class EmailParser:
    """Parse .eml files and raw email text into structured data."""

    def parse_eml_bytes(self, raw_bytes: bytes) -> Dict[str, Any]:
        """Parse a raw .eml file (bytes) into structured email data."""
        try:
            msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)
            return self._extract_fields(msg)
        except Exception as e:
            logger.error(f"[EmailParser] Failed to parse .eml bytes: {e}")
            return {"error": str(e)}

    def parse_raw_text(self, raw_text: str) -> Dict[str, Any]:
        """Parse a raw email string."""
        try:
            msg = Parser(policy=policy.default).parsestr(raw_text)
            return self._extract_fields(msg)
        except Exception as e:
            logger.warning(f"[EmailParser] Falling back to plain text parse: {e}")
            return {
                "subject": "",
                "sender": "",
                "recipients": [],
                "body": raw_text,
                "html_body": "",
                "attachments": [],
                "headers": {},
                "reply_to": "",
                "x_mailer": "",
                "received_from": [],
            }

    def _extract_fields(self, msg) -> Dict[str, Any]:
        """Extract all relevant fields from a parsed email message."""
        # Body extraction
        body_text, html_body = self._get_body(msg)

        # Attachment detection
        attachments = self._get_attachments(msg)

        # Header analysis
        received_from = self._parse_received_headers(msg)

        return {
            "subject": str(msg.get("Subject", "")),
            "sender": str(msg.get("From", "")),
            "recipients": [str(r) for r in msg.get_all("To", [])],
            "date": str(msg.get("Date", "")),
            "reply_to": str(msg.get("Reply-To", "")),
            "x_mailer": str(msg.get("X-Mailer", "")),
            "message_id": str(msg.get("Message-ID", "")),
            "body": body_text,
            "html_body": html_body,
            "attachments": attachments,
            "received_from": received_from,
            "has_attachments": len(attachments) > 0,
            "attachment_count": len(attachments),
            "suspicious_attachment": self._check_suspicious_attachments(attachments),
        }

    def _get_body(self, msg) -> tuple:
        """Extract plain text and HTML body from email."""
        text_body = ""
        html_body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        text_body += part.get_content() or ""
                    except Exception:
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                text_body += payload.decode("utf-8", errors="replace")
                        except Exception:
                            pass

                elif content_type == "text/html":
                    try:
                        html_body += part.get_content() or ""
                    except Exception:
                        pass
        else:
            try:
                text_body = msg.get_content() or ""
            except Exception:
                try:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        text_body = payload.decode("utf-8", errors="replace")
                except Exception:
                    text_body = str(msg.get_payload())

        return text_body.strip(), html_body.strip()

    def _get_attachments(self, msg) -> list:
        """List all attachments with filename and content type."""
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in disposition:
                    filename = part.get_filename() or "unknown"
                    content_type = part.get_content_type()
                    size = len(part.get_payload(decode=True) or b"")
                    attachments.append({
                        "filename": filename,
                        "content_type": content_type,
                        "size_bytes": size,
                    })
        return attachments

    def _parse_received_headers(self, msg) -> list:
        """Extract all Received headers (hop trail)."""
        received = msg.get_all("Received", [])
        return [str(r)[:200] for r in received]

    def _check_suspicious_attachments(self, attachments: list) -> bool:
        """Flag dangerous attachment types."""
        DANGEROUS_EXTENSIONS = {
            ".exe", ".bat", ".cmd", ".vbs", ".js", ".jar", ".ps1",
            ".scr", ".pif", ".com", ".msi", ".hta", ".wsf", ".reg",
        }
        for att in attachments:
            fname = att.get("filename", "").lower()
            if any(fname.endswith(ext) for ext in DANGEROUS_EXTENSIONS):
                return True
        return False
