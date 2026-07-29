# JARVIS: Local-First AI Operating System Assistant

JARVIS is an event-driven, modular AI Operating System Assistant designed for privacy, local execution, and autonomous multi-step task planning. Built adhering to SOLID principles, strict decoupling, and dependency injection, JARVIS allows swapping local model providers, speech engines, vector stores, and automation tools without altering business logic.

---

## Key Features

- **Local-First Architecture**: Prioritizes local processing using models such as Ollama, Whisper, ChromaDB, and local TTS, ensuring data privacy and low execution latency.
- **Event-Driven & Event-Sourced**: Asynchronous communications powered by `AsyncEventBus` with unified correlation IDs for tracing the complete execution lifecycle.
- **Executive Agent & Multi-Step Planner**: Decouples conversational interaction from complex execution planning. Generates structured, validated `ExecutionPlan` pipelines processed asynchronously by `PlanExecutor` and `ActionQueue`.
- **Global State Machine**: Unified state lifecycle management tracking assistant states (`IDLE`, `LISTENING`, `THINKING`, `PLANNING`, `EXECUTING`, `SPEAKING`, `ERROR`).
- **Flexible UI & Interfaces**: Supports interactive CLI terminal execution, a PySide6 Desktop GUI dashboard, and automated headless benchmarking suites.
- **Plugin & MCP Integration**: Extensible architecture supporting dynamic plugin discovery, Model Context Protocol (MCP) tool adapters, and capability registration via `ToolRegistry`.
- **System Observability**: Integrated performance metrics collection, tracing, system resource diagnostics, and quality evaluation suites.

---

## System Architecture

JARVIS follows a modular layer separation to achieve high maintainability and subsystem replaceability.

```
User Input (Voice / Text)
        │
        ▼
   SpeechManager (VAD / STT) ─── [Event: speech.recognized (Correlation ID)] ───► AsyncEventBus
                                                                                      │
        ┌─────────────────────────────────────────────────────────────────────────────┘
        ▼
  ExecutiveAgent (Decision Engine: Planning, Memory, Vision, Search)
        │
        ├──► Conversational Query ──► ResponseGenerator ──► SpeechManager (TTS)
        │
        └──► Complex Multi-Step Goal
                     │
                     ▼
                  Planner (Generates Pydantic ExecutionPlan)
                     │
                     ▼
                 PlanExecutor ──► ActionQueue (PENDING / RUNNING / COMPLETED) ──► ToolRegistry
```

---

## Project Structure

```text
JARVIS/
├── agent/            Executive agent and decision engine components
├── automation/       Action queue, plan execution engine, and undo management
├── benchmark/        Automated performance benchmarking suite
├── brain/            Intent identification, goal parsing, and multi-step planner
├── config/           System configuration parameters and environment profiles
├── context/          Context management and short-term memory assembly
├── core/             Application container, interfaces, event bus, and service registry
├── dashboard/        PySide6 desktop graphical interface
├── evaluation/       Tool selection accuracy and plan optimality evaluators
├── language/         Language identification and localization management
├── mcp/              Model Context Protocol adapters and tool registries
├── memory/           ChromaDB vector memory storage and schema management
├── models/           Abstractions for LLMs, STT, and TTS engines
├── observability/    Structured logger, metrics collection, tracing, and diagnostics
├── plugins/          Plugin SDK and runtime plugin loading system
├── prompts/          System prompt templates and intent directives
├── resource/         GPU allocation and system hardware resource management
├── session/          Session history and state retention
├── skills/           Skill discovery engine and execution routines
├── speech/           Voice activity detection, speech recognition, and speech synthesis
├── state/            Global finite state machine implementation
├── system/           System resource monitoring and runtime profile selection
├── tests/            Pytest unit and integration test suite
├── tools/            System tools and automated capability registry
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
- **Ollama**: Running locally with a compatible LLM model (e.g., `llama3` or `mistral`)
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
   ollama pull llama3
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
