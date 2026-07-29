import sys
import asyncio
from typing import Optional, List

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QLabel, QTextEdit, QProgressBar, QGroupBox, QListWidget, QSplitter,
        QPushButton, QLineEdit, QComboBox
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from state.state_manager import StateManager
from system.monitor import SystemMonitor
from core.event_bus import AsyncEventBus
from core.models import EventModel
from observability.logger import logger

if PYSIDE6_AVAILABLE:
    class JARVISDashboard(QMainWindow):
        """Modern Dark Glassmorphic PySide6 GUI Dashboard with Live Event Timeline and Session Event Replay."""
        
        def __init__(self, state_manager: StateManager, event_bus: AsyncEventBus):
            super().__init__()
            self.state_manager = state_manager
            self.event_bus = event_bus
            self.system_monitor = SystemMonitor()
            self._is_replaying = False
            
            self.setWindowTitle("JARVIS - AI OS Live Event Timeline & Black Box Replay Dashboard v1.0")
            self.resize(1280, 850)
            self.setStyleSheet("""
                QMainWindow { background-color: #0b0f19; color: #e2e8f0; }
                QGroupBox { border: 1px solid #1e293b; border-radius: 8px; margin-top: 12px; font-weight: bold; color: #38bdf8; background-color: #0f172a; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
                QLabel { color: #cbd5e1; }
                QLineEdit { background-color: #020617; border: 1px solid #1e293b; border-radius: 6px; color: #f8fafc; padding: 5px; }
                QPushButton { background-color: #0284c7; color: white; border-radius: 6px; padding: 6px 12px; font-weight: bold; }
                QPushButton:hover { background-color: #0369a1; }
                QTextEdit { background-color: #020617; border: 1px solid #1e293b; border-radius: 6px; color: #f8fafc; font-family: 'Consolas', 'Courier New', monospace; }
                QListWidget { background-color: #020617; border: 1px solid #1e293b; border-radius: 6px; color: #38bdf8; }
                QProgressBar { border: 1px solid #1e293b; border-radius: 4px; text-align: center; color: white; background-color: #020617; }
                QProgressBar::chunk { background-color: #0284c7; border-radius: 4px; }
            """)
            
            self._init_ui()
            
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._update_metrics)
            self.timer.start(1000)

        def _init_ui(self):
            main_widget = QWidget()
            main_layout = QHBoxLayout(main_widget)
            
            splitter = QSplitter(Qt.Horizontal)
            
            # Left Panel - System State, Replay Controls & Hardware Metrics
            left_widget = QWidget()
            left_layout = QVBoxLayout(left_widget)
            
            # State Group
            state_box = QGroupBox("Assistant Status & Finite State Machine")
            state_box_layout = QVBoxLayout(state_box)
            self.lbl_state = QLabel(f"CURRENT STATE: {self.state_manager.current_state.name}")
            self.lbl_state.setFont(QFont("Segoe UI", 12, QFont.Bold))
            self.lbl_state.setStyleSheet("color: #4ade80;")
            state_box_layout.addWidget(self.lbl_state)
            left_layout.addWidget(state_box)
            
            # Event Replay & Filter Controls Box
            replay_box = QGroupBox("Session Black Box Event Replay & Filter")
            replay_layout = QVBoxLayout(replay_box)
            
            filter_layout = QHBoxLayout()
            filter_layout.addWidget(QLabel("CID Filter:"))
            self.txt_cid_filter = QLineEdit()
            self.txt_cid_filter.setPlaceholderText("Enter Correlation ID...")
            filter_layout.addWidget(self.txt_cid_filter)
            replay_layout.addLayout(filter_layout)
            
            btn_layout = QHBoxLayout()
            self.btn_replay = QPushButton("Replay Session Events")
            self.btn_replay.clicked.connect(self._on_replay_clicked)
            btn_layout.addWidget(self.btn_replay)
            
            self.btn_clear = QPushButton("Clear Timeline")
            self.btn_clear.clicked.connect(lambda: self.txt_timeline.clear())
            btn_layout.addWidget(self.btn_clear)
            replay_layout.addLayout(btn_layout)
            
            left_layout.addWidget(replay_box)
            
            # Hardware Metrics Group
            metrics_box = QGroupBox("Hardware Monitors & Resource Budget")
            metrics_layout = QVBoxLayout(metrics_box)
            
            metrics_layout.addWidget(QLabel("CPU Utilization:"))
            self.pbar_cpu = QProgressBar()
            metrics_layout.addWidget(self.pbar_cpu)
            
            metrics_layout.addWidget(QLabel("RAM Utilization:"))
            self.pbar_ram = QProgressBar()
            metrics_layout.addWidget(self.pbar_ram)
            
            metrics_layout.addWidget(QLabel("Disk Utilization:"))
            self.pbar_disk = QProgressBar()
            metrics_layout.addWidget(self.pbar_disk)
            
            left_layout.addWidget(metrics_box)
            
            # Subsystem Dependency Graph Box
            deps_box = QGroupBox("Subsystem Event Pipeline Graph")
            deps_layout = QVBoxLayout(deps_box)
            self.lst_deps = QListWidget()
            self.lst_deps.addItems([
                "1. speech.recognized ──► [Input Transcribed]",
                "2. intent.detected   ──► [Executive Decision]",
                "3. plan.created      ──► [LLM Capability Steps]",
                "4. tool.started      ──► [Subprocess Spawned]",
                "5. tool.finished     ──► [Result Collected]",
                "6. speech.spoke      ──► [TTS Synthesized]"
            ])
            deps_layout.addWidget(self.lst_deps)
            left_layout.addWidget(deps_box)
            
            # Right Panel - Live Event Sourcing Timeline & Stream
            right_widget = QWidget()
            right_layout = QVBoxLayout(right_widget)
            
            # Event Timeline Box
            timeline_box = QGroupBox("Live Event Sourcing Timeline (SQLite Persisted)")
            timeline_layout = QVBoxLayout(timeline_box)
            self.txt_timeline = QTextEdit()
            self.txt_timeline.setReadOnly(True)
            timeline_layout.addWidget(self.txt_timeline)
            right_layout.addWidget(timeline_box)
            
            # Thought Stream Box
            reasoning_box = QGroupBox("Execution & Thought Stream Monitor")
            reasoning_layout = QVBoxLayout(reasoning_box)
            self.txt_reasoning = QTextEdit()
            self.txt_reasoning.setReadOnly(True)
            reasoning_layout.addWidget(self.txt_reasoning)
            right_layout.addWidget(reasoning_box)
            
            splitter.addWidget(left_widget)
            splitter.addWidget(right_widget)
            splitter.setSizes([480, 800])
            
            main_layout.addWidget(splitter)
            self.setCentralWidget(main_widget)
            
            self.txt_timeline.append("[SYSTEM INIT]: JARVIS Live Event Dashboard Online. All Subsystems Operational.")

        def _update_metrics(self):
            if self._is_replaying:
                return
                
            self.lbl_state.setText(f"CURRENT STATE: {self.state_manager.current_state.name}")
            
            stats = self.system_monitor.get_stats()
            self.pbar_cpu.setValue(int(stats.cpu_percent))
            self.pbar_ram.setValue(int(stats.ram_percent))
            self.pbar_disk.setValue(int(stats.disk_percent))
            
            cid_filter = self.txt_cid_filter.text().strip()
            events = self.event_bus.get_event_history(correlation_id=cid_filter if cid_filter else None, limit=12)
            
            self.txt_timeline.clear()
            for ev in events:
                topic_tag = f"[{ev.topic.upper()}]"
                self.txt_timeline.append(f"{topic_tag} ({ev.sender}) [CID: {ev.correlation_id[:8]}]: {ev.payload.model_dump()}")

        def _on_replay_clicked(self):
            cid_filter = self.txt_cid_filter.text().strip()
            events = self.event_bus.get_event_history(correlation_id=cid_filter if cid_filter else None, limit=50)
            
            if not events:
                self.txt_timeline.append("[REPLAY]: No matching historical events found.")
                return
                
            self._is_replaying = True
            self.txt_timeline.clear()
            self.txt_timeline.append(f"[REPLAY START]: Replaying {len(events)} historical events...")
            
            async def replay_routine():
                for ev in events:
                    await asyncio.sleep(0.1)
                    self.txt_timeline.append(f"[REPLAY] ({ev.topic}) [{ev.sender}]: {ev.payload.model_dump()}")
                self.txt_timeline.append("[REPLAY END]: Event replay complete.")
                self._is_replaying = False

            asyncio.create_task(replay_routine())

def run_dashboard(state_manager: StateManager, event_bus: AsyncEventBus):
    if not PYSIDE6_AVAILABLE:
        print("[WARNING]: PySide6 is not installed in the current environment. To enable GUI dashboard, run 'pip install PySide6'.")
        return
        
    app = QApplication.instance() or QApplication(sys.argv)
    window = JARVISDashboard(state_manager, event_bus)
    window.show()
    app.exec()
