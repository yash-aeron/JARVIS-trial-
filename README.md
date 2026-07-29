# JARVIS: Local-First AI Operating System Assistant

JARVIS is an event-driven, modular AI Operating System Assistant designed for privacy, local execution, and autonomous multi-step task planning. Built adhering to SOLID principles, strict decoupling, and type-based dependency injection, JARVIS allows swapping local model providers, speech engines, vector stores, and automation tools without altering business logic.

---

## Key Features

- **Local-First Architecture**: Prioritizes local processing using models such as Ollama, Whisper, ChromaDB, and local TTS, ensuring data privacy and low execution latency.
- **Type-Based & Modular DI Bootstrapping**: Registers and resolves dependencies using strict Class and Interface types (`container.resolve(ISTTProvider)`). Registration is modularized into foundation, speech, brain, automation, memory, and plugin layers.
- **Circuit Breakers & Service Lifecycle**: Subsystems implement explicit lifecycle states (`NEW`, `STARTING`, `RUNNING`, `DEGRADED`, `STOPPING`, `STOPPED`, `FAILED`). `CircuitBreaker` tracks consecutive failures and cooldown timers to prevent continuous retries on degraded services.
- **Middleware-Enabled Event Bus & Replay**: Powered by `AsyncEventBus` with unified Correlation IDs, middleware chains (`add_middleware()`), automatic SQLite persistence (`data/event_store.db`), and session event replay (`replay_events()`).
- **Decoupled LLM-First Planner**: Generates capability-based plans from structured LLM JSON outputs. Injects `PromptManager`, `PlanValidator` (verifying step IDs, dependency references, and registered capabilities), and `FallbackPlanner` via DI.
- **Priority Action Queue & Parallel Execution**: `ActionQueue` uses `heapq` priority sorting, cancellation, pause/resume, and progress/ETA tracking. `PlanExecutor` executes independent tasks concurrently via `asyncio.gather(*tasks)`.
- **Composite Tool Ranking Strategy**: `ToolRegistry` uses a `CompositeRankingStrategy` evaluating capability specialization, runtime context (Windows foreground window & clipboard), permission level, performance speed, and historical success rate.
- **Native Process Control & App Focus**: `ApplicationLauncherTool` detects running processes (`psutil`), bringing existing application windows to the foreground or spawning new native subprocesses.
- **Guarded State Machine**: `StateManager` enforces valid finite state transitions (`transition_to`), raising `StateTransitionError` on invalid state jumps.
- **System Observability & Latency Metrics**: Structured logging with correlation IDs and `MetricsCollector` tracking latencies across planner, tool, memory retrieval, speech, and event bus operations.
- **Flexible UI & Interfaces**: Supports interactive CLI terminal execution, a PySide6 Desktop GUI dashboard, and automated headless benchmarking suites.

---

## System Architecture

JARVIS follows a modular layer separation to achieve high maintainability and subsystem replaceability.

```text
User Input (Voice / Text)
        │
        ▼
   SpeechManager (VAD / STT) ─── [Event: speech.recognized (Correlation ID)] ───► AsyncEventBus
                                                                                      │ (Persisted to SQLite)
        ┌─────────────────────────────────────────────────────────────────────────────┘
        ▼
  ExecutiveAgent (Decision Engine: Confidence, Risk Level, Planning, Memory, Search)
        │
        ├──► Conversational Query ──► ResponseGenerator ──► SpeechManager (TTS)
        │
        └──► Complex Multi-Step Goal
                     │
                     ▼
                  Planner (PromptManager ──► LLM JSON ──► PlanValidator)
                     │
                     ▼
            PlanExecutor (Parallel Execution & Composite Ranking) ──► ActionQueue ──► ToolRegistry
```

---

## Project Structure

```text
JARVIS/
├── agent/            Executive agent and decision engine components
├── automation/       Action queue (heapq priority), parallel plan executor, and undo management
├── benchmark/        Automated performance benchmarking suite
├── brain/            Intent identification, LLM-first planner, plan validator, and fallback planner
├── config/           System configuration parameters and environment profiles
├── context/          Windows API context manager (active window title, clipboard, mode)
├── core/             Application container, interfaces, models, event bus (middleware/replay), and service registry
├── dashboard/        PySide6 desktop graphical interface (live event pipeline visualizer)
├── evaluation/       Tool selection accuracy and plan optimality evaluators
├── language/         Code-switching language identification and localization management
├── mcp/              Model Context Protocol adapters and tool registries
├── memory/           Rich vector memory schema, SQLite persistence, and multi-factor ranking
├── models/           Abstractions for LLMs, STT (streaming & interruptible), and TTS engines
├── observability/    Structured logger, metrics collection (latencies), tracing, and diagnostics
├── plugins/          Plugin SDK and runtime plugin loading system
├── prompts/          PromptManager and Markdown prompt templates
├── resource/         GPU allocation (RTX 3050 Ti VRAM management) and system hardware resources
├── session/          Session history and state retention
├── skills/           Skill discovery engine and execution routines
├── speech/           Voice activity detection, speech recognition, and speech synthesis
├── state/            Guarded finite state machine and transition table
├── system/           System resource monitoring and runtime profile selection
├── tests/            Pytest unit, integration, and multi-step scenario test suite
├── tools/            System tools, process launcher, and composite ranking strategy
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
- **Optional**: NVIDIA GPU with CUDA support for accelerated local inference (optimized for RTX 3050 Ti)

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

Launch the graphical desktop interface:

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
