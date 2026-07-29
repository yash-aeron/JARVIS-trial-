# JARVIS Event Catalogue

All events carry a unified `correlation_id` to link speech recognition, intent detection, planning, tool execution, and response synthesis.

| Event Topic | Publisher | Subscriber(s) | Description |
|---|---|---|---|
| `speech.recognized` | SpeechManager | ExecutiveAgent, Dashboard | Emitted when user audio is transcribed. |
| `intent.detected` | ExecutiveAgent | Planner, DialogueManager | Emitted after intent classification. |
| `plan.created` | Planner | PlanExecutor, Dashboard | Emitted when an ExecutionPlan is generated. |
| `tool.started` | PlanExecutor | ActionQueue, Dashboard | Emitted before a tool executes. |
| `tool.finished` | PlanExecutor | UndoManager, Dashboard | Emitted after a tool finishes execution. |
| `speech.spoke` | SpeechManager | Dashboard | Emitted when TTS synthesis completes. |
| `system.state_changed` | StateManager | Dashboard | Emitted whenever AssistantState transitions. |
