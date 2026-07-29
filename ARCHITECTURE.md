# JARVIS Architecture Guide

## Overview

JARVIS is a local-first, event-driven, modular AI Operating System Assistant designed according to SOLID principles, Dependency Injection, and strict decoupling.

## Core Architectural Principles

1. **Subsystem Replaceability**: Every subsystem communicates exclusively through abstract interfaces (`core/interfaces.py`). Swapping Ollama with llama.cpp, Whisper with Parakeet, or ChromaDB with FAISS requires zero changes to business logic.
2. **Event-Driven & Event-Sourced**: Subsystems publish and subscribe to events on `AsyncEventBus`. All events are recorded with a unified **Correlation ID** for full request lifecycle tracing.
3. **Executive Agent & Multi-Step Planner**: Conversation and planning are decoupled. The Executive Agent decides what resources are needed, while the Planner produces pure `ExecutionPlan` data structures executed asynchronously by `PlanExecutor` through `ActionQueue`.
4. **Global State Machine**: `StateManager` tracks assistant state transitions (`IDLE`, `LISTENING`, `THINKING`, `PLANNING`, `EXECUTING`, `SPEAKING`, `ERROR`).

## High-Level Architecture Diagram

```
User Voice / Text Input
        │
        ▼
   SpeechManager (VAD / STT) ───[Event: speech.recognized (Correlation ID)]───► AsyncEventBus
                                                                                      │
        ┌─────────────────────────────────────────────────────────────────────────────┘
        ▼
 ExecutiveAgent (Decision Engine: Planning, Memory, Vision, Search)
        │
        ├──► Simple Conversation ──► ResponseGenerator ──► SpeechManager (TTS)
        │
        └──► Complex Multi-Step Goal
                     │
                     ▼
                  Planner (Generates Pydantic ExecutionPlan)
                     │
                     ▼
                PlanExecutor ──► ActionQueue (PENDING/RUNNING/COMPLETED) ──► ToolRegistry (Capability Discovery)
```
