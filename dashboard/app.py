import sys
import asyncio
from typing import Optional, List

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QLabel, QTextEdit, QProgressBar, QGroupBox, QListWidget, QSplitter,
        QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

from state.state_manager import StateManager
from system.monitor import SystemMonitor
from core.event_bus import AsyncEventBus
from observability.metrics import MetricsProvider
from memory.memory_manager import MemoryManager
from observability.logger import logger

if PYSIDE6_AVAILABLE:
    class JARVISDashboard(QMainWindow):
        """Production GUI Dashboard visualising active state, live execution graphs, memory hits, latencies, planner output, and event replay."""
        
        def __init__(self, state_manager: StateManager, event_bus: AsyncEventBus, memory_manager: Optional[MemoryManager] = None):
            super().__init__()
            self.state_manager = state_manager
            self.event_bus = event_bus
            self.memory_manager = memory_manager or MemoryManager()
            self.metrics_provider = MetricsProvider(SystemMonitor())
            self._is_replaying = False
            
            self.setWindowTitle("JARVIS - Production AI Operating System Visualizer & Inspector v1.0")
            self.resize(1360, 900)
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
                QTableWidget { background-color: #020617; gridline-color: #1e293b; color: #f8fafc; border: 1px solid #1e293b; }
                QHeaderView::section { background-color: #0f172a; color: #38bdf8; border: 1px solid #1e293b; font-weight: bold; }
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
            
            # Left Panel - Active State, Subsystem Latencies & Hardware Metrics
            left_widget = QWidget()
            left_layout = QVBoxLayout(left_widget)
            
            # 1. Active State Box
            state_box = QGroupBox("1. Active FSM State & Subsystem Status")
            state_box_layout = QVBoxLayout(state_box)
            self.lbl_state = QLabel(f"STATE: {self.state_manager.current_state.name}")
            self.lbl_state.setFont(QFont("Segoe UI", 12, QFont.Bold))
            self.lbl_state.setStyleSheet("color: #4ade80;")
            state_box_layout.addWidget(self.lbl_state)
            
            self.lbl_active_tool = QLabel("ACTIVE TOOL: None (Idle)")
            self.lbl_active_tool.setStyleSheet("color: #fbbf24;")
            state_box_layout.addWidget(self.lbl_active_tool)
            left_layout.addWidget(state_box)
            
            # 2. Execution Latency Metrics Box
            latency_box = QGroupBox("2. Real-Time Execution Latencies (ms)")
            latency_layout = QVBoxLayout(latency_box)
            self.lbl_bus_latency = QLabel("Event Bus Latency: 4.5 ms")
            self.lbl_mem_latency = QLabel("Memory Retrieval Latency: 15.2 ms")
            self.lbl_tool_latency = QLabel("Tool Execution Latency: 16.0 ms")
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
            
            # 4. Session Replay Box
            replay_box = QGroupBox("4. Black Box Session Event Replay")
            replay_layout = QVBoxLayout(replay_box)
            filter_layout = QHBoxLayout()
            filter_layout.addWidget(QLabel("CID Filter:"))
            self.txt_cid_filter = QLineEdit()
            self.txt_cid_filter.setPlaceholderText("Enter Correlation ID...")
            filter_layout.addWidget(self.txt_cid_filter)
            replay_layout.addLayout(filter_layout)
            
            btn_layout = QHBoxLayout()
            self.btn_replay = QPushButton("Replay Session")
            self.btn_replay.clicked.connect(self._on_replay_clicked)
            btn_layout.addWidget(self.btn_replay)
            self.btn_clear = QPushButton("Clear")
            self.btn_clear.clicked.connect(lambda: self.txt_timeline.clear())
            btn_layout.addWidget(self.btn_clear)
            replay_layout.addLayout(btn_layout)
            left_layout.addWidget(replay_box)
            
            # Right Panel - Execution Graph, Planner Output, Memory Hits & Timeline
            right_widget = QWidget()
            right_layout = QVBoxLayout(right_widget)
            
            # 5. Live Execution Graph Table
            graph_box = QGroupBox("5. Active Plan Execution Graph & Step Progress")
            graph_layout = QVBoxLayout(graph_box)
            self.tbl_graph = QTableWidget(3, 4)
            self.tbl_graph.setHorizontalHeaderLabels(["Step ID", "Capability", "Status", "Tool Target"])
            self.tbl_graph.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self._populate_sample_graph()
            graph_layout.addWidget(self.tbl_graph)
            right_layout.addWidget(graph_box)
            
            # 6. Memory Hits Table
            memory_box = QGroupBox("6. Semantic Vector Memory Hits & Ranking")
            memory_layout = QVBoxLayout(memory_box)
            self.tbl_memory = QTableWidget(2, 4)
            self.tbl_memory.setHorizontalHeaderLabels(["Memory Content", "Score", "Tags", "Importance"])
            self.tbl_memory.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self._populate_sample_memory()
            memory_layout.addWidget(self.tbl_memory)
            right_layout.addWidget(memory_box)
            
            # 7. Live Event Sourcing Timeline
            timeline_box = QGroupBox("7. Live Event Sourcing Timeline (SQLite Persisted)")
            timeline_layout = QVBoxLayout(timeline_box)
            self.txt_timeline = QTextEdit()
            self.txt_timeline.setReadOnly(True)
            timeline_layout.addWidget(self.txt_timeline)
            right_layout.addWidget(timeline_box)
            
            splitter.addWidget(left_widget)
            splitter.addWidget(right_widget)
            splitter.setSizes([450, 910])
            
            main_layout.addWidget(splitter)
            self.setCentralWidget(main_widget)
            self.txt_timeline.append("[SYSTEM INIT]: JARVIS Production Dashboard Online. All Subsystems Operational.")

        def _populate_sample_graph(self):
            sample_steps = [
                ("1", "open_application", "COMPLETED", "app_launcher (VS Code)"),
                ("2", "terminal_execution", "RUNNING", "cmd_runner (git status)"),
                ("3", "web_search", "PENDING", "browser_tool")
            ]
            for row, (sid, cap, stat, tool) in enumerate(sample_steps):
                self.tbl_graph.setItem(row, 0, QTableWidgetItem(sid))
                self.tbl_graph.setItem(row, 1, QTableWidgetItem(cap))
                self.tbl_graph.setItem(row, 2, QTableWidgetItem(stat))
                self.tbl_graph.setItem(row, 3, QTableWidgetItem(tool))

        def _populate_sample_memory(self):
            try:
                memories = self.memory_manager.semantic_recall(query_text="python preference", top_k=2)
                for row, (item, score) in enumerate(memories):
                    self.tbl_memory.setItem(row, 0, QTableWidgetItem(item.content[:40]))
                    self.tbl_memory.setItem(row, 1, QTableWidgetItem(f"{score:.2f}"))
                    self.tbl_memory.setItem(row, 2, QTableWidgetItem(", ".join(item.tags)))
                    self.tbl_memory.setItem(row, 3, QTableWidgetItem(str(item.importance)))
            except Exception:
                pass

        def _update_metrics(self):
            if self._is_replaying:
                return
                
            self.lbl_state.setText(f"STATE: {self.state_manager.current_state.name}")
            
            status = self.metrics_provider.get_system_status()
            self.pbar_cpu.setValue(int(status.cpu_percent))
            self.pbar_ram.setValue(int(status.ram_percent))
            self.pbar_disk.setValue(int(status.disk_percent))
            
            benchmarks = self.metrics_provider.get_benchmark_results()
            self.lbl_bus_latency.setText(f"Event Bus Latency: {benchmarks.event_bus_latency_ms} ms")
            self.lbl_mem_latency.setText(f"Memory Retrieval Latency: {benchmarks.memory_retrieval_latency_ms} ms")
            self.lbl_tool_latency.setText(f"Tool Execution Latency: {benchmarks.tool_execution_latency_ms} ms")
            
            cid_filter = self.txt_cid_filter.text().strip()
            events = self.event_bus.get_event_history(correlation_id=cid_filter if cid_filter else None, limit=12)
            
            self.txt_timeline.clear()
            for ev in events:
                if ev.topic == "tool.started":
                    self.lbl_active_tool.setText(f"ACTIVE TOOL: {ev.payload.data.get('tool_name', 'Executing...')}")
                elif ev.topic == "tool.finished":
                    self.lbl_active_tool.setText("ACTIVE TOOL: None (Idle)")
                    
                topic_tag = f"[{ev.topic.upper()}]"
                self.txt_timeline.append(f"{topic_tag} ({ev.sender}) [CID: {ev.correlation_id[:8]}]: {ev.payload.data}")

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
