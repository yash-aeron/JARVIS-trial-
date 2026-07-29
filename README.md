# JARVIS: Local-First AI Operating System Assistant

JARVIS is an event-driven, modular AI Operating System Assistant designed for privacy, local execution, and autonomous multi-step task planning. Built adhering to SOLID principles, strict decoupling, zero generic untyped dictionaries, and type-based dependency injection, JARVIS allows swapping local model providers, speech engines, vector stores, and automation tools without altering business logic.

---

## Key Features

- **Local-First Architecture**: Prioritizes local processing using models such as Ollama, Faster-Whisper, Silero VAD, and local Edge-TTS, ensuring data privacy and low execution latency.
- **Type-Based & Modular DI Bootstrapping**: Registers and resolves dependencies using strict Class and Interface types (`container.resolve(ISTTProvider)`). Registration is modularized into foundation, speech, brain, automation, memory, vision, security, and plugin layers.
- **Strongly Typed Pydantic Contracts**: Zero generic untyped dictionaries (`Dict[str, Any]`). Uses dedicated Pydantic models across all layers (`ExecutionContextModel`, `PlannerContextModel`, `OpenApplicationArgs`, `SystemControlArgs`, `LanguageDetectionModel`, `SystemStatusModel`, `BenchmarkResultModel`, `UserCommandResultModel`, `EpisodicMemoryItemModel`, `ProceduralMemoryItemModel`, `VisionObservationModel`, `SubagentTaskRequestModel`, `SecurityPolicyModel`).
- **Phase 0–1 Foundation & Operating Modes**: Extended `ModeManager` with 8 typed operating modes (`Study`, `Coding`, `Developer`, `Gaming`, `Focus`, `Meeting`, `Presentation`, `Travel`) and expanded Windows software catalog with Google STT & pyttsx3 fallback providers.
- **Phase 2 Reasoning & Reflection Engine**: Extended `DecisionEngine` with sub-goal decomposition, constraint evaluation, `ExecutiveAgent.reflect()` satisfaction loop, and automatic `FallbackPlanner` re-planning.
- **Phase 3 Episodic, Procedural & Vector Memory**: `MemoryManager` with session episodic logging, procedural sequence caching, rolling long-term summarization, and `sentence-transformers` vector embeddings.
- **Phase 4 Formalized Plugin Ecosystem**: Hot-loading `PluginManager` with permission-gate checks, JSON-Schema settings, and reference plugins (`spotify_control` and `vscode_workspace`).
- **Phase 5 Vision & Desktop Understanding**: `ScreenshotCaptureTool` (conforming to `ITool`), OCR text extraction, and accessibility-based UI element detection.
- **Phase 6 Multi-Agent Architecture**: Decoupled `ExecutiveAgent` into dedicated event-driven subagents (`PlanningSubagent`, `MemorySubagent`, `ExecutionSubagent`) over `AsyncEventBus`.
- **Phase 7 Security & Permissions**: Centralized `PermissionManager`, fine-grained capability sandboxing, and high-risk action approval mode.
- **Automated CI Benchmarking & Quality Assurance**: Continuous Integration pipeline (`.github/workflows/ci.yml`) enforcing static analysis (`pyflakes .`), unit tests (`pytest tests/`), and evaluation metrics.

---

## System Architecture

JARVIS follows a modular layer separation to achieve high maintainability and subsystem replaceability.

```text
User Input (Voice Stream / Text / Context Signals)
        │
        ▼
   SpeechManager (Silero VAD / Faster-Whisper / Wake Word) ──► [Event: speech.recognized (CID)] ──► AsyncEventBus
                                                                                                        │
                                                                                            EventStore (SQLite)
        ┌───────────────────────────────────────────────────────────────────────────────────────────────┘
        ▼
   ExecutiveAgent (Decision Engine: Intent, Risk Level, Context Snapshot, Memory Recall)
        │
        ├──► Conversational Query ──► ResponseGenerator ──► SpeechManager (Streaming Edge-TTS)
        │
        └──► Complex Multi-Step Goal
                     │
                     ▼
                  Planner (PromptManager ──► LLM JSON ──► PlanValidator ──► PlanOptimizer)
                     │
                     ▼
             PlanExecutor (Parallel Execution & Composite Ranking) ──► ActionQueue ──► ToolRegistry
                                                                                            │
        ┌───────────────────────────────────────────────────────────────────────────────────┴─────────────────────────┐
        ▼                                                   ▼                                                         ▼
 ApplicationLauncherTool (Win32 EnumWindows)    ContextReaderTool (UI Automation / Clipboard)    MemoryManagementTool / Plugin SDK
```

---

## Project Structure

```text
JARVIS/
├── .github/
│   └── workflows/    CI workflow pipeline (tests, benchmarks, SLA assertions)
├── agent/            Executive agent and decision engine components
├── automation/       Action queue (priority aging & worker pool), parallel plan executor, and undo management
├── benchmark/        Automated performance benchmarking suite and benchmark_ci SLA runner
├── brain/            Intent identification, LLM-first planner, plan validator, plan optimizer, and fallback planner
├── config/           System configuration parameters and environment profiles
├── context/          Windows context manager (foreground app, Unicode clipboard, selected text, UI Automation browser URL, workspace)
├── core/             Application container, interfaces, models (Pydantic contracts), EventStore, event bus, and service registry
├── dashboard/        PySide6 desktop graphical interface (event timeline, execution graph, state monitor, memory visualizer)
├── evaluation/       Tool selection accuracy and plan optimality evaluators
├── language/         Code-switching language identification and localization management
├── mcp/              Model Context Protocol adapters and tool registries
├── memory/           Rich vector memory schema, multi-factor weighted ranking, SQLite store, and DocumentIndexer
├── models/           Abstractions for LLMs, Faster-Whisper STT (VAD-gated & interruptible), and Edge-TTS engines
├── observability/    Structured logger, MetricsProvider, tracing, and diagnostics
├── plugins/          Plugin SDK (PluginManifest, PluginContext, BasePlugin) and hot-loading PluginManager
│   └── installed/    Directory containing installed third-party plugins (e.g. sample_weather)
├── prompts/          PromptManager (in-memory template caching) and Markdown prompt templates
├── resource/         GPU allocation (RTX 3050 Ti VRAM auto-offloading & warm-up) and system hardware resources
├── session/          Session history and state retention
├── skills/           Skill discovery engine and execution routines
├── speech/           Silero VAD, Wake-Word Detector, speech recognition, and streaming speech synthesis
├── state/            Guarded finite state machine and transition table
├── system/           System resource monitoring and runtime profile selection
├── tests/            Pytest unit, integration, and multi-step scenario test suite
├── tools/            System tools (AppLauncher, SystemControl, ContextReader, MemoryManagement) and ranking strategies
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

- **Python**: Version 3.10 or higher (3.11 recommended)
- **Ollama**: Running locally with a compatible LLM model (e.g., `qwen2.5-coder`, `llama3`, or `mistral`)
- **System Memory**: 8 GB RAM minimum (16 GB recommended)
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

   *Optional streaming speech dependencies:*
   ```bash
   pip install faster-whisper edge-tts torch
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

Launch the graphical desktop interface with live event sourcing timeline, execution graph inspector, state monitor, and memory visualizer:

```bash
python main.py --gui
```

### System Benchmarking Suite

Execute system performance benchmarks:

```bash
python main.py --benchmark
```

### SLA Threshold Benchmark Check (CI Mode)

Execute benchmarks with SLA threshold assertions (exits non-zero on SLA regression):

```bash
python main.py --ci-benchmark
```

### Quality Evaluation Suite

Evaluate tool selection accuracy and planning optimality:

```bash
python main.py --eval
```

---

## Testing & CI

Run the automated test suite using `pytest`:

```bash
pytest tests/
```

Run CI benchmark check locally:

```bash
python benchmark/benchmark_ci.py
```

---

## License & Contributing

Contributions are welcome. Please refer to [CONTRIBUTING.md](file:///c:/Users/aeron/OneDrive/Documents/JARVIS/CONTRIBUTING.md) for guidelines on code formatting, testing requirements, and submission processes.
