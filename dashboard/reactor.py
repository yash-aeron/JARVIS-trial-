"""
dashboard/reactor.py — Animated arc-reactor presence indicator.

Renders a glowing multi-ring core whose colour, pulse rate and ring rotation
track the assistant's FSM state, plus a live audio waveform strip.
"""
import math
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient, QConicalGradient, QFont
)
from PySide6.QtWidgets import QWidget

from state.states import AssistantState

# Per-state accent colour and pulse speed (cycles/sec).
_STATE_STYLE = {
    AssistantState.IDLE:               ("#37c6ff", 0.45, "STANDBY"),
    AssistantState.WAKE_WORD_DETECTED: ("#7ee8fa", 1.60, "WAKE"),
    AssistantState.LISTENING:          ("#3ddc97", 1.20, "LISTENING"),
    AssistantState.THINKING:           ("#b98cff", 1.90, "THINKING"),
    AssistantState.PLANNING:           ("#ffb454", 1.70, "PLANNING"),
    AssistantState.EXECUTING:          ("#ff9f45", 2.30, "EXECUTING"),
    AssistantState.SPEAKING:           ("#37c6ff", 2.00, "SPEAKING"),
    AssistantState.ERROR:              ("#ff5470", 3.00, "FAULT"),
}


class ReactorWidget(QWidget):
    """Arc-reactor style state indicator with rotating rings and a waveform."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self._phase = 0.0
        self._spin = 0.0
        self._state = AssistantState.IDLE
        self._levels: List[float] = [0.0] * 48
        self._busy = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30 fps

    # ── External updates ──────────────────────────────────────────────────────
    def set_state(self, state: AssistantState) -> None:
        self._state = state
        self._busy = state not in (AssistantState.IDLE, AssistantState.ERROR)
        self.update()

    def push_level(self, level: float) -> None:
        """Feed a 0..1 audio amplitude sample into the waveform."""
        self._levels.append(max(0.0, min(1.0, level)))
        if len(self._levels) > 48:
            self._levels.pop(0)

    def _tick(self) -> None:
        _, speed, _ = _STATE_STYLE.get(self._state, _STATE_STYLE[AssistantState.IDLE])
        self._phase = (self._phase + 0.033 * speed) % 1.0
        self._spin = (self._spin + (1.4 if self._busy else 0.35)) % 360.0
        if not self._busy:
            # Decay the waveform toward silence when nothing is happening.
            self._levels.append(max(0.0, self._levels[-1] * 0.82))
            if len(self._levels) > 48:
                self._levels.pop(0)
        self.update()

    # ── Painting ──────────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        colour_hex, _, label = _STATE_STYLE.get(self._state, _STATE_STYLE[AssistantState.IDLE])
        accent = QColor(colour_hex)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        wave_h = 46
        cx, cy = w / 2.0, (h - wave_h) / 2.0
        radius = max(40.0, min(cx, cy) - 18.0)

        pulse = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)

        self._draw_halo(p, cx, cy, radius, accent, pulse)
        self._draw_rings(p, cx, cy, radius, accent, pulse)
        self._draw_core(p, cx, cy, radius, accent, pulse)
        self._draw_label(p, cx, cy, radius, accent, label)
        self._draw_wave(p, w, h, wave_h, accent)
        p.end()

    def _draw_halo(self, p, cx, cy, radius, accent, pulse) -> None:
        glow_r = radius * (1.55 + 0.10 * pulse)
        grad = QRadialGradient(QPointF(cx, cy), glow_r)
        c0 = QColor(accent)
        c0.setAlpha(int(70 + 55 * pulse))
        mid = QColor(accent)
        mid.setAlpha(int(22 + 18 * pulse))
        edge = QColor(accent)
        edge.setAlpha(0)
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.45, mid)
        grad.setColorAt(1.0, edge)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

    def _draw_rings(self, p, cx, cy, radius, accent, pulse) -> None:
        # Sweeping conical ring — the "spinning" energy band.
        sweep = QConicalGradient(QPointF(cx, cy), -self._spin)
        head = QColor(accent)
        head.setAlpha(230)
        tail = QColor(accent)
        tail.setAlpha(0)
        sweep.setColorAt(0.0, head)
        sweep.setColorAt(0.28, tail)
        sweep.setColorAt(1.0, tail)
        pen = QPen(QBrush(sweep), 3.4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        # Static guide ring.
        guide = QColor(accent)
        guide.setAlpha(60)
        p.setPen(QPen(guide, 1.2))
        p.drawEllipse(QPointF(cx, cy), radius * 0.88, radius * 0.88)

        # Counter-rotating tick marks.
        p.save()
        p.translate(cx, cy)
        p.rotate(self._spin * -0.6)
        tick = QColor(accent)
        tick.setAlpha(140)
        p.setPen(QPen(tick, 2.0, Qt.SolidLine, Qt.RoundCap))
        inner, outer = radius * 0.94, radius * 1.06
        for i in range(36):
            if i % 3 == 0:
                a = math.radians(i * 10)
                p.drawLine(
                    QPointF(inner * math.cos(a), inner * math.sin(a)),
                    QPointF(outer * math.cos(a), outer * math.sin(a)),
                )
        p.restore()

        # Segmented inner ring (the classic reactor coil look).
        p.save()
        p.translate(cx, cy)
        p.rotate(self._spin * 0.35)
        seg = QColor(accent)
        seg.setAlpha(int(120 + 80 * pulse))
        p.setPen(QPen(seg, 5.0, Qt.SolidLine, Qt.FlatCap))
        r2 = radius * 0.60
        box = QRectF(-r2, -r2, r2 * 2, r2 * 2)
        for i in range(8):
            p.drawArc(box, int((i * 45 + 6) * 16), int(32 * 16))
        p.restore()

    def _draw_core(self, p, cx, cy, radius, accent, pulse) -> None:
        core_r = radius * (0.34 + 0.045 * pulse)
        grad = QRadialGradient(QPointF(cx, cy), core_r)
        grad.setColorAt(0.0, QColor(255, 255, 255, 245))
        bright = QColor(accent).lighter(150)
        bright.setAlpha(220)
        grad.setColorAt(0.42, bright)
        deep = QColor(accent)
        deep.setAlpha(120)
        grad.setColorAt(1.0, deep)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), core_r, core_r)

        rim = QColor(accent).lighter(130)
        rim.setAlpha(200)
        p.setPen(QPen(rim, 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), core_r * 1.28, core_r * 1.28)

    def _draw_label(self, p, cx, cy, radius, accent, label) -> None:
        f = QFont("Consolas", 9)
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2.2)
        p.setFont(f)
        txt = QColor(accent).lighter(140)
        p.setPen(QPen(txt))
        rect = QRectF(cx - radius, cy + radius * 1.14, radius * 2, 20)
        p.drawText(rect, Qt.AlignCenter, label)

    def _draw_wave(self, p, w, h, wave_h, accent) -> None:
        base = h - wave_h / 2.0
        n = len(self._levels)
        if n < 2:
            return
        slot = w / float(n)
        bar_w = max(2.0, slot * 0.42)
        for i, lv in enumerate(self._levels):
            amp = max(1.5, lv * (wave_h / 2.0 - 4))
            x = i * slot + (slot - bar_w) / 2.0
            c = QColor(accent)
            c.setAlpha(int(80 + 150 * lv))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(c))
            p.drawRoundedRect(QRectF(x, base - amp, bar_w, amp * 2), bar_w / 2, bar_w / 2)
