# JARVIS Technical Architecture & Design Document

## Architectural Overview

JARVIS is a local-first, event-driven AI Operating System Assistant built adhering strictly to SOLID principles, interface segregation, and type-based Dependency Injection.

---

## High-Level Execution Pipeline

```text
User Input (Voice / Text)
        │
        ▼
   SpeechManager (Streaming / Interruptible STT) ──► EventBus (Auto-Persisted to SQLite)
                                                             │
        ┌────────────────────────────────────────────────────┘
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

## Core Component Contracts

### 1. Dependency Container (`core/container.py`)
- Type-safe DI container requiring explicit Class and Interface types (`container.resolve(ISTTProvider)`).

### 2. Service Manager (`core/service_manager.py`)
- Lifecycle tracking with `ServiceState` enum (`NEW`, `STARTING`, `RUNNING`, `DEGRADED`, `STOPPING`, `STOPPED`, `FAILED`).
- `CircuitBreaker` tracking consecutive failures and cooldown timers.

### 3. Async Event Bus & Persistence (`core/event_bus.py`)
- Middleware chain (`add_middleware()`), automatic SQLite event persistence (`data/event_store.db`), and session event replay (`replay_events()`).

### 4. Pluggable Composite Ranking (`tools/ranking_strategy.py`)
- `CompositeRankingStrategy` evaluating Runtime Context, Permission Level, Performance Speed, and Historical Success Rate.

### 5. Memory & Context Manager (`memory/` & `context/`)
- `MemoryItemModel` with rich metadata (`importance`, `timestamp`, `project`, `language`, `source`, `confidence`, `access_count`, `last_accessed`, `embedding_version`).
- `ContextManager` querying Windows APIs for active window title (`GetForegroundWindow`) and clipboard text.
