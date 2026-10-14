"""
URL Scanner Service.
Analyzes URLs found in email body for phishing indicators.
"""

import re
import logging
from urllib.parse import urlparse
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ── Suspicious patterns ────────────────────────────────────────────────────────
SUSPICIOUS_TLDS = {
    ".xyz", ".tk", ".ml", ".ga", ".cf", ".gq", ".top", ".work",
    ".click", ".link", ".download", ".zip", ".review", ".country",
    ".stream", ".gdn", ".racing", ".win", ".date", ".faith",
}

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "cli.gs", "yfrog.com", "migre.me", "ff.im",
    "tiny.cc", "url4.eu", "tr.im", "twit.ac", "su.pr", "twurl.nl",
    "snipurl.com", "short.to", "short.ie", "u.bb", "yourls.org",
    "prettylinkpro.com", "youtu.be",
}

SUSPICIOUS_KEYWORDS_IN_URL = [
    "login", "signin", "verify", "account", "secure", "banking",
    "paypal", "amazon", "microsoft", "apple", "google", "facebook",
    "update", "confirm", "password", "credential", "suspend",
]

# Regex to extract URLs from text
URL_REGEX = re.compile(
    r"\b(?:https?://[^\s<>\"']+|www\.[^\s<>\"']+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}/[^\s<>\"'\s]*)",
    re.IGNORECASE,
)


class URLScanner:
    """Scans URLs found in email for phishing indicators."""

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Extract and analyze all URLs from email body text."""
        urls = self._extract_urls(text)
        analyzed = [self._analyze_url(url) for url in urls]

        suspicious = [u for u in analyzed if u["is_suspicious"]]
        total_risk_score = sum(u["risk_score"] for u in analyzed)

        return {
            "total_urls": len(urls),
            "suspicious_count": len(suspicious),
            "urls": analyzed,
            "total_risk_score": total_risk_score,
            "has_http_only": any(not u["is_https"] for u in analyzed),
            "has_shortened": any(u["is_shortened"] for u in analyzed),
            "has_suspicious_tld": any(u["suspicious_tld"] for u in analyzed),
        }

    def _extract_urls(self, text: str) -> List[str]:
        """Find all URLs in the given text."""
        return URL_REGEX.findall(text)

    def _analyze_url(self, url: str) -> Dict[str, Any]:
        """Analyze a single URL for risk factors."""
        risk_score = 0
        flags = []

        # Normalize
        if not url.startswith(("http://", "https://")):
            url = "http://" + url

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            scheme = parsed.scheme
        except Exception:
            return {"url": url, "is_suspicious": True, "risk_score": 10, "flags": ["parse_error"], "is_https": False, "is_shortened": False, "suspicious_tld": False}

        # ── Check HTTPS ─────────────────────────────────────────────────────
        is_https = scheme == "https"
        if not is_https:
            risk_score += 2
            flags.append("no_https")

        # ── URL shortener ───────────────────────────────────────────────────
        is_shortened = any(s in domain for s in URL_SHORTENERS)
        if is_shortened:
            risk_score += 5
            flags.append("url_shortener")

        # ── Suspicious TLD ──────────────────────────────────────────────────
        suspicious_tld = any(domain.endswith(tld) for tld in SUSPICIOUS_TLDS)
        if suspicious_tld:
            risk_score += 4
            flags.append("suspicious_tld")

        # ── Suspicious keywords in URL ───────────────────────────────────────
        kw_hits = [kw for kw in SUSPICIOUS_KEYWORDS_IN_URL if kw in domain + path]
        if kw_hits:
            risk_score += len(kw_hits) * 2
            flags.append(f"suspicious_keywords:{','.join(kw_hits)}")

        # ── IP address instead of domain ─────────────────────────────────────
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", domain):
            risk_score += 6
            flags.append("ip_address_as_domain")

        # ── Excessive subdomains ─────────────────────────────────────────────
        subdomain_count = domain.count(".")
        if subdomain_count > 3:
            risk_score += 3
            flags.append("excessive_subdomains")

        # ── Long URL ─────────────────────────────────────────────────────────
        if len(url) > 100:
            risk_score += 1
            flags.append("long_url")

        # ── @-sign in URL (redirect trick) ───────────────────────────────────
        if "@" in url:
            risk_score += 5
            flags.append("at_sign_in_url")

        # ── Double slash redirect ─────────────────────────────────────────────
        if "//" in path:
            risk_score += 3
            flags.append("double_slash_redirect")

        is_suspicious = risk_score >= 4

        return {
            "url": url,
            "domain": domain,
            "is_https": is_https,
            "is_shortened": is_shortened,
            "suspicious_tld": suspicious_tld,
            "is_suspicious": is_suspicious,
            "risk_score": risk_score,
            "flags": flags,
        }
