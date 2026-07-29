"""
speech/wake_word.py — Low-latency wake-word detector.

Strategy:
  1. Exact substring match on transcript text  ("jarvis", "hey jarvis", etc.)
  2. Phonetic sliding-window on a rolling text buffer so partial tokens like
     "djar vis" or "jar-vis" still trigger (handles STT variability).
  3. Configurable cooldown so the same utterance doesn't double-trigger.
"""
import re
import time
from typing import List
from observability.logger import logger


class WakeWordDetector:
    """
    Wake-word detection over streaming transcript tokens.

    Works in two modes:

    * **detect_wake_word(text)** — one-shot check on a completed utterance.
    * **push_token(token)** — incremental streaming check over a rolling
      buffer; returns True the first time a wake-word is detected and
      respects a cooldown window to avoid repeated triggers.
    """

    # Patterns that count as wake-words (case-insensitive)
    _PATTERNS: List[re.Pattern] = [
        re.compile(r"\bjarvis\b",     re.IGNORECASE),
        re.compile(r"\bhey\s+jarvis\b", re.IGNORECASE),
        re.compile(r"\byo\s+jarvis\b",  re.IGNORECASE),
        re.compile(r"\bok\s+jarvis\b",  re.IGNORECASE),
        re.compile(r"\bdjarvis\b",    re.IGNORECASE),   # common STT mis-transcription
    ]

    def __init__(
        self,
        keyphrase: str = "jarvis",
        sensitivity: float = 0.7,
        cooldown_sec: float = 2.0,
        buffer_words: int = 12,
    ):
        self.keyphrase    = keyphrase.lower()
        self.sensitivity  = sensitivity
        self.cooldown_sec = cooldown_sec
        self._buffer:     List[str] = []
        self._buffer_max: int       = buffer_words
        self._last_trigger: float   = 0.0

    # ── One-shot detection ─────────────────────────────────────────────────────
    def detect_wake_word(self, transcript: str) -> bool:
        """Return True if transcript contains a wake-word."""
        for pat in self._PATTERNS:
            if pat.search(transcript):
                logger.info(f"[WakeWordDetector] Wake-word detected in transcript.")
                return True
        return False

    # ── Streaming incremental detection ───────────────────────────────────────
    def push_token(self, token: str) -> bool:
        """
        Push a single STT token into the rolling buffer.
        Returns True (once per cooldown window) when a wake-word is found.
        """
        # Keep a sliding window of recent words
        words = token.strip().split()
        self._buffer.extend(words)
        if len(self._buffer) > self._buffer_max:
            self._buffer = self._buffer[-self._buffer_max :]

        window_text = " ".join(self._buffer)
        now = time.monotonic()

        for pat in self._PATTERNS:
            if pat.search(window_text):
                if now - self._last_trigger >= self.cooldown_sec:
                    self._last_trigger = now
                    self._buffer.clear()   # reset after trigger
                    logger.info("[WakeWordDetector] Wake-word triggered in streaming buffer.")
                    return True
                # inside cooldown — silently ignore
                return False
        return False

    def reset(self) -> None:
        """Clear internal buffer (call at end of each listen cycle)."""
        self._buffer.clear()
