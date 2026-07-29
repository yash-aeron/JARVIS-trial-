# JARVIS Contributing Guidelines

## Coding Standards

1. **Strict Type Annotations**: All methods and functions must have type hints.
2. **Pydantic Validation**: Use Pydantic models for all data structures across subsystem boundaries.
3. **No Direct Third-Party Leakage**: Wrap external engines (Ollama, Whisper, EdgeTTS, ChromaDB) inside abstract Providers/Adapters.
4. **Correlation IDs**: All events, plans, and actions must pass `correlation_id`.
5. **Testing**: Run unit and integration tests via `python -m pytest tests/`.

## Git Workflow & Release Tags

- `v0.1 Foundation`: Core Interfaces, EventBus, StateManager, ServiceManager, Observability, Config Profiles.
- `v0.2 Speech`: SpeechManager, STT, TTS, VAD, Code-Switching Language Manager.
- `v0.3 Brain`: IntentEngine, ExecutiveAgent, Planner, DialogueManager.
- `v0.4 Automation`: ToolRegistry, Capability Discovery, ActionQueue, Executor, UndoManager.
- `v0.5 Memory`: Tagged Memory, ChromaDB, RAG Knowledge Base, Session & Context Managers.
- `v0.6 Dashboard`: PySide6 Desktop GUI, Live Event Timeline, Subsystem Dependency Graph.
- `v0.7 Vision`: OCR, Screen Inspector, UI Element Tracker.
- `v0.8 Plugins`: PluginManager, Hot-Loader, Custom Tools SDK.
- `v0.9 MCP`: Model Context Protocol Client & Server adapters.
- `v1.0 Stable`: Benchmarks, Quality Evaluation Framework, Production Release.
