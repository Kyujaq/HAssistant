     Project Memory (HAssistant-specific)

     Add the following entries:

     Architecture & Design Decisions

     - GPU allocation is intentional: GPU 0 (1080 Ti) for heavy Qwen vision model, GPU 1 (1070) for lighter Hermes-3/STT/TTS/Frigate
     - Orchestrator v2.0 uses tool provider pattern: HA connects directly to Ollama at port 11434, orchestrator provides tools at port 8082
     - Memory access is opt-in via letta_query tool, not automatically loaded for every query
     - External network "assistant_default" must exist before starting services

     Known Issues & Important Warnings

     - Letta Bridge uses fake_embed() for embeddings - this is a known placeholder that needs replacement with real embedding model in production
     - Port allocations avoid conflicts: postgres on 5432, redis on 6380 (to avoid conflicts with other instances)
     - NVIDIA_VISIBLE_DEVICES in docker-compose.yml sometimes conflicts with device_ids declarations

     Development Workflow

     - Memory API requires x-api-key header (default: "dev-key")
     - After orchestrator changes, test health: curl http://localhost:8082/healthz
     - After model changes, verify HA can see models at Settings → Ollama
     - Tool definitions must follow Ollama function calling format

     Recent Major Changes Context

     - Orchestrator refactored to v2.0: proxy → tool provider (46% code reduction)
     - Folder reorganization: files moved from root to services/, clients/, docs/, examples/, tests/, config/
     - HA Ollama integration URL changed from orchestrator:8082 to ollama-chat:11434

     User Memory (Cross-project preferences)

     Add the following entries:

     Communication Style

     - Prefers concise responses with short explanations (e.g., "this crashed because of wrong version library")
     - Will explicitly ask for more details when needed
     - Give instructions one step at a time (don't provide 10 steps when step 1 might fail)
     - Balanced command explanations (not every detail, not completely minimal)

     Proactiveness & Decision Making

     - Be proactive with suggestions
     - Format: "I have reviewed X and have Y suggestions to improve Z" - then wait for request for details
     - CRITICAL: Never make major architecture decisions without consulting first
     - Don't pivot away from architectural goals just because first attempt fails (e.g., don't switch GPU→CPU just because GPU didn't work immediately)
     - Involve user when stuck debugging - explain problem, don't loop endlessly

     Testing Philosophy

     - Don't always run tests automatically
     - Never run tests after documentation-only changes
     - Run tests when:
       - Confidence decreases due to many changes
       - Feature work is complete (even temporarily, as last step before moving on)

     Technical Background

     - Learning Docker, Home Assistant, LLMs, Python with this project
     - Amateur programming background - understands basic logic and can help with debugging strategies
     - Limited deep GPU/CUDA knowledge

     Issue Reporting

     - Definitely point out potential issues proactively
     - Keep issue descriptions concise

     Git/Commits

     - Learning git with this project
     - No specific commit message style preference