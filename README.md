# JARVIS: Local-First AI Operating System Assistant

JARVIS is an event-driven, modular AI Operating System Assistant designed for privacy, local execution, and autonomous multi-step task planning. Built adhering to SOLID principles, strict decoupling, and type-based dependency injection, JARVIS allows swapping local model providers, speech engines, vector stores, and automation tools without altering business logic.

---

## Key Features

- **Local-First Architecture**: Prioritizes local processing using models such as Ollama, Whisper, ChromaDB, and local TTS, ensuring data privacy and low execution latency.
- **Type-Based & Config-Driven DI**: Registers and resolves singletons and factories using strict Class and Interface types (`container.resolve(ISTTProvider)`). Providers (`ISTTProvider`, `ITTSProvider`, `ILLMProvider`) are selected dynamically based on active configuration profiles.
- **Strongly-Typed Persistent Event Sourcing**: Asynchronous communications powered by `AsyncEventBus` with unified Correlation IDs. Every system event carries a strongly-typed Pydantic payload (`EventModel.payload`) and is persisted to a local SQLite Event Store (`data/event_store.db`) for black-box session replay.
- **Decoupled LLM-First Planner**: Generates capability-based plans from structured LLM JSON outputs. Prompt management is injected via DI (`PromptManager`), schema validation enforced by `PlanValidator` (verifying step IDs, dependency references, and registered capabilities), and offline steps handled by `FallbackPlanner`.
- **Dependency-Aware Parallel Execution**: Analyzes step dependencies (`depends_on`) and executes independent tasks concurrently via `asyncio.gather(*tasks)` through `PlanExecutor` and `ActionQueue`.
- **Pluggable Context-Aware Tool Scorer**: `ToolRegistry` uses an `IRankingStrategy` to evaluate capability specialization, permission level, runtime context (Windows foreground window & clipboard), and execution speed.
- **Native Process Control & App Focus**: `ApplicationLauncherTool` detects running processes (`psutil`), bringing existing application windows to the foreground or spawning new native subprocesses.
- **Guarded State Machine**: `StateManager` enforces valid finite state transitions (`transition_to`), raising `StateTransitionError` on invalid state jumps.
- **Flexible UI & Interfaces**: Supports interactive CLI terminal execution, a PySide6 Desktop GUI dashboard, and automated headless benchmarking suites.
- **Plugin & MCP Integration**: Extensible architecture supporting dynamic plugin discovery, Model Context Protocol (MCP) tool adapters, and capability registration via `ToolRegistry`.

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
            PlanExecutor (Parallel Execution & Ranked Tools) ──► ActionQueue ──► ToolRegistry
```

---

## Project Structure

```text
JARVIS/
├── agent/            Executive agent and decision engine components
├── automation/       Action queue, parallel plan executor, and undo management
├── benchmark/        Automated performance benchmarking suite
├── brain/            Intent identification, LLM-first planner, plan validator, and fallback planner
├── config/           System configuration parameters and environment profiles
├── context/          Windows API context manager (active window title, clipboard, mode)
├── core/             Application container, interfaces, models, event bus, and service registry
├── dashboard/        PySide6 desktop graphical interface
├── evaluation/       Tool selection accuracy and plan optimality evaluators
├── language/         Code-switching language identification and localization management
├── mcp/              Model Context Protocol adapters and tool registries
├── memory/           Tagged vector memory storage, SQLite schema, and retrieval ranking
├── models/           Abstractions for LLMs, STT, and TTS engines
├── observability/    Structured logger, metrics collection, tracing, and diagnostics
├── plugins/          Plugin SDK and runtime plugin loading system
├── prompts/          PromptManager and Markdown prompt templates
├── resource/         GPU allocation and system hardware resource management
├── session/          Session history and state retention
├── skills/           Skill discovery engine and execution routines
├── speech/           Voice activity detection, speech recognition, and speech synthesis
├── state/            Guarded finite state machine and transition table
├── system/           System resource monitoring and runtime profile selection
├── tests/            Pytest unit and integration test suite
├── tools/            System tools, process launcher, and pluggable ranking strategy
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
- **Optional**: NVIDIA GPU with CUDA support for accelerated local inference

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
