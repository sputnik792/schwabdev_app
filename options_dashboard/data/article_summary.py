"""
Fetch article body text and build an extractive summary — no LLM required.

Flow:
  1. Download the page (follow redirects; resolve Google News wrappers)
  2. Extract main article text (trafilatura, then BeautifulSoup fallback)
  3. Rank sentences by word frequency / TextRank-lite and keep the top ones
     in their original order (classic extractive summarization)

This paraphrases nothing — it selects the most representative original sentences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set
from urllib.parse import parse_qs, unquote, urlparse
import math
import re

import requests
import trafilatura
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15

# Minimal English stopword list — enough for frequency scoring without NLTK.
_STOPWORDS: Set[str] = {
    "a", "about", "after", "all", "also", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "between", "both", "but", "by",
    "can", "could", "did", "do", "does", "doing", "down", "during", "each",
    "few", "for", "from", "further", "had", "has", "have", "having", "he",
    "her", "here", "hers", "him", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "just", "me", "more", "most", "my", "no", "nor",
    "not", "now", "of", "on", "once", "only", "or", "other", "our", "out",
    "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "them", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "will", "with", "would", "you", "your", "said", "says", "according",
}


@dataclass
class ArticleContent:
    url: str
    final_url: str
    title: str
    text: str
    summary: str
    sentences_used: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.text.strip() or self.summary.strip())


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def resolve_article_url(url: str, session: Optional[requests.Session] = None) -> str:
    """Follow redirects and unwrap Google News / tracker URLs to the publisher page."""
    session = session or _session()
    current = url.strip()

    # Google News RSS links are wrappers — decode to the real publisher URL first.
    if "news.google." in urlparse(current).netloc.lower():
        try:
            from googlenewsdecoder import new_decoderv1

            decoded = new_decoderv1(current)
            if isinstance(decoded, dict) and decoded.get("status") and decoded.get("decoded_url"):
                current = str(decoded["decoded_url"]).strip()
        except Exception:
            pass

    try:
        resp = session.get(current, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        current = str(resp.url)
    except requests.RequestException:
        return current

    parsed = urlparse(current)
    host = parsed.netloc.lower()

    if "news.google." in host:
        qs = parse_qs(parsed.query)
        for key in ("url", "q"):
            if key in qs and qs[key]:
                candidate = unquote(qs[key][0])
                if candidate.startswith("http"):
                    return resolve_article_url(candidate, session)

    return current


def fetch_html(url: str, session: Optional[requests.Session] = None) -> tuple[str, str]:
    """Return (final_url, html). Tries requests, then trafilatura's fetcher."""
    session = session or _session()
    resolved = resolve_article_url(url, session)

    try:
        resp = session.get(resolved, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"
        return str(resp.url), resp.text
    except requests.RequestException:
        # Some publishers block bare requests; trafilatura's fetcher can still succeed.
        downloaded = trafilatura.fetch_url(resolved)
        if downloaded:
            return resolved, downloaded
        raise


def extract_article_text(html: str, url: str = "") -> tuple[str, str]:
    """
    Extract (title, body_text) from HTML.
    Primary: trafilatura. Fallback: BeautifulSoup paragraph scrape.
    """
    title = ""
    text = ""

    downloaded = trafilatura.extract(
        html,
        url=url or None,
        include_comments=False,
        include_tables=False,
        favor_recall=True,
        output_format="txt",
    )
    meta = trafilatura.extract_metadata(html, default_url=url or None)
    if meta and meta.title:
        title = meta.title.strip()
    if downloaded:
        text = downloaded.strip()

    if text and len(text) >= 200:
        return title, text

    # Fallback: gather <p> / <article> text
    soup = BeautifulSoup(html, "lxml")
    if not title:
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = str(og["content"]).strip()

    blocks: List[str] = []
    root = soup.find("article") or soup.find("main") or soup.body or soup
    for p in root.find_all(["p", "h2"]):
        chunk = p.get_text(" ", strip=True)
        if len(chunk) >= 40:
            blocks.append(chunk)
    fallback = "\n\n".join(blocks).strip()
    if len(fallback) > len(text):
        text = fallback
    return title, text


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“\(])")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]+")


def split_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT.split(cleaned)
    out: List[str] = []
    for part in parts:
        s = part.strip()
        if len(s) < 40:
            continue
        # Drop nav / boilerplate crumbs
        lower = s.lower()
        if lower.startswith("click here") or lower.startswith("sign up"):
            continue
        out.append(s)
    return out


def _tokenize(sentence: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(sentence) if w.lower() not in _STOPWORDS]


def summarize_extractive(
    text: str,
    *,
    max_sentences: int = 5,
    max_chars: int = 1800,
) -> tuple[str, int]:
    """
    Frequency-based extractive summary (Luhn-style).

    Scores each sentence by how often its content words appear in the article,
    then returns the top sentences in original order. No model / LLM involved.
    """
    sentences = split_sentences(text)
    if not sentences:
        clipped = text.strip()
        if len(clipped) > max_chars:
            clipped = clipped[: max_chars - 1].rstrip() + "…"
        return clipped, 0

    if len(sentences) <= max_sentences and len(text) <= max_chars:
        return " ".join(sentences), len(sentences)

    # Document word frequencies
    freqs: dict[str, int] = {}
    tokenized = [_tokenize(s) for s in sentences]
    for tokens in tokenized:
        for t in tokens:
            freqs[t] = freqs.get(t, 0) + 1

    if not freqs:
        chosen = sentences[:max_sentences]
        return " ".join(chosen), len(chosen)

    max_f = max(freqs.values())
    scores: List[float] = []
    for idx, tokens in enumerate(tokenized):
        if not tokens:
            scores.append(0.0)
            continue
        score = sum(freqs[t] / max_f for t in tokens) / math.sqrt(len(tokens))
        # Slight boost for earlier sentences (news leads matter)
        position_boost = 1.15 if idx < 3 else 1.0
        scores.append(score * position_boost)

    # Pick top-k by score, restore chronological order
    ranked = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)
    pick = sorted(ranked[:max_sentences])
    summary = " ".join(sentences[i] for i in pick)

    if len(summary) > max_chars:
        # Drop lowest-scoring kept sentence until under budget
        kept = list(pick)
        while len(" ".join(sentences[i] for i in kept)) > max_chars and len(kept) > 1:
            weakest = min(kept, key=lambda i: scores[i])
            kept.remove(weakest)
        summary = " ".join(sentences[i] for i in kept)
        if len(summary) > max_chars:
            summary = summary[: max_chars - 1].rstrip() + "…"
        return summary, len(kept)

    return summary, len(pick)


def fetch_and_summarize(
    url: str,
    *,
    title_hint: str = "",
    rss_fallback: str = "",
    max_sentences: int = 5,
) -> ArticleContent:
    """Download a news URL and return extracted text + extractive summary."""
    result = ArticleContent(
        url=url,
        final_url=url,
        title=title_hint,
        text="",
        summary="",
    )
    session = _session()
    try:
        final_url, html = fetch_html(url, session)
        result.final_url = final_url
    except Exception as exc:
        result.errors.append(f"Download failed: {exc}")
        if rss_fallback.strip():
            summary, n = summarize_extractive(rss_fallback, max_sentences=max_sentences)
            result.text = rss_fallback.strip()
            result.summary = summary or rss_fallback.strip()
            result.sentences_used = n
            result.errors.append("Used RSS snippet because the full page could not be downloaded.")
        return result

    try:
        title, text = extract_article_text(html, url=result.final_url)
    except Exception as exc:
        result.errors.append(f"Extract failed: {exc}")
        text = ""
        title = ""

    if title:
        result.title = title
    elif not result.title:
        result.title = title_hint or result.final_url

    result.text = text
    if not text.strip():
        if rss_fallback.strip():
            summary, n = summarize_extractive(rss_fallback, max_sentences=max_sentences)
            result.text = rss_fallback.strip()
            result.summary = summary or rss_fallback.strip()
            result.sentences_used = n
            result.errors.append(
                "Could not extract full article text; showing RSS snippet instead."
            )
            return result
        result.errors.append(
            "Could not extract article text (paywall, blocked, or non-article page)."
        )
        return result

    summary, n = summarize_extractive(text, max_sentences=max_sentences)
    result.summary = summary
    result.sentences_used = n
    return result
