"""
Thin client for local Ollama models (HTTP API on localhost:11434).

Default model: smollm2:1.7b — small footprint for summarization experiments.
Also provides a 5-level market-sentiment classifier (very bearish → very bullish).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import re
import shutil
import subprocess
import time

import requests

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "smollm2:1.7b"
# Alternate tags worth trying later from the same UI:
KNOWN_MODELS = [
    "smollm2:1.7b",
    "phi3:mini",
    "qwen2.5:3b",
]

# Ordered bearish → bullish for UI gradient bars.
SENTIMENT_LABELS: Tuple[str, ...] = (
    "very_bearish",
    "bearish",
    "neutral",
    "bullish",
    "very_bullish",
)

# (display name, fill color) — red → gray → green
SENTIMENT_META = {
    "very_bearish": ("Very Bearish", "#b91c1c"),
    "bearish": ("Bearish", "#ef4444"),
    "neutral": ("Neutral", "#94a3b8"),
    "bullish": ("Bullish", "#34d399"),
    "very_bullish": ("Very Bullish", "#059669"),
}

_SENTIMENT_ALIASES = {
    "very bearish": "very_bearish",
    "very_bearish": "very_bearish",
    "extremely bearish": "very_bearish",
    "strongly bearish": "very_bearish",
    "bearish": "bearish",
    "slightly bearish": "bearish",
    "negative": "bearish",
    "neutral": "neutral",
    "mixed": "neutral",
    "balanced": "neutral",
    "bullish": "bullish",
    "slightly bullish": "bullish",
    "positive": "bullish",
    "very bullish": "very_bullish",
    "very_bullish": "very_bullish",
    "extremely bullish": "very_bullish",
    "strongly bullish": "very_bullish",
}

_SENTIMENT_LINE_RE = re.compile(
    r"(?im)^\s*(?:sentiment|label)\s*[:\-]\s*([a-z_ ]+)"
)
_REASON_LINE_RE = re.compile(
    r"(?im)^\s*(?:reason|rationale|why)\s*[:\-]\s*(.+)$"
)


@dataclass
class OllamaStatus:
    reachable: bool
    models: List[str] = field(default_factory=list)
    error: str = ""
    ollama_on_path: bool = False


@dataclass
class SentimentResult:
    """5-level market sentiment for an article (LLM-classified)."""

    label: str = "neutral"
    reason: str = ""
    model: str = ""
    elapsed_sec: float = 0.0
    error: str = ""
    raw: str = ""

    @property
    def ok(self) -> bool:
        return self.label in SENTIMENT_META and not self.error

    @property
    def display_label(self) -> str:
        meta = SENTIMENT_META.get(self.label)
        return meta[0] if meta else self.label.replace("_", " ").title()

    @property
    def color(self) -> str:
        meta = SENTIMENT_META.get(self.label)
        return meta[1] if meta else SENTIMENT_META["neutral"][1]

    @property
    def index(self) -> int:
        try:
            return SENTIMENT_LABELS.index(self.label)
        except ValueError:
            return 2  # neutral


@dataclass
class LlmSummaryResult:
    model: str
    summary: str
    elapsed_sec: float = 0.0
    error: str = ""
    prompt_chars: int = 0
    sentiment: Optional[SentimentResult] = None

    @property
    def ok(self) -> bool:
        return bool(self.summary.strip()) and not self.error


def _base(host: str = DEFAULT_HOST) -> str:
    return host.rstrip("/")


def ollama_binary() -> Optional[str]:
    found = shutil.which("ollama")
    if found:
        return found
    # Common Windows install locations
    candidates = [
        r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe",
        r"%ProgramFiles%\Ollama\ollama.exe",
    ]
    import os

    for pattern in candidates:
        path = os.path.expandvars(pattern)
        if os.path.isfile(path):
            return path
    return None


def check_ollama(host: str = DEFAULT_HOST) -> OllamaStatus:
    status = OllamaStatus(reachable=False, ollama_on_path=bool(ollama_binary()))
    try:
        resp = requests.get(f"{_base(host)}/api/tags", timeout=3)
        resp.raise_for_status()
        data = resp.json()
        status.reachable = True
        status.models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception as exc:
        status.error = str(exc)
    return status


def ensure_model(model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST, timeout: int = 600) -> str:
    """
    Pull model if missing. Returns empty string on success, else an error message.
    Prefer calling this from a worker thread — pulls can take a few minutes.
    """
    status = check_ollama(host)
    if not status.reachable:
        return (
            "Ollama is not running. Install from https://ollama.com/download "
            "then start it (or run: ollama serve)."
            + (f" Detail: {status.error}" if status.error else "")
        )

    if any(m == model or m.startswith(model) for m in status.models):
        return ""

    try:
        resp = requests.post(
            f"{_base(host)}/api/pull",
            json={"name": model, "stream": False},
            timeout=timeout,
        )
        if resp.status_code >= 400:
            return f"Pull failed ({resp.status_code}): {resp.text[:300]}"
        payload = resp.json() if resp.content else {}
        if isinstance(payload, dict) and payload.get("error"):
            return str(payload["error"])
        return ""
    except Exception as exc:
        binary = ollama_binary()
        if not binary:
            return f"Could not pull model via API: {exc}"
        try:
            completed = subprocess.run(
                [binary, "pull", model],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if completed.returncode != 0:
                return (
                    completed.stderr.strip()
                    or completed.stdout.strip()
                    or f"ollama pull failed ({completed.returncode})"
                )
            return ""
        except Exception as cli_exc:
            return f"Pull failed: {exc}; CLI also failed: {cli_exc}"


def normalize_sentiment_label(raw: str) -> Optional[str]:
    """Map free-form model output to one of SENTIMENT_LABELS, or None."""
    cleaned = re.sub(r"\s+", " ", (raw or "").strip().lower().replace("-", " "))
    underscored = cleaned.replace(" ", "_")
    if underscored in SENTIMENT_META:
        return underscored
    if cleaned in _SENTIMENT_ALIASES:
        return _SENTIMENT_ALIASES[cleaned]
    if underscored in _SENTIMENT_ALIASES:
        return _SENTIMENT_ALIASES[underscored]
    for label in SENTIMENT_LABELS:
        if label in underscored or label.replace("_", " ") in cleaned:
            return label
    return None


def parse_sentiment_block(text: str, *, model: str = "", elapsed_sec: float = 0.0) -> SentimentResult:
    """Extract SENTIMENT / REASON lines from model output."""
    raw = (text or "").strip()
    label = "neutral"
    reason = ""
    error = ""

    match = _SENTIMENT_LINE_RE.search(raw)
    if match:
        parsed = normalize_sentiment_label(match.group(1))
        if parsed:
            label = parsed
        else:
            error = f"Unrecognized sentiment: {match.group(1).strip()}"
    else:
        # Whole response might just be the label
        parsed = normalize_sentiment_label(raw.splitlines()[0] if raw else "")
        if parsed:
            label = parsed
        else:
            error = "Could not parse sentiment label from model output."

    reason_match = _REASON_LINE_RE.search(raw)
    if reason_match:
        reason = reason_match.group(1).strip()

    return SentimentResult(
        label=label if not error else "neutral",
        reason=reason,
        model=model,
        elapsed_sec=elapsed_sec,
        error=error,
        raw=raw,
    )


def _chat_ollama(
    *,
    system: str,
    user: str,
    model: str,
    host: str,
    temperature: float,
    num_predict: int,
    timeout: int = 180,
) -> tuple[str, float, str]:
    """
    Low-level /api/chat helper.
    Returns (content, elapsed_sec, error). error is empty on success.
    """
    started = time.perf_counter()
    try:
        resp = requests.post(
            f"{_base(host)}/api/chat",
            json={
                "model": model,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                },
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=timeout,
        )
        elapsed = time.perf_counter() - started
        if resp.status_code >= 400:
            return "", elapsed, f"Ollama error {resp.status_code}: {resp.text[:400]}"
        data = resp.json()
        message = (data.get("message") or {}).get("content") or data.get("response") or ""
        return message.strip(), elapsed, ""
    except Exception as exc:
        return "", time.perf_counter() - started, str(exc)


def _clip_article(text: str, max_input_chars: int) -> str:
    clipped = (text or "").strip()
    if len(clipped) > max_input_chars:
        clipped = clipped[: max_input_chars - 1].rstrip() + "…"
    return clipped


def analyze_sentiment_with_ollama(
    text: str,
    *,
    title: str = "",
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    max_input_chars: int = 4000,
    temperature: float = 0.1,
) -> SentimentResult:
    """Classify article tone for traders on a 5-level bullish/bearish scale."""
    clipped = _clip_article(text, max_input_chars)
    if not clipped:
        return SentimentResult(error="No article text for sentiment analysis.", model=model)

    labels = ", ".join(SENTIMENT_LABELS)
    system = (
        "You are a market sentiment classifier for equity traders. "
        "Judge how the article's content would typically be read for the company or stock: "
        "positive catalysts → bullish, negative news → bearish, mixed/unclear → neutral. "
        "Do not invent facts. Reply with EXACTLY two lines in this format:\n"
        "SENTIMENT: <label>\n"
        "REASON: <one short sentence>\n"
        f"Where <label> is one of: {labels}"
    )
    user = (
        f"Title: {title or '(untitled)'}\n\nArticle:\n{clipped}\n\n"
        "Classify sentiment now:"
    )

    content, elapsed, err = _chat_ollama(
        system=system,
        user=user,
        model=model,
        host=host,
        temperature=temperature,
        num_predict=80,
    )
    if err:
        return SentimentResult(model=model, elapsed_sec=elapsed, error=err)
    result = parse_sentiment_block(content, model=model, elapsed_sec=elapsed)
    if result.error and not result.reason:
        # Keep parse error; still expose raw for debugging
        result.raw = content
    return result


def summarize_with_ollama(
    text: str,
    *,
    title: str = "",
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    max_input_chars: int = 6000,
    temperature: float = 0.2,
    include_sentiment: bool = True,
) -> LlmSummaryResult:
    """Ask a local Ollama model to paraphrase/summarize article text (and optionally sentiment)."""
    clipped = _clip_article(text, max_input_chars)
    if not clipped:
        return LlmSummaryResult(model=model, summary="", error="No article text to summarize.")

    labels = ", ".join(SENTIMENT_LABELS)
    if include_sentiment:
        system = (
            "You are a concise financial news editor. "
            "Summarize the article in plain English for a stock trader. "
            "Use 3-5 short sentences. Cover: what happened, why it matters, and any numbers "
            "(price moves, %, revenue, guidance) if present. "
            "Do not invent facts. Do not use bullet points. Do not mention that you are an AI.\n\n"
            "After the summary, add exactly these two lines:\n"
            "SENTIMENT: <label>\n"
            "REASON: <one short sentence>\n"
            f"Where <label> is one of: {labels}"
        )
        user = (
            f"Title: {title or '(untitled)'}\n\nArticle:\n{clipped}\n\n"
            "Write the summary, then SENTIMENT and REASON:"
        )
        num_predict = 340
    else:
        system = (
            "You are a concise financial news editor. "
            "Summarize the article in plain English for a stock trader. "
            "Use 3-5 short sentences. Cover: what happened, why it matters, and any numbers "
            "(price moves, %, revenue, guidance) if present. "
            "Do not invent facts. Do not use bullet points. Do not mention that you are an AI."
        )
        user = f"Title: {title or '(untitled)'}\n\nArticle:\n{clipped}\n\nWrite the summary now:"
        num_predict = 280

    content, elapsed, err = _chat_ollama(
        system=system,
        user=user,
        model=model,
        host=host,
        temperature=temperature,
        num_predict=num_predict,
    )
    if err:
        return LlmSummaryResult(
            model=model,
            summary="",
            elapsed_sec=elapsed,
            error=err,
            prompt_chars=len(clipped),
        )

    sentiment: Optional[SentimentResult] = None
    summary = content
    if include_sentiment:
        sentiment = parse_sentiment_block(content, model=model, elapsed_sec=elapsed)
        # Strip trailing SENTIMENT/REASON lines from the prose summary
        summary = _SENTIMENT_LINE_RE.split(content)[0].strip()
        summary = re.sub(r"(?im)^\s*(?:reason|rationale|why)\s*[:\-].*$", "", summary).strip()
        if not summary:
            summary = content.strip()

    return LlmSummaryResult(
        model=model,
        summary=summary,
        elapsed_sec=elapsed,
        prompt_chars=len(clipped),
        sentiment=sentiment,
    )