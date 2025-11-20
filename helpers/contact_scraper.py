import re
import time
import random
import html
import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import pandas as pd

from helpers.contact_scraper_config import (
    HEADERS,
    REQUEST_TIMEOUT,
    MAX_BYTES,
    PAUSE_MIN,
    PAUSE_MAX,
    CANDIDATE_PATHS,
    MAX_EXTRA_LINKS,
    KEYWORDS_LINK,
    KEYWORDS_TEXT,
    EMAIL_REGEX_PATTERN,
    PRIVACY_HANDLE_PATTERN,
    SCORE_EMAIL,
    SCORE_MAILTO,
    SCORE_JSONLD_EMAIL,
    SCORE_FORM,
    SCORE_LINK,
    SCORE_CONTEXT,
    SCORE_KEYWORD_MATCH,
    SCORE_PRIVACY_HANDLE,
    MAX_SCORE,
    TOP_PICKS_PER_DOMAIN,
    OUTPUT_COLUMNS,
    EXTRACT_TEXT_EMAILS,
    EXTRACT_MAILTO_LINKS,
    EXTRACT_PRIVACY_LINKS,
    EXTRACT_FORM_BUTTONS,
    EXTRACT_JSONLD,
    EXTRACT_CONTEXT_KEYWORDS,
    FOLLOW_HOMEPAGE_LINKS,
    CONTEXT_SNIPPET_RADIUS,
)

try:
    from helpers.language_detector import (
        detect_html_language,
        get_language_keywords,
        is_supported_language,
    )

    LANGUAGE_DETECTOR_AVAILABLE = True
except ImportError:
    LANGUAGE_DETECTOR_AVAILABLE = False


@dataclass
class Finding:
    domain: str
    page_url: str
    found_type: str
    value: str
    anchor_text: str
    context_snippet: str
    relevance_score: int
    status_code: Optional[int]
    note: str
    detected_language: Optional[str] = None
    language_confidence: Optional[float] = None


EMAIL_REGEX = re.compile(EMAIL_REGEX_PATTERN, re.IGNORECASE)
PRIVACY_HANDLE = re.compile(PRIVACY_HANDLE_PATTERN, re.IGNORECASE)
COMPILED_KEYWORDS_LINK = [re.compile(pat, re.IGNORECASE) for pat in KEYWORDS_LINK]
COMPILED_KEYWORDS_TEXT = [re.compile(pat, re.IGNORECASE) for pat in KEYWORDS_TEXT]


def normalize_domain(domain: str) -> str:
    d = domain.strip()
    if d.startswith(("http://", "https://")):
        return urlparse(d).netloc
    return d


def base_url_for(domain: str) -> str:
    return f"https://{domain}"


def polite_pause():
    time.sleep(random.uniform(PAUSE_MIN, PAUSE_MAX))


def get_page(
    session: requests.Session, url: str, logger: Optional[logging.Logger] = None
) -> Tuple[Optional[requests.Response], Optional[str]]:
    try:
        resp = session.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            stream=True,
        )

        content = b""
        for chunk in resp.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_BYTES:
                if logger:
                    logger.debug(f"Truncated download at {MAX_BYTES} bytes for {url}")
                break

        encoding = resp.encoding or "utf-8"
        text = content.decode(encoding, errors="replace")
        return resp, text

    except requests.Timeout:
        if logger:
            logger.warning(f"Timeout accessing {url}")
        return None, None
    except requests.RequestException as e:
        if logger:
            logger.warning(f"Request error for {url}: {e}")
        return None, None
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error fetching {url}: {e}")
        return None, None


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def snippet_around(
    full_text: str, needle: str, radius: int = CONTEXT_SNIPPET_RADIUS
) -> str:
    try:
        i = full_text.lower().find(needle.lower())
        if i == -1:
            return ""
        start = max(0, i - radius)
        end = min(len(full_text), i + len(needle) + radius)
        return clean_text(full_text[start:end])
    except Exception:
        return ""


def score_finding(found_type: str, anchor_text: str, href_or_email: str) -> int:
    score = 0
    at = anchor_text.lower()
    hv = (href_or_email or "").lower()

    if found_type in ("email", "mailto"):
        score += SCORE_EMAIL
    elif found_type == "jsonld_email":
        score += SCORE_JSONLD_EMAIL
    elif found_type == "form":
        score += SCORE_FORM
    elif found_type == "link":
        score += SCORE_LINK
    elif found_type == "context":
        score += SCORE_CONTEXT

    for pat in COMPILED_KEYWORDS_LINK:
        if pat.search(at) or pat.search(hv):
            score += SCORE_KEYWORD_MATCH
            break

    if found_type in ("email", "mailto", "jsonld_email"):
        if PRIVACY_HANDLE.search(hv):
            score += SCORE_PRIVACY_HANDLE

    return min(score, MAX_SCORE)


def is_probable_form_link(href: str, text: str) -> bool:
    target = f"{href} {text}".lower()
    needles = [
        "privacy request",
        "data request",
        "dsar",
        "delete my data",
        "delete account",
        "do not sell",
        "your privacy choices",
        "ccpa",
        "cpra",
        "gdpr",
        "erasure",
        "erase",
        "contact",
    ]
    return any(n in target for n in needles)


def dedupe_findings(findings: List[Finding]) -> List[Finding]:
    """Remove duplicate findings"""
    seen: Set[Tuple[str, str, str]] = set()
    out = []
    for f in findings:
        key = (f.domain, f.found_type, f.value.lower())
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def extract_jsonld_emails(soup: BeautifulSoup) -> List[str]:
    emails = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
            blocks = data if isinstance(data, list) else [data]

            for b in blocks:
                if not isinstance(b, dict):
                    continue

                if "contactPoint" in b and isinstance(b["contactPoint"], list):
                    for cp in b["contactPoint"]:
                        if isinstance(cp, dict):
                            em = cp.get("email")
                            if em and EMAIL_REGEX.search(em):
                                emails.append(em)

                if "email" in b and isinstance(b["email"], str):
                    if EMAIL_REGEX.search(b["email"]):
                        emails.append(b["email"])

        except json.JSONDecodeError:
            continue
        except Exception:
            continue

    return list(dict.fromkeys(emails))


def extract_from_page(
    domain: str,
    page_url: str,
    html_text: str,
    status_code: Optional[int],
    logger: Optional[logging.Logger] = None,
) -> List[Finding]:
    findings: List[Finding] = []

    try:
        soup = BeautifulSoup(html_text, "lxml")
    except Exception:
        soup = BeautifulSoup(html_text, "html.parser")

    full_text = soup.get_text(separator=" ", strip=True)

    detected_lang = None
    lang_confidence = None
    if LANGUAGE_DETECTOR_AVAILABLE:
        try:
            detected_lang, _, lang_confidence = detect_html_language(
                html_text, page_url
            )
            if logger:
                logger.debug(
                    f"Detected {detected_lang} (conf: {lang_confidence}) for {page_url}"
                )
        except Exception as e:
            if logger:
                logger.debug(f"Language detection failed for {page_url}: {e}")

    lang_specific_keywords = []
    if detected_lang and is_supported_language(detected_lang):
        lang_specific_keywords = get_language_keywords(detected_lang)
        if logger:
            logger.debug(
                f"Using {len(lang_specific_keywords)} keywords for {detected_lang}"
            )

    effective_keywords_link = KEYWORDS_LINK + lang_specific_keywords
    effective_keywords_text = KEYWORDS_TEXT + lang_specific_keywords
    effective_compiled_keywords_link = [
        re.compile(p, re.IGNORECASE) for p in effective_keywords_link
    ]
    effective_compiled_keywords_text = [
        re.compile(p, re.IGNORECASE) for p in effective_keywords_text
    ]

    if EXTRACT_TEXT_EMAILS:
        for m in EMAIL_REGEX.finditer(html_text):
            email = m.group(0)
            findings.append(
                Finding(
                    domain=domain,
                    page_url=page_url,
                    found_type="email",
                    value=email,
                    anchor_text="",
                    context_snippet=snippet_around(full_text, email),
                    relevance_score=score_finding("email", "", email),
                    status_code=status_code,
                    note="text_email",
                    detected_language=detected_lang,
                    language_confidence=lang_confidence,
                )
            )

    if EXTRACT_MAILTO_LINKS:
        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            if href.lower().startswith("mailto:"):
                email = href.split(":", 1)[1].split("?")[0]
                text = clean_text(a.get_text(" ", strip=True))
                findings.append(
                    Finding(
                        domain=domain,
                        page_url=page_url,
                        found_type="mailto",
                        value=email,
                        anchor_text=text,
                        context_snippet=snippet_around(full_text, text or email),
                        relevance_score=score_finding("mailto", text, email),
                        status_code=status_code,
                        note="mailto_link",
                        detected_language=detected_lang,
                        language_confidence=lang_confidence,
                    )
                )

    if EXTRACT_PRIVACY_LINKS:
        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            if not href or href.startswith(("#", "mailto:")):
                continue

            abs_href = urljoin(page_url, href)
            if not abs_href.startswith(("http://", "https://")):
                continue

            text = clean_text(a.get_text(" ", strip=True))
            matched = any(
                pat.search(href) or pat.search(text)
                for pat in effective_compiled_keywords_link
            )

            if not matched and not is_probable_form_link(href, text):
                continue

            findings.append(
                Finding(
                    domain=domain,
                    page_url=page_url,
                    found_type="link",
                    value=abs_href,
                    anchor_text=text,
                    context_snippet=snippet_around(full_text, text or href),
                    relevance_score=score_finding("link", text, abs_href),
                    status_code=status_code,
                    note="keyword_link",
                    detected_language=detected_lang,
                    language_confidence=lang_confidence,
                )
            )

    if EXTRACT_FORM_BUTTONS:
        for btn in soup.find_all(["button", "input"]):
            text = clean_text(
                btn.get_text(" ", strip=True)
                if btn.name == "button"
                else btn.get("value", "") or ""
            )
            if text and is_probable_form_link("", text):
                findings.append(
                    Finding(
                        domain=domain,
                        page_url=page_url,
                        found_type="form",
                        value=page_url,
                        anchor_text=text,
                        context_snippet=snippet_around(full_text, text),
                        relevance_score=score_finding("form", text, page_url),
                        status_code=status_code,
                        note="button_form_candidate",
                        detected_language=detected_lang,
                        language_confidence=lang_confidence,
                    )
                )

    if EXTRACT_JSONLD:
        for em in extract_jsonld_emails(soup):
            findings.append(
                Finding(
                    domain=domain,
                    page_url=page_url,
                    found_type="jsonld_email",
                    value=em,
                    anchor_text="",
                    context_snippet=snippet_around(full_text, em),
                    relevance_score=score_finding("jsonld_email", "", em),
                    status_code=status_code,
                    note="jsonld",
                    detected_language=detected_lang,
                    language_confidence=lang_confidence,
                )
            )

    if EXTRACT_CONTEXT_KEYWORDS:
        for pat in effective_compiled_keywords_text:
            m = pat.search(full_text)
            if m:
                findings.append(
                    Finding(
                        domain=domain,
                        page_url=page_url,
                        found_type="context",
                        value=m.group(0),
                        anchor_text="",
                        context_snippet=snippet_around(full_text, m.group(0)),
                        relevance_score=score_finding("context", "", ""),
                        status_code=status_code,
                        note="body_keyword",
                        detected_language=detected_lang,
                        language_confidence=lang_confidence,
                    )
                )

    return findings


def crawl_domain(domain: str, logger: Optional[logging.Logger] = None) -> List[Finding]:
    findings: List[Finding] = []
    dom = normalize_domain(domain)

    if not dom:
        if logger:
            logger.warning(f"Invalid domain: {domain}")
        return findings

    base = base_url_for(dom)
    tried_urls: Set[str] = set()

    with requests.Session() as s:
        for path in CANDIDATE_PATHS:
            url = urljoin(base, path)
            if url in tried_urls:
                continue

            tried_urls.add(url)
            polite_pause()

            resp, text = get_page(s, url, logger)
            if not resp or not text:
                continue

            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
                continue

            page_findings = extract_from_page(
                dom, resp.url, text, resp.status_code, logger
            )
            findings.extend(page_findings)

            if path == "/" and FOLLOW_HOMEPAGE_LINKS:
                try:
                    soup = BeautifulSoup(text, "lxml")
                except Exception:
                    soup = BeautifulSoup(text, "html.parser")

                extra_links = []
                for a in soup.find_all("a", href=True):
                    txt = clean_text(a.get_text(" ", strip=True))
                    href = a.get("href") or ""
                    target = (href + " " + txt).lower()

                    if any(
                        k in target
                        for k in [
                            "privacy",
                            "ccpa",
                            "cpra",
                            "do-not-sell",
                            "privacy-choices",
                            "contact",
                            "impressum",
                            "datenschutz",
                        ]
                    ):
                        extra_links.append(urljoin(resp.url, href))

                extra_links = list(dict.fromkeys(extra_links))[:MAX_EXTRA_LINKS]

                for u in extra_links:
                    if u in tried_urls:
                        continue
                    tried_urls.add(u)
                    polite_pause()

                    r2, t2 = get_page(s, u, logger)
                    if not r2 or not t2:
                        continue

                    ct2 = (r2.headers.get("Content-Type") or "").lower()
                    if "text/html" not in ct2 and "application/xhtml+xml" not in ct2:
                        continue

                    findings.extend(
                        extract_from_page(dom, r2.url, t2, r2.status_code, logger)
                    )

    findings = dedupe_findings(findings)
    findings.sort(key=lambda x: x.relevance_score, reverse=True)

    if logger:
        logger.info(f"Found {len(findings)} privacy contact points for {dom}")

    return findings


def findings_to_dataframe(findings: List[Finding]) -> pd.DataFrame:
    rows = [asdict(f) for f in findings if f.found_type != "context"]
    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    df = pd.DataFrame(rows)
    df = df[OUTPUT_COLUMNS]
    return df


def get_top_picks(df: pd.DataFrame, top_n: int = TOP_PICKS_PER_DOMAIN) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    top_rows = []
    for dom, group in df.groupby("domain"):
        top_rows.append(
            group.sort_values("relevance_score", ascending=False).head(top_n)
        )

    return (
        pd.concat(top_rows, ignore_index=True)
        if top_rows
        else pd.DataFrame(columns=OUTPUT_COLUMNS)
    )


def save_findings(
    findings: List[Finding],
    output_file: str = "privacy_contacts.csv",
    logger: Optional[logging.Logger] = None,
) -> None:
    df = findings_to_dataframe(findings)

    if df.empty:
        if logger:
            logger.warning("No findings to save")
        return

    df.to_csv(output_file, index=False, encoding="utf-8")

    if logger:
        logger.info(f"Saved {len(df)} findings to {output_file}")


def scrape_privacy_contacts(
    domain: str, logger: Optional[logging.Logger] = None
) -> List[Finding]:
    if logger:
        logger.info(f"[Privacy Contact Scraper] Starting scrape for {domain}")

    findings = crawl_domain(domain, logger)

    if logger:
        logger.info(
            f"[Privacy Contact Scraper] Completed: {len(findings)} findings for {domain}"
        )

    return findings
