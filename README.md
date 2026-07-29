# JARVIS: Local-First AI Operating System Assistant

JARVIS is an event-driven, modular AI Operating System Assistant designed for privacy, local execution, and autonomous multi-step task planning. Built adhering to SOLID principles, strict decoupling, zero generic untyped dictionaries, and type-based dependency injection, JARVIS allows swapping local model providers, speech engines, vector stores, and automation tools without altering business logic.

---

## Key Features

- **Local-First Architecture**: Prioritizes local processing using models such as Ollama, Faster-Whisper, Silero VAD, and local TTS, ensuring data privacy and low execution latency.
- **Type-Based & Modular DI Bootstrapping**: Registers and resolves dependencies using strict Class and Interface types (`container.resolve(ISTTProvider)`). Registration is modularized into foundation, speech, brain, automation, memory, and plugin layers.
- **Strongly Typed Pydantic Contracts**: Zero generic untyped dictionaries (`Dict[str, Any]`). Uses dedicated Pydantic models across all layers (`ExecutionContextModel`, `PlannerContextModel`, `OpenApplicationArgs`, `SystemControlArgs`, `LanguageDetectionModel`, `SystemStatusModel`, `BenchmarkResultModel`, `UserCommandResultModel`).
- **Decoupled Event Store & Middleware Bus**: Powered by `AsyncEventBus` with unified Correlation IDs, middleware chains (`add_middleware()`), session event replay (`replay_events()`), and a dedicated `EventStore` handling SQLite persistence (`data/event_store.db`).
- **Plan Optimization & Validation Engine**: Generates capability-based plans from structured LLM JSON outputs. Injects `PromptManager` (with in-memory template caching), `PlanValidator` (verifying step IDs, dependency references, and registered capabilities), `PlanOptimizer` (removing duplicate steps and re-indexing dependency graphs), and `FallbackPlanner` via DI.
- **Priority Action Queue & Parallel Execution**: `ActionQueue` features priority aging starvation prevention, worker pool limits (`max_workers`), heapq priority ordering, cancellation, pause/resume, and progress/ETA tracking. `PlanExecutor` executes independent tasks concurrently via `asyncio.gather(*tasks)`.
- **Circuit Breakers & Service Lifecycle**: Subsystems implement explicit lifecycle states (`NEW`, `STARTING`, `RUNNING`, `DEGRADED`, `STOPPING`, `STOPPED`, `FAILED`). `ServiceManager` tracks consecutive failure windows (60s) and circuit breaker thresholds (3 failures) to transition degraded services to `ServiceState.DEGRADED`.
- **Multi-Factor Weighted Memory Engine**: `MemoryManager` uses Cosine Similarity vector search scored by an exact weighted formula: `(0.45 * Semantic) + (0.20 * Importance) + (0.20 * Recency) + (0.10 * Project) + (0.05 * Confidence)`.
- **NVIDIA RTX 3050 Ti VRAM `GPUManager`**: `GPUManager` monitors VRAM budget (3.5GB threshold), supporting automatic model offloading (`auto_offload`), lazy loading (`register_model`), explicit model unloading (`unload_model`), and CUDA warm-up (`warm_up`).
- **Faster-Whisper & Silero VAD Speech Pipeline**: Integrated `SileroVAD` audio energy filtering (`speech/vad.py`), `WakeWordDetector` keyphrase activation ("Jarvis"), interruption handling (`interrupt()`), and low-latency streaming transcription and TTS.
- **Native Process Control & Win32 Window Focus**: `ApplicationLauncherTool` detects running processes (`psutil`), using native Windows User32 `EnumWindows` callbacks (`ctypes.WINFUNCTYPE`) to restore minimized windows (`ShowWindow(hwnd, SW_RESTORE)`) and bring existing application windows to the foreground.
- **Real Windows ContextManager**: `ContextManager` queries Windows User32 `GetForegroundWindow` PID, active window title, Unicode clipboard (`CF_UNICODETEXT = 13`), and display resolution metrics.
- **Unified Observability & Metrics Provider**: `MetricsProvider` consolidates hardware metrics (`SystemStatusModel`), latency benchmarks (`BenchmarkResultModel`), and execution counters across Dashboard, Evaluators, and Tests.
- **PySide6 Desktop GUI Dashboard**: Features a live Event Sourcing Timeline, Correlation ID filtering, and Session Black Box Event Replay controls (`replay_events()`).

---

## System Architecture

JARVIS follows a modular layer separation to achieve high maintainability and subsystem replaceability.

```text
User Input (Voice / Text)
        │
        ▼
   SpeechManager (Silero VAD / Faster-Whisper / Wake Word) ──► [Event: speech.recognized (Correlation ID)] ──► AsyncEventBus
                                                                                                                   │
                                                                                                       EventStore (SQLite)
        ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
        ▼
  ExecutiveAgent (Decision Engine: Confidence, Risk Level, Planning, Memory, Search)
        │
        ├──► Conversational Query ──► ResponseGenerator ──► SpeechManager (Streaming TTS)
        │
        └──► Complex Multi-Step Goal
                     │
                     ▼
                  Planner (PromptManager ──► LLM JSON ──► PlanValidator ──► PlanOptimizer)
                     │
                     ▼
             PlanExecutor (Parallel Execution & Composite Ranking) ──► ActionQueue ──► ToolRegistry
```

---

## Project Structure

```text
JARVIS/
├── agent/            Executive agent and decision engine components
├── automation/       Action queue (priority aging & worker pool), parallel plan executor, and undo management
├── benchmark/        Automated performance benchmarking suite
├── brain/            Intent identification, LLM-first planner, plan validator, plan optimizer, and fallback planner
├── config/           System configuration parameters and environment profiles
├── context/          Windows API context manager (process PID, window title, Unicode clipboard, screen resolution)
├── core/             Application container, interfaces, models (Pydantic contracts), EventStore, event bus (middleware/replay), and service registry
├── dashboard/        PySide6 desktop graphical interface (live event timeline & session replay visualizer)
├── evaluation/       Tool selection accuracy and plan optimality evaluators
├── language/         Code-switching language identification and localization management
├── mcp/              Model Context Protocol adapters and tool registries
├── memory/           Rich vector memory schema, SQLite persistence, and multi-factor weighted ranking
├── models/           Abstractions for LLMs, STT (Faster-Whisper, Silero VAD, streaming & interruptible), and TTS engines
├── observability/    Structured logger (TimerLogger), MetricsProvider, tracing, and diagnostics
├── plugins/          Plugin SDK and runtime plugin loading system
├── prompts/          PromptManager (in-memory template caching) and Markdown prompt templates
├── resource/         GPU allocation (RTX 3050 Ti VRAM auto-offloading & warm-up) and system hardware resources
├── session/          Session history and state retention
├── skills/           Skill discovery engine and execution routines
├── speech/           Silero VAD, Wake-Word Detection, speech recognition, and streaming speech synthesis
├── state/            Guarded finite state machine and transition table
├── system/           System resource monitoring and runtime profile selection
├── tests/            Pytest unit, integration, and multi-step scenario test suite
├── tools/            System tools, process launcher (Win32 EnumWindows callback), and composite ranking strategy
├── main.py           Application entry point and CLI bootloader
├── requirements.txt  Python project dependencies
├── ARCHITECTURE.md   Technical design and component interaction documentation
├── CONTRIBUTING.md   Development guidelines and pull request standards
├── EVENTS.md         System event topics and correlation ID specification
├── INTERFACES.md     Abstract interface contracts
├── PLUGIN_SDK.md     Plugin creation and integration documentation
└── ROADMAP.md        Project milestones and feature targets
```

---

## Prerequisites

- **Python**: Version 3.10 or higher
- **Ollama**: Running locally with a compatible LLM model (e.g., `qwen2.5-coder`, `llama3`, or `mistral`)
- **System Memory**: 8 GB RAM minimum (16 GB recommended for local LLM execution)
- **Optional**: NVIDIA GPU with CUDA support for accelerated local inference (optimized for RTX 3050 Ti VRAM budget)

---

## Installation & Setup

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yash-aeron/JARVIS-trial-.git
   cd JARVIS-trial-
   ```

2. **Set Up Virtual Environment**

   ```bash
   python -m venv .venv
   # On Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   # On Linux/macOS
   source .venv/bin/activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Local Model Service**

   Ensure Ollama is installed and running locally:

   ```bash
   ollama pull qwen2.5-coder
   ```

---

## Usage

JARVIS provides multiple execution modes accessible via `main.py`.

### Interactive CLI Mode

Launch the interactive terminal interface:

```bash
python main.py --cli
```

### PySide6 Desktop GUI Dashboard

Launch the graphical desktop interface with live event sourcing timeline and event replay:

```bash
python main.py --gui
```

### System Benchmarking Suite

Execute system performance benchmarks:

```bash
python main.py --benchmark
```

### Quality Evaluation Suite

Evaluate tool selection accuracy and planning optimality:

```bash
python main.py --eval
```

---

## Configuration & Profiles

System settings are defined in `config/config.yaml`. Profiles can be customized under `config/profiles/` to adapt system performance based on operational context:

- `Developer.yaml`: Optimizes logging verbosity and tool access for software development tasks.
- `Gaming.yaml`: Reduces background resource consumption and latency during gameplay.
- `Study.yaml`: Prioritizes memory retention, research tools, and distraction-free operation.

---

## Testing

Run the automated test suite using `pytest`:

```bash
pytest tests/
```

---

## License & Contributing

Contributions are welcome. Please refer to [CONTRIBUTING.md](file:///c:/Users/aeron/OneDrive/Documents/JARVIS/CONTRIBUTING.md) for guidelines on code formatting, testing requirements, and submission processes.
