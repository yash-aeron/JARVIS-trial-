"""
dashboard/app.py — JARVIS desktop interface.

Conversation-first layout: an animated arc-reactor presence indicator and system
vitals on the left, the dialogue with JARVIS on the right. Voice in (push-to-talk
via faster-whisper) and voice out (edge-tts) are wired through SpeechManager.

Diagnostics (event timeline, execution graph, memory inspector) live behind the
Diagnostics tab rather than dominating the window.
"""

import asyncio
import html
import sys
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QTextEdit, QProgressBar, QSplitter, QPushButton, QLineEdit,
        QTabWidget, QScrollArea, QFrame, QSizePolicy,
    )
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QFont, QKeyEvent
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from state.state_manager import StateManager
from state.states import AssistantState
from system.monitor import SystemMonitor
from core.event_bus import AsyncEventBus
from core.models import EventModel
from observability.metrics import MetricsProvider
from memory.memory_manager import MemoryManager
from observability.logger import logger

if PYSIDE6_AVAILABLE:
    from dashboard.reactor import ReactorWidget

# ── Palette ───────────────────────────────────────────────────────────────────
BG_DEEP   = "#05080f"
BG_PANEL  = "#0b1220"
BG_INPUT  = "#111b2d"
BORDER    = "#1b2b45"
TEXT      = "#dce6f5"
TEXT_DIM  = "#7c8ba5"
ACCENT    = "#37c6ff"
USER_C    = "#7ee8fa"
OK_C      = "#3ddc97"
WARN_C    = "#ffb454"
ERR_C     = "#ff5470"

STYLESHEET = f"""
QMainWindow, QWidget {{ background: {BG_DEEP}; color: {TEXT};
    font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
QFrame#panel {{ background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#title {{ font-size: 15px; font-weight: 600; color: {ACCENT};
    letter-spacing: 3px; }}
QLabel#sub {{ color: {TEXT_DIM}; font-size: 11px; letter-spacing: 1px; }}
QLabel#vital {{ color: {TEXT_DIM}; font-size: 11px; letter-spacing: 1px; }}
QTextEdit {{ background: transparent; border: none; font-size: 14px; }}
QTextEdit#diag {{ background: {BG_DEEP}; border: 1px solid {BORDER};
    border-radius: 8px; font-family: 'Consolas', monospace; font-size: 11px;
    color: {TEXT_DIM}; }}
QLineEdit {{ background: {BG_INPUT}; border: 1px solid {BORDER};
    border-radius: 18px; padding: 10px 16px; font-size: 14px; color: {TEXT}; }}
QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
QPushButton {{ background: {BG_INPUT}; border: 1px solid {BORDER};
    border-radius: 18px; padding: 9px 18px; color: {TEXT}; font-weight: 600; }}
QPushButton:hover {{ border: 1px solid {ACCENT}; color: {ACCENT}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton#mic[recording="true"] {{ border: 1px solid {ERR_C}; color: {ERR_C}; }}
QProgressBar {{ background: {BG_INPUT}; border: none; border-radius: 5px;
    height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 10px;
    background: {BG_PANEL}; }}
QTabBar::tab {{ background: transparent; color: {TEXT_DIM}; padding: 9px 20px;
    border-bottom: 2px solid transparent; letter-spacing: 1px; }}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


if PYSIDE6_AVAILABLE:

    class JARVISDashboard(QMainWindow):
        """Conversation-centric JARVIS interface with reactor presence indicator."""

        # Worker coroutines emit through these so UI updates stay on the Qt thread.
        replyReady = Signal(str, str)      # (response, summary)
        errorRaised = Signal(str)
        transcribed = Signal(str)

        def __init__(
            self,
            state_manager: StateManager,
            event_bus: AsyncEventBus,
            memory_manager: Optional[MemoryManager] = None,
            jarvis_app: Optional[Any] = None,
        ):
            super().__init__()
            self.state_manager = state_manager
            self.event_bus = event_bus
            self.memory_manager = memory_manager or MemoryManager()
            self.jarvis_app = jarvis_app
            self.metrics_provider = MetricsProvider(SystemMonitor())

            self._busy = False
            self._mic = None
            self._recorder_active = False

            self.setWindowTitle("JARVIS")
            self.resize(1180, 760)
            self.setStyleSheet(STYLESHEET)

            self._build_ui()
            self._wire_events()

            self._vitals_timer = QTimer(self)
            self._vitals_timer.timeout.connect(self._refresh_vitals)
            self._vitals_timer.start(1500)

            self._mic_timer = QTimer(self)
            self._mic_timer.timeout.connect(self._pump_mic_level)
            self._mic_timer.start(50)

            self.replyReady.connect(self._on_reply)
            self.errorRaised.connect(self._on_error)
            self.transcribed.connect(self._on_transcribed)

            self._greet()

        # ── UI construction ───────────────────────────────────────────────────
        def _build_ui(self) -> None:
            root = QWidget()
            self.setCentralWidget(root)
            outer = QVBoxLayout(root)
            outer.setContentsMargins(14, 14, 14, 14)
            outer.setSpacing(12)

            split = QSplitter(Qt.Horizontal)
            split.setHandleWidth(12)
            split.addWidget(self._build_left())
            split.addWidget(self._build_right())
            split.setStretchFactor(0, 0)
            split.setStretchFactor(1, 1)
            split.setSizes([390, 790])
            outer.addWidget(split, 1)

        def _build_left(self) -> QWidget:
            panel = QFrame()
            panel.setObjectName("panel")
            panel.setMinimumWidth(330)
            lay = QVBoxLayout(panel)
            lay.setContentsMargins(18, 18, 18, 18)
            lay.setSpacing(10)

            title = QLabel("J  A  R  V  I  S")
            title.setObjectName("title")
            title.setAlignment(Qt.AlignCenter)
            lay.addWidget(title)

            self.lbl_tagline = QLabel("Just A Rather Very Intelligent System")
            self.lbl_tagline.setObjectName("sub")
            self.lbl_tagline.setAlignment(Qt.AlignCenter)
            self.lbl_tagline.setWordWrap(True)
            lay.addWidget(self.lbl_tagline)

            self.reactor = ReactorWidget()
            self.reactor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lay.addWidget(self.reactor, 1)

            self.lbl_activity = QLabel("Awaiting instruction")
            self.lbl_activity.setObjectName("sub")
            self.lbl_activity.setAlignment(Qt.AlignCenter)
            self.lbl_activity.setWordWrap(True)
            lay.addWidget(self.lbl_activity)

            lay.addSpacing(6)
            self.bar_cpu, cpu_row = self._vital_row("CPU")
            self.bar_ram, ram_row = self._vital_row("MEMORY")
            lay.addLayout(cpu_row)
            lay.addLayout(ram_row)

            return panel

        def _vital_row(self, name: str):
            row = QVBoxLayout()
            row.setSpacing(4)
            head = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setObjectName("vital")
            val = QLabel("--%")
            val.setObjectName("vital")
            val.setAlignment(Qt.AlignRight)
            head.addWidget(lbl)
            head.addWidget(val)
            row.addLayout(head)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            row.addWidget(bar)
            bar.value_label = val  # type: ignore[attr-defined]
            return bar, row

        def _build_right(self) -> QWidget:
            tabs = QTabWidget()
            tabs.addTab(self._build_chat(), "CONVERSATION")
            tabs.addTab(self._build_diagnostics(), "DIAGNOSTICS")
            return tabs

        def _build_chat(self) -> QWidget:
            wrap = QWidget()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(16, 16, 16, 16)
            lay.setSpacing(12)

            self.transcript = QTextEdit()
            self.transcript.setReadOnly(True)
            lay.addWidget(self.transcript, 1)

            row = QHBoxLayout()
            row.setSpacing(8)
            self.input = QLineEdit()
            self.input.setPlaceholderText("Speak to JARVIS, or hold the mic button…")
            self.input.returnPressed.connect(self._on_submit)
            row.addWidget(self.input, 1)

            self.btn_mic = QPushButton("HOLD TO TALK")
            self.btn_mic.setObjectName("mic")
            self.btn_mic.setToolTip("Hold to record, release to send")
            self.btn_mic.pressed.connect(self._start_recording)
            self.btn_mic.released.connect(self._stop_recording)
            row.addWidget(self.btn_mic)

            self.btn_send = QPushButton("SEND")
            self.btn_send.clicked.connect(self._on_submit)
            row.addWidget(self.btn_send)
            lay.addLayout(row)

            return wrap

        def _build_diagnostics(self) -> QWidget:
            wrap = QWidget()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(16, 16, 16, 16)
            lay.setSpacing(10)

            head = QHBoxLayout()
            lbl = QLabel("EVENT STREAM")
            lbl.setObjectName("sub")
            head.addWidget(lbl)
            head.addStretch(1)
            btn_clear = QPushButton("CLEAR")
            btn_clear.clicked.connect(lambda: self.txt_diag.clear())
            head.addWidget(btn_clear)
            lay.addLayout(head)

            self.txt_diag = QTextEdit()
            self.txt_diag.setObjectName("diag")
            self.txt_diag.setReadOnly(True)
            lay.addWidget(self.txt_diag, 1)

            return wrap

        # ── Event bus wiring ──────────────────────────────────────────────────
        def _wire_events(self) -> None:
            self.state_manager.subscribe(self._on_state_change)
            self.event_bus.subscribe("*", self._on_bus_event)

        def _on_state_change(self, old: AssistantState, new: AssistantState) -> None:
            self.reactor.set_state(new)
            self.lbl_activity.setText(_ACTIVITY.get(new, new.name.title()))

        async def _on_bus_event(self, ev: EventModel) -> None:
            payload = ev.payload
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump()
            stamp = time.strftime("%H:%M:%S")
            self.txt_diag.append(
                f'<span style="color:{TEXT_DIM}">{stamp}</span> '
                f'<span style="color:{ACCENT}">{html.escape(ev.topic)}</span> '
                f'<span style="color:{TEXT_DIM}">{html.escape(str(payload)[:220])}</span>'
            )

        # ── Transcript rendering ──────────────────────────────────────────────
        def _append(self, who: str, text: str, colour: str) -> None:
            stamp = time.strftime("%H:%M")
            self.transcript.append(
                f'<div style="margin:10px 0 2px 0">'
                f'<span style="color:{colour};font-weight:600;letter-spacing:1px">{who}</span>'
                f'<span style="color:{TEXT_DIM};font-size:11px">  {stamp}</span></div>'
                f'<div style="color:{TEXT};margin-bottom:6px">{html.escape(text)}</div>'
            )
            self.transcript.verticalScrollBar().setValue(
                self.transcript.verticalScrollBar().maximum()
            )

        def _append_detail(self, text: str, colour: str) -> None:
            self.transcript.append(
                f'<div style="color:{colour};font-size:12px;margin:0 0 4px 14px">{html.escape(text)}</div>'
            )

        def _greet(self) -> None:
            self._append("JARVIS", "Systems online. How can I help, sir?", ACCENT)

        # ── Input handling ────────────────────────────────────────────────────
        def _on_submit(self) -> None:
            text = self.input.text().strip()
            if not text:
                return
            self.input.clear()
            self._dispatch(text)

        def _dispatch(self, text: str) -> None:
            if self._busy:
                self._append_detail("Still working on the previous request…", WARN_C)
                return
            if self.jarvis_app is None:
                self._append_detail("No JARVIS core attached — running in view-only mode.", WARN_C)
                return

            self._append("YOU", text, USER_C)
            self._busy = True
            self._set_inputs_enabled(False)
            asyncio.ensure_future(self._process(text))

        async def _process(self, text: str) -> None:
            cid = str(uuid.uuid4())
            try:
                result = await self.jarvis_app.process_user_command(text, correlation_id=cid)
                summary = self._summarize(result)
                self.replyReady.emit(result.response, summary)
            except Exception as exc:
                logger.error(f"[Dashboard] Command failed: {exc}")
                self.errorRaised.emit(str(exc))

        @staticmethod
        def _summarize(result) -> str:
            bits: List[str] = []
            for r in result.execution_results:
                status = getattr(r, "status", "?")
                if status == "completed" and isinstance(r.result, dict):
                    if "cpu_percent" in r.result:
                        bits.append(f"CPU {r.result['cpu_percent']}%  ·  RAM {r.result.get('ram_percent','?')}%")
                    elif "app_name" in r.result:
                        bits.append(f"{r.result['app_name']} → {r.result.get('action_taken','done')}")
                    elif "url" in r.result:
                        bits.append(f"searched: {r.result.get('query','')}")
                elif status != "completed":
                    bits.append(f"failed: {getattr(r, 'error', 'unknown error')}")
            return "   ".join(bits)

        def _on_reply(self, response: str, summary: str) -> None:
            self._append("JARVIS", response, ACCENT)
            if summary:
                colour = ERR_C if "failed" in summary else OK_C
                self._append_detail(summary, colour)
            self._busy = False
            self._set_inputs_enabled(True)

        def _on_error(self, msg: str) -> None:
            self._append("JARVIS", f"I ran into a problem: {msg}", ERR_C)
            self._busy = False
            self._set_inputs_enabled(True)

        def _set_inputs_enabled(self, on: bool) -> None:
            self.input.setEnabled(on)
            self.btn_send.setEnabled(on)
            self.btn_mic.setEnabled(on)
            if on:
                self.input.setFocus()

        # ── Push-to-talk ──────────────────────────────────────────────────────
        def _ensure_mic(self):
            if self._mic is None:
                from speech.audio_in import MicRecorder
                self._mic = MicRecorder()
            return self._mic

        def _start_recording(self) -> None:
            if self._busy:
                return
            mic = self._ensure_mic()
            if not mic.available:
                self._append_detail("No microphone available on this system.", WARN_C)
                return
            if mic.start():
                self._recorder_active = True
                self.btn_mic.setProperty("recording", "true")
                self.btn_mic.setText("● RECORDING")
                self.btn_mic.style().unpolish(self.btn_mic)
                self.btn_mic.style().polish(self.btn_mic)
                self.lbl_activity.setText("Listening…")
                self.state_manager.transition_to(
                    AssistantState.LISTENING, "Push-to-talk engaged"
                )

        def _stop_recording(self) -> None:
            if not self._recorder_active or self._mic is None:
                return
            self._recorder_active = False
            self.btn_mic.setProperty("recording", "false")
            self.btn_mic.setText("HOLD TO TALK")
            self.btn_mic.style().unpolish(self.btn_mic)
            self.btn_mic.style().polish(self.btn_mic)

            pcm = self._mic.stop()
            if len(pcm) < 4000:  # under ~0.12 s of audio
                self.lbl_activity.setText("Awaiting instruction")
                self.state_manager.transition_to(AssistantState.IDLE, "Recording too short")
                self._append_detail("That was too short to transcribe.", WARN_C)
                return

            self.lbl_activity.setText("Transcribing…")
            asyncio.ensure_future(self._transcribe(pcm))

        async def _transcribe(self, pcm: bytes) -> None:
            try:
                from core.interfaces import ISTTProvider
                provider = self.jarvis_app.container.resolve(ISTTProvider)
                text = await provider.transcribe(pcm, language=None)
                self.transcribed.emit(text or "")
            except Exception as exc:
                logger.error(f"[Dashboard] Transcription failed: {exc}")
                self.errorRaised.emit(f"transcription failed: {exc}")

        def _on_transcribed(self, text: str) -> None:
            text = text.strip()
            self.state_manager.transition_to(AssistantState.IDLE, "Transcription complete")
            if not text:
                self._append_detail("I didn't catch that.", WARN_C)
                self.lbl_activity.setText("Awaiting instruction")
                return
            self._dispatch(text)

        def _pump_mic_level(self) -> None:
            if self._recorder_active and self._mic is not None:
                self.reactor.push_level(self._mic.level)

        # ── Vitals ────────────────────────────────────────────────────────────
        def _refresh_vitals(self) -> None:
            try:
                stats = self.metrics_provider.get_system_status()
            except Exception:
                return
            cpu = int(getattr(stats, "cpu_percent", 0) or 0)
            ram = int(getattr(stats, "ram_percent", 0) or 0)
            self.bar_cpu.setValue(cpu)
            self.bar_ram.setValue(ram)
            self.bar_cpu.value_label.setText(f"{cpu}%")
            self.bar_ram.value_label.setText(f"{ram}%")

        # ── Shortcuts ─────────────────────────────────────────────────────────
        def keyPressEvent(self, event: "QKeyEvent") -> None:  # noqa: N802
            if event.key() == Qt.Key_Space and event.modifiers() & Qt.ControlModifier:
                if not self._recorder_active:
                    self._start_recording()
                return
            super().keyPressEvent(event)

        def keyReleaseEvent(self, event: "QKeyEvent") -> None:  # noqa: N802
            if event.key() == Qt.Key_Space and self._recorder_active:
                self._stop_recording()
                return
            super().keyReleaseEvent(event)


_ACTIVITY = {
    AssistantState.IDLE: "Awaiting instruction",
    AssistantState.WAKE_WORD_DETECTED: "Wake word detected",
    AssistantState.LISTENING: "Listening…",
    AssistantState.THINKING: "Interpreting request…",
    AssistantState.PLANNING: "Formulating a plan…",
    AssistantState.EXECUTING: "Carrying out your request…",
    AssistantState.SPEAKING: "Responding…",
    AssistantState.ERROR: "Something went wrong",
} if PYSIDE6_AVAILABLE else {}


def run_dashboard(
    state_manager: StateManager,
    event_bus: AsyncEventBus,
    jarvis_app: Optional[Any] = None,
):
    if not PYSIDE6_AVAILABLE:
        print("[WARNING]: PySide6 is not installed. Run 'pip install PySide6' to enable the GUI.")
        return

    import qasync

    app = QApplication.instance() or QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = JARVISDashboard(state_manager, event_bus, jarvis_app=jarvis_app)
    window.show()

    with loop:
        loop.run_forever()
