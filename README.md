# JARVIS — AI Operating System Assistant

> A fully local, voice-driven AI desktop assistant built on Python.  
> Speak a goal. JARVIS plans it, executes it, and remembers it — no cloud required.

---

## Table of Contents

- [What it does](#what-it-does)
- [Architecture overview](#architecture-overview)
- [Project layout](#project-layout)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running JARVIS](#running-jarvis)
- [Core subsystems](#core-subsystems)
- [Tools](#tools)
- [Plugin SDK](#plugin-sdk)
- [Configuration](#configuration)
- [Testing & benchmarking](#testing--benchmarking)
- [Known limitations](#known-limitations)

---

## What it does

JARVIS accepts voice commands or typed text and turns them into multi-step execution plans that run against real desktop capabilities:

- **Launch and control applications** (Chrome, VS Code, Notepad, Spotify, etc.)
- **Search the web** via your default browser (Google, Bing, DuckDuckGo)
- **Take and analyse screenshots** with OCR and UI element detection
- **Read desktop context** — clipboard, selected text, foreground window, browser URL
- **Store and recall memories** with vector similarity search (ChromaDB + sentence-transformers)
- **Speak responses** via Edge TTS (online) with a pyttsx3/SAPI5 fallback
- **Transcribe speech** via faster-whisper with a SpeechRecognition fallback
- **Undo executed actions** via a full undo-manager with time-travel event replay

---

## Architecture overview

```
User Voice/Text
       │
       ▼
SpeechManager ──→ STT (Whisper / SpeechRecognition)
       │
       ▼
 IntentEngine ──→ complexity classification
       │
       ▼
   Planner ──────→ LLMRouter (Ollama: small / medium / large)
       │               └── FallbackPlanner (no Ollama needed)
       ▼
 PlanValidator ──→ PlanOptimizer
       │
       ▼
 PlanExecutor ──→ PermissionManager gate
       │               └── ToolRegistry → ITool implementations
       ▼
 UndoManager ←─── EventStore (SQLite, snapshots, audit log)
       │
       ▼
  TTS response ──→ Edge TTS / pyttsx3
       │
       ▼
JARVISDashboard (PySide6 GUI) ← AsyncEventBus (all events)
```

All communication between subsystems flows through a typed **AsyncEventBus** backed by a **SQLite EventStore** with point-in-time snapshots, audit logging, and event replay.

---

## Project layout

```
JARVIS/
├── main.py                  # Bootloader: --cli | --gui | --benchmark | --eval
├── requirements.txt
│
├── core/                    # Framework contracts
│   ├── interfaces.py        # ITool, IService, ILLMProvider, ISTTProvider, ITTSProvider …
│   ├── models/              # All Pydantic typed models (no raw dicts anywhere)
│   ├── app.py               # JARVISApp orchestrator + bootstrap_container()
│   ├── container.py         # DependencyContainer (singleton DI)
│   ├── event_bus.py         # AsyncEventBus with SQLite persistence + snapshot replay
│   └── event_store.py       # EventStore, StateSnapshotModel, AuditLogRecordModel
│
├── agent/
│   ├── executive.py         # ExecutiveAgent — goal reflection loop
│   ├── decision_engine.py   # DecisionEngine — sub-goal decomposition + constraints
│   └── subagents.py         # PlanningSubagent, MemorySubagent, ExecutionSubagent
│
├── brain/
│   ├── planner.py           # Planner — LLM-backed multi-step plan generation
│   ├── plan_validator.py    # PlanValidator — structural + safety checks
│   ├── plan_optimizer.py    # PlanOptimizer — deduplication, reordering
│   ├── fallback_planner.py  # FallbackPlanner — heuristic plans without Ollama
│   ├── intent_engine.py     # IntentEngine — complexity classification
│   └── prompt_manager.py    # PromptManager — disk-cached template loader
│
├── models/
│   ├── llm.py               # OllamaLLMProvider + LLMRouter (small/medium/large tiers)
│   ├── stt.py               # FasterWhisperSTTProvider + SpeechRecognitionSTTProvider
│   └── tts.py               # EdgeTTSProvider + pyttsx3 fallback
│
├── speech/
│   ├── speech_manager.py    # SpeechManager service (VAD → wake-word → STT → TTS)
│   ├── vad.py               # SileroVAD + RMS amplitude fallback
│   ├── wake_word.py         # Wake-word detector
│   ├── audio_in.py          # MicRecorder — push-to-talk, 16 kHz PCM, live level
│   └── audio_out.py         # AudioOut — non-blocking PCM playback via sounddevice
│
├── automation/
│   ├── executor.py          # PlanExecutor — step-by-step plan runner
│   ├── action_queue.py      # ActionQueue — priority queue for plan steps
│   └── undo_manager.py      # UndoManager — full action reversal + event_id chains
│
├── tools/
│   ├── registry.py          # ToolRegistry — capability → ITool lookup
│   ├── ranking_strategy.py  # ContextAwareRankingStrategy
│   └── system_tools/
│       ├── applications.py  # AppLauncherTool — 30+ Windows apps
│       ├── system_tools.py  # SystemControlTool — hardware info, power
│       ├── context_tool.py  # ContextReaderTool — clipboard, URL, window
│       ├── memory_tool.py   # MemoryTool — store/recall/index
│       ├── screenshot.py    # ScreenshotCaptureTool — capture, OCR, UI detection
│       ├── web_search.py    # WebSearchTool — Google/Bing/DuckDuckGo via browser
│       └── power.py         # PowerTool — shutdown, restart, sleep
│
├── memory/
│   ├── memory_manager.py    # MemoryManager — semantic + episodic + procedural
│   ├── schema.py            # Memory item Pydantic models
│   └── document_indexer.py  # DocumentIndexer — file/directory indexing
│
├── security/
│   └── permission_manager.py # PermissionManager — LOW/MEDIUM/HIGH/CRITICAL gates
│
├── dashboard/
│   ├── app.py               # JARVISDashboard — PySide6 4-tab live monitor
│   └── reactor.py           # ReactorWidget — animated arc-reactor state indicator
│
├── plugins/
│   ├── sdk.py               # BasePlugin, PluginContext
│   ├── plugin_manager.py    # PluginManager — discover_and_load_all()
│   └── installed/
│       ├── sample_weather/  # Reference weather plugin
│       ├── spotify_control/ # Reference Spotify media control plugin
│       └── vscode_workspace/ # Reference VS Code workspace plugin
│
├── context/
│   └── context_manager.py   # ContextManager — desktop context snapshot
│
├── state/
│   ├── states.py            # AssistantState FSM enum + transition matrix
│   └── state_manager.py     # StateManager — guarded FSM transitions
│
├── config/
│   └── settings.py          # Typed settings loaded from env / YAML
│
├── observability/
│   ├── logger.py            # Structured JSON logger
│   ├── metrics.py           # MetricsProvider — CPU/RAM/disk readings
│   └── tracing.py           # Correlation ID tracing
│
├── benchmark/
│   ├── benchmarking.py      # SystemBenchmarking — real latency measurements
│   └── benchmark_ci.py      # CI runner with SLA threshold assertions
│
└── tests/
    ├── test_jarvis.py        # Core integration tests
    ├── test_integration.py   # E2E pipeline tests
    ├── test_scenarios.py     # Real-world scenario tests
    ├── test_phase1.py  …  test_phase10.py   # Phase-by-phase regression tests
    └── (50 tests — all passing)
```

---

## Requirements

| Category | Packages |
|---|---|
| Core | `pydantic>=2.0`, `pyyaml>=6.0`, `psutil>=5.9` |
| Desktop UI | `PySide6>=6.5` |
| Local LLM | `ollama>=0.1.6` (optional — fallback planner works without it) |
| Vector memory | `chromadb>=0.4` |
| Speech (primary) | `faster-whisper`, `edge-tts>=6.1` |
| Speech (fallback) | `pyttsx3>=2.90`, `SpeechRecognition>=3.10` |
| Microphone | `sounddevice` (optional — required for push-to-talk) |
| Vision | `pyautogui>=0.9.54`, `Pillow>=10.0` |
| Testing | `pytest>=7.4`, `pytest-asyncio>=0.21` |

Python **3.11+** required.

---

## Installation

```powershell
# Clone
git clone https://github.com/yash-aeron/JARVIS-trial-.git
cd JARVIS-trial-

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: install faster-whisper and edge-tts for full speech support
pip install faster-whisper edge-tts

# Optional: install sounddevice for push-to-talk microphone input
pip install sounddevice numpy
```

**For local LLM routing**, install [Ollama](https://ollama.com/download) and pull a model:

```powershell
ollama pull qwen2.5-coder:1.5b   # small tier  — fast intent parsing
ollama pull qwen2.5-coder:7b     # medium tier — multi-step plans
ollama pull qwen2.5-coder:14b    # large tier  — long-form reasoning
```

JARVIS works without Ollama — the `FallbackPlanner` generates heuristic plans automatically.

---

## Running JARVIS

```powershell
# Desktop GUI Dashboard (recommended)
python main.py --gui

# Interactive CLI / voice loop
python main.py --cli

# Run latency benchmarks and SLA assertions
python main.py --benchmark
python benchmark/benchmark_ci.py

# Run full test suite
python -m pytest tests/ -v
```

### GUI Dashboard tabs

| Tab | Contents |
|---|---|
| **Event Timeline** | Live event stream with CID / topic filtering and historical replay |
| **Execution Graph** | Active plan steps, tool names, step status, duration |
| **State Monitor** | FSM state, active tool, CPU / RAM / disk gauges, arc-reactor indicator |
| **Memory Visualizer** | Semantic memory records, importance + recency scores, tag filters |

---

## Core subsystems

### Local LLM routing (`models/llm.py`)

The `LLMRouter` classifies prompt complexity into three tiers and selects the appropriate Ollama model automatically:

| Tier | Complexity | Default model |
|---|---|---|
| Small | `SIMPLE_INTENT` — single-step, keyword commands | `qwen2.5-coder:1.5b` |
| Medium | `MULTI_STEP_PLAN` — 2–5 step action sequences | `qwen2.5-coder:7b` |
| Large | `LONG_FORM_REASONING` — analysis, multi-constraint goals | `qwen2.5-coder:14b` |

The routing is an internal detail of `OllamaLLMProvider` — the `ILLMProvider` interface is unchanged.

### Event store (`core/event_store.py`)

All events are persisted in SQLite with:
- **Point-in-time state snapshots** — `save_snapshot()` / `get_latest_snapshot()`
- **Audit log** — who/what triggered each event, filterable by sender, topic, CID
- **Event replay from snapshot** — `replay_from_snapshot(state_name)` avoids replaying from zero

### Undo & time-travel debugging (`automation/undo_manager.py`)

Every executed plan step creates an `UndoRecordModel` linked to its originating `event_id`. This chain lets you:
1. Replay events back to any snapshot
2. Undo any recorded step by capability and re-run from the previous state

### Permission manager (`security/permission_manager.py`)

All tool capabilities carry a risk level. The `PlanExecutor` gates execution:

| Level | Behaviour |
|---|---|
| `LOW` | Always permitted |
| `MEDIUM` | Permitted unless sandboxed |
| `HIGH` | Requires explicit `grant_approval(correlation_id)` |
| `CRITICAL` | Requires explicit approval; not auto-grantable |

---

## Tools

| Tool | Capabilities | Notes |
|---|---|---|
| `AppLauncherTool` | `open_application`, `launch_app`, `focus_window`, `close_application` | 30+ Windows apps; reuses existing windows |
| `SystemControlTool` | `system_control`, `hardware_info` | CPU, RAM, disk info; permission level HIGH |
| `ContextReaderTool` | `read_context`, `get_clipboard`, `get_selected_text`, `get_browser_url` | Win32 API clipboard; pyautogui fallback |
| `MemoryTool` | `recall_memory`, `store_memory`, `index_document`, `index_directory` | ChromaDB vector store |
| `ScreenshotCaptureTool` | `capture_screenshot`, `ocr_screen`, `detect_ui_elements` | Pillow + pytesseract |
| `WebSearchTool` | `web_search`, `search`, `browse` | Opens results in default browser; no API key required |
| `PowerTool` | `shutdown`, `restart`, `sleep` | Permission level CRITICAL |

All tools implement `ITool` (`execute` + `undo`).

---

## Plugin SDK

Drop a plugin into `plugins/installed/<name>/` with a `plugin.py` and a `manifest.json`:

```python
from plugins.sdk import BasePlugin, PluginContext

class MyPlugin(BasePlugin):
    async def initialize(self, ctx: PluginContext) -> None:
        ctx.register_tool(MyTool())   # any ITool implementation

    async def teardown(self) -> None:
        pass
```

```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "entry_class": "MyPlugin",
  "permissions": ["recall_memory"]
}
```

JARVIS auto-discovers and loads all installed plugins on startup. See [`PLUGIN_SDK.md`](PLUGIN_SDK.md) for the full SDK reference.

---

## Configuration

Settings are loaded from environment variables or a `config.yaml` file (see [`config/settings.py`](config/settings.py)):

| Setting | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODELS` | `{"small": "qwen2.5-coder:1.5b", ...}` | Model tier mapping |
| `STT_PROVIDER` | `faster_whisper` | `faster_whisper` or `speech_recognition` |
| `TTS_PROVIDER` | `edge_tts` | `edge_tts` or `pyttsx3` |
| `TTS_VOICE` | `en-US-ChristopherNeural` | Edge TTS voice name |
| `MEMORY_BACKEND` | `chromadb` | Vector DB backend |
| `PERMISSION_MODE` | `STANDARD` | `STANDARD` or `STRICT` |
| `WAKE_WORD` | `hey jarvis` | Wake-word phrase |

---

## Testing & benchmarking

```powershell
# Run all 50 tests
python -m pytest tests/ -v

# Run CI benchmark with SLA assertions
python benchmark/benchmark_ci.py
```

### SLA thresholds (benchmark_ci.py)

| Metric | SLA budget |
|---|---|
| Startup time | 500 ms |
| Planner latency | 3 000 ms |
| Executor latency | 150 ms |
| Event bus latency | 25 ms |
| Memory retrieval | 50 ms |
| Tool execution | 100 ms |
| STT latency | 500 ms |
| TTS latency | 500 ms |

---

## Known limitations

- **Ollama required for full LLM planning** — without it, the `FallbackPlanner` uses heuristic single-step plans. Install Ollama and pull a model for multi-step reasoning.
- **faster-whisper optional** — falls back to Google SpeechRecognition (requires internet).
- **edge-tts optional** — falls back to pyttsx3 SAPI5 (Windows only, no internet required).
- **sounddevice optional** — microphone capture (push-to-talk) disabled without it.
- **OCR requires pytesseract** — install Tesseract and `pip install pytesseract` to enable `ocr_screen` capability.
- **Windows only** — the AppLauncherTool, context reader, and power tools use Win32 APIs. Core logic (planner, memory, event bus) is platform-agnostic.
