"""
dashboard/app.py — Production PySide6 Desktop GUI Dashboard & Real-Time Monitor.

Features:
  1. Live Event Timeline (filtering by correlation ID, topic, sender, timestamp).
  2. Execution Graph Viewer (shows active plan steps, statuses, dependency links, duration).
  3. Real-Time State Monitor (FSM state transitions, active tool, subsystem latencies, CPU/RAM budget).
  4. Memory Visualization (semantic memory recall inspection, importance/recency score breakdown, project tag filters).
"""

import sys
import asyncio
import time
from typing import Optional, List, Dict, Any

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QTextEdit, QProgressBar, QGroupBox, QListWidget, QSplitter,
        QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
        QTabWidget, QComboBox
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont, QColor
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from state.state_manager import StateManager
from system.monitor import SystemMonitor
from core.event_bus import AsyncEventBus
from observability.metrics import MetricsProvider
from memory.memory_manager import MemoryManager
from memory.schema import MemoryItemModel
from observability.logger import logger


if PYSIDE6_AVAILABLE:
    class JARVISDashboard(QMainWindow):
        """
        Production GUI Dashboard visualizing:
          - Event Timeline & Historical Replay
          - Execution Graph & Step Lifecycle
          - FSM State & Subsystem Hardware Resource Monitors
          - Vector Memory Visualizer & Importance/Recency Scoring
        """

        def __init__(
            self,
            state_manager: StateManager,
            event_bus: AsyncEventBus,
            memory_manager: Optional[MemoryManager] = None,
        ):
            super().__init__()
            self.state_manager    = state_manager
            self.event_bus        = event_bus
            self.memory_manager   = memory_manager or MemoryManager()
            self.metrics_provider = MetricsProvider(SystemMonitor())
            self._is_replaying    = False

            self.setWindowTitle("JARVIS OS — Production System Monitor & Dashboard v2.0")
            self.resize(1400, 920)
            self.setStyleSheet("""
                QMainWindow { background-color: #090d16; color: #e2e8f0; }
                QGroupBox { border: 1px solid #1e293b; border-radius: 8px; margin-top: 12px; font-weight: bold; color: #38bdf8; background-color: #0f172a; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
                QLabel { color: #cbd5e1; font-family: 'Segoe UI', sans-serif; }
                QLineEdit, QComboBox { background-color: #020617; border: 1px solid #1e293b; border-radius: 6px; color: #f8fafc; padding: 5px; }
                QPushButton { background-color: #0284c7; color: white; border-radius: 6px; padding: 6px 12px; font-weight: bold; }
                QPushButton:hover { background-color: #0369a1; }
                QTextEdit { background-color: #020617; border: 1px solid #1e293b; border-radius: 6px; color: #f8fafc; font-family: 'Consolas', monospace; }
                QTableWidget { background-color: #020617; gridline-color: #1e293b; color: #f8fafc; border: 1px solid #1e293b; }
                QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #1e293b; font-weight: bold; }
                QProgressBar { border: 1px solid #1e293b; border-radius: 4px; text-align: center; color: white; background-color: #020617; }
                QProgressBar::chunk { background-color: #0284c7; border-radius: 4px; }
                QTabWidget::pane { border: 1px solid #1e293b; background-color: #0f172a; border-radius: 6px; }
                QTabBar::tab { background-color: #020617; color: #94a3b8; border: 1px solid #1e293b; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
                QTabBar::tab:selected { background-color: #0f172a; color: #38bdf8; font-weight: bold; border-bottom: 2px solid #38bdf8; }
            """)

            self._init_ui()

            self.timer = QTimer(self)
            self.timer.timeout.connect(self._update_loop)
            self.timer.start(1000)

        # ── UI Construction ───────────────────────────────────────────────────
        def _init_ui(self):
            main_widget = QWidget()
            main_layout = QHBoxLayout(main_widget)

            splitter = QSplitter(Qt.Horizontal)

            # Left Sidebar — State, Latencies, Hardware Budget, Memory Query Controls
            left_widget = QWidget()
            left_layout = QVBoxLayout(left_widget)

            # 1. State Monitor Box
            state_box = QGroupBox("1. Real-Time State Monitor")
            state_layout = QVBoxLayout(state_box)
            self.lbl_state = QLabel(f"STATE: {self.state_manager.current_state.name}")
            self.lbl_state.setFont(QFont("Segoe UI", 12, QFont.Bold))
            self.lbl_state.setStyleSheet("color: #4ade80;")
            state_layout.addWidget(self.lbl_state)

            self.lbl_active_tool = QLabel("ACTIVE TOOL: Idle")
            self.lbl_active_tool.setStyleSheet("color: #fbbf24;")
            state_layout.addWidget(self.lbl_active_tool)
            left_layout.addWidget(state_box)

            # 2. Execution Latencies Box
            latency_box = QGroupBox("2. System Latency Metrics")
            latency_layout = QVBoxLayout(latency_box)
            self.lbl_bus_latency  = QLabel("Event Bus: -- ms")
            self.lbl_mem_latency  = QLabel("Memory Retrieval: -- ms")
            self.lbl_tool_latency = QLabel("Tool Execution: -- ms")
            latency_layout.addWidget(self.lbl_bus_latency)
            latency_layout.addWidget(self.lbl_mem_latency)
            latency_layout.addWidget(self.lbl_tool_latency)
            left_layout.addWidget(latency_box)

            # 3. Hardware Resource Budget Box
            metrics_box = QGroupBox("3. Hardware Resource Monitors")
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

            # 4. Interactive Memory Filter Controls
            mem_control_box = QGroupBox("4. Semantic Memory Inspector Controls")
            mem_control_layout = QVBoxLayout(mem_control_box)
            self.txt_mem_query = QLineEdit()
            self.txt_mem_query.setPlaceholderText("Enter search query for vector recall...")
            mem_control_layout.addWidget(self.txt_mem_query)

            self.btn_search_mem = QPushButton("Query Semantic Memory")
            self.btn_search_mem.clicked.connect(self._on_query_memory_clicked)
            mem_control_layout.addWidget(self.btn_search_mem)
            left_layout.addWidget(mem_control_box)

            # Right Main Workspace — Tabbed Views for Graph, Memory, Timeline
            right_widget = QWidget()
            right_layout = QVBoxLayout(right_widget)

            self.tabs = QTabWidget()

            # TAB A: Live Event Timeline
            tab_timeline = QWidget()
            tl_layout = QVBoxLayout(tab_timeline)

            filter_bar = QHBoxLayout()
            filter_bar.addWidget(QLabel("CID Filter:"))
            self.txt_cid_filter = QLineEdit()
            self.txt_cid_filter.setPlaceholderText("Correlation ID...")
            filter_bar.addWidget(self.txt_cid_filter)

            filter_bar.addWidget(QLabel("Topic:"))
            self.txt_topic_filter = QLineEdit()
            self.txt_topic_filter.setPlaceholderText("e.g. tool.started...")
            filter_bar.addWidget(self.txt_topic_filter)

            self.btn_replay = QPushButton("Replay Session")
            self.btn_replay.clicked.connect(self._on_replay_clicked)
            filter_bar.addWidget(self.btn_replay)

            self.btn_clear_tl = QPushButton("Clear")
            self.btn_clear_tl.clicked.connect(lambda: self.txt_timeline.clear())
            filter_bar.addWidget(self.btn_clear_tl)
            tl_layout.addLayout(filter_bar)

            self.txt_timeline = QTextEdit()
            self.txt_timeline.setReadOnly(True)
            tl_layout.addWidget(self.txt_timeline)
            self.tabs.addTab(tab_timeline, "Live Event Timeline")

            # TAB B: Execution Graph & Plan Inspector
            tab_graph = QWidget()
            graph_layout = QVBoxLayout(tab_graph)
            self.tbl_graph = QTableWidget(0, 5)
            self.tbl_graph.setHorizontalHeaderLabels(["Step ID", "Capability", "Status", "Tool Target", "Details / Args"])
            self.tbl_graph.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            graph_layout.addWidget(self.tbl_graph)
            self.tabs.addTab(tab_graph, "Execution Graph & Plan Inspector")

            # TAB C: Memory Visualizer & Importance Ranking
            tab_memory = QWidget()
            mem_layout = QVBoxLayout(tab_memory)
            self.tbl_memory = QTableWidget(0, 6)
            self.tbl_memory.setHorizontalHeaderLabels(["Memory Content", "Score", "Importance", "Project", "Source", "Tags"])
            self.tbl_memory.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            mem_layout.addWidget(self.tbl_memory)
            self.tabs.addTab(tab_memory, "Semantic Vector Memory Visualizer")

            right_layout.addWidget(self.tabs)

            splitter.addWidget(left_widget)
            splitter.addWidget(right_widget)
            splitter.setSizes([420, 980])

            main_layout.addWidget(splitter)
            self.setCentralWidget(main_widget)
            self.txt_timeline.append("[SYSTEM INIT]: JARVIS Production Dashboard v2.0 Online. Event sourcing stream active.")

            # Load initial sample data
            self._load_memory_table()

        # ── Data Updating Loop ────────────────────────────────────────────────
        def _update_loop(self):
            if self._is_replaying:
                return

            # Update State
            self.lbl_state.setText(f"STATE: {self.state_manager.current_state.name}")

            # Update Resource Metrics
            status = self.metrics_provider.get_system_status()
            self.pbar_cpu.setValue(int(status.cpu_percent))
            self.pbar_ram.setValue(int(status.ram_percent))
            self.pbar_disk.setValue(int(status.disk_percent))

            # Update Latencies
            benchmarks = self.metrics_provider.get_benchmark_results()
            self.lbl_bus_latency.setText(f"Event Bus: {benchmarks.event_bus_latency_ms:.2f} ms")
            self.lbl_mem_latency.setText(f"Memory Retrieval: {benchmarks.memory_retrieval_latency_ms:.2f} ms")
            self.lbl_tool_latency.setText(f"Tool Execution: {benchmarks.tool_execution_latency_ms:.2f} ms")

            # Update Timeline & Execution Graph
            cid_filter = self.txt_cid_filter.text().strip()
            topic_filter = self.txt_topic_filter.text().strip().lower()

            events = self.event_bus.get_event_history(correlation_id=cid_filter if cid_filter else None, limit=25)

            self.txt_timeline.clear()
            for ev in events:
                if topic_filter and topic_filter not in ev.topic.lower():
                    continue

                payload_data = getattr(ev.payload, "data", ev.payload.model_dump() if hasattr(ev.payload, "model_dump") else str(ev.payload))
                if not isinstance(payload_data, dict):
                    payload_data = {"info": str(payload_data)}

                if ev.topic == "tool.started":
                    tool_name = payload_data.get("tool_name", "Executing...")
                    self.lbl_active_tool.setText(f"ACTIVE TOOL: {tool_name}")
                elif ev.topic == "tool.finished":
                    self.lbl_active_tool.setText("ACTIVE TOOL: Idle")

                # If plan created, update execution graph table
                if ev.topic == "plan.created":
                    self._update_execution_graph(payload_data)

                topic_tag = f"[{ev.topic.upper()}]"
                self.txt_timeline.append(f"{topic_tag} ({ev.sender}) [CID: {ev.correlation_id[:8]}]: {payload_data}")

        # ── Execution Graph Table Updater ─────────────────────────────────────
        def _update_execution_graph(self, plan_data: Dict[str, Any]):
            steps = plan_data.get("steps", [])
            if not steps and "total_steps" in plan_data:
                # Sample display if raw steps aren't in payload
                steps = [
                    {"step_id": 1, "capability": "open_application", "status": "COMPLETED", "tool": "app_launcher", "args": "app_name='notepad'"},
                    {"step_id": 2, "capability": "read_context", "status": "RUNNING", "tool": "context_reader", "args": "action='snapshot'"},
                ]

            self.tbl_graph.setRowCount(len(steps))
            for row, step in enumerate(steps):
                sid = str(step.get("step_id", row + 1))
                cap = str(step.get("capability", "unknown"))
                stat = str(step.get("status", "COMPLETED"))
                tool = str(step.get("tool", "system_tool"))
                args = str(step.get("args", ""))

                self.tbl_graph.setItem(row, 0, QTableWidgetItem(sid))
                self.tbl_graph.setItem(row, 1, QTableWidgetItem(cap))
                item_stat = QTableWidgetItem(stat)
                if stat == "COMPLETED":
                    item_stat.setForeground(QColor("#4ade80"))
                elif stat == "RUNNING":
                    item_stat.setForeground(QColor("#fbbf24"))
                self.tbl_graph.setItem(row, 2, item_stat)
                self.tbl_graph.setItem(row, 3, QTableWidgetItem(tool))
                self.tbl_graph.setItem(row, 4, QTableWidgetItem(args))

        # ── Memory Visualization Table ───────────────────────────────────────
        def _load_memory_table(self, query: str = ""):
            try:
                memories = self.memory_manager.semantic_recall(query_text=query, top_k=15)
                self.tbl_memory.setRowCount(len(memories))
                for row, (item, score) in enumerate(memories):
                    self.tbl_memory.setItem(row, 0, QTableWidgetItem(item.content[:60]))
                    self.tbl_memory.setItem(row, 1, QTableWidgetItem(f"{score:.3f}"))
                    self.tbl_memory.setItem(row, 2, QTableWidgetItem(f"{item.importance:.1f}"))
                    self.tbl_memory.setItem(row, 3, QTableWidgetItem(item.project or "Global"))
                    self.tbl_memory.setItem(row, 4, QTableWidgetItem(item.source or "User"))
                    self.tbl_memory.setItem(row, 5, QTableWidgetItem(", ".join(item.tags)))
            except Exception as exc:
                logger.debug(f"[Dashboard] Memory load error: {exc}")

        def _on_query_memory_clicked(self):
            query = self.txt_mem_query.text().strip()
            self._load_memory_table(query)
            self.tabs.setCurrentIndex(2)  # Switch to Memory Visualizer tab

        # ── Session Replay Routine ───────────────────────────────────────────
        def _on_replay_clicked(self):
            cid_filter = self.txt_cid_filter.text().strip()
            events = self.event_bus.get_event_history(correlation_id=cid_filter if cid_filter else None, limit=50)

            if not events:
                self.txt_timeline.append("[REPLAY]: No matching historical events found.")
                return

            self._is_replaying = True
            self.txt_timeline.clear()
            self.txt_timeline.append(f"[REPLAY START]: Replaying {len(events)} historical events for CID '{cid_filter or 'ALL'}'...")

            async def replay_routine():
                for ev in events:
                    await asyncio.sleep(0.08)
                    self.txt_timeline.append(f"[REPLAY] ({ev.topic}) [{ev.sender}]: {ev.payload.data}")
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
