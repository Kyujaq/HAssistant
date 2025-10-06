# Documentation

Comprehensive documentation for HAssistant organized by category.

## Quick Start

For getting started quickly:
- [QUICK_START.md](setup/QUICK_START.md) - Fast track setup guide
- [HA_ASSIST_SETUP.md](setup/HA_ASSIST_SETUP.md) - Home Assistant configuration

## Documentation Categories

### 📚 Setup Guides (`setup/`)
Step-by-step instructions for setting up various components:

- **[QUICK_START.md](setup/QUICK_START.md)** - Quick setup guide
- **[HA_ASSIST_SETUP.md](setup/HA_ASSIST_SETUP.md)** - Home Assistant Assist configuration
- **[HA_VOICE_CONFIG.md](setup/HA_VOICE_CONFIG.md)** - Voice service configuration
- **[WYOMING_SETUP.md](setup/WYOMING_SETUP.md)** - Wyoming protocol setup
- **[PI_SETUP.md](setup/PI_SETUP.md)** - Raspberry Pi client setup
- **[PI_ETHERNET_SETUP.md](setup/PI_ETHERNET_SETUP.md)** - Pi ethernet configuration
- **[COMPUTER_CONTROL_QUICK_START.md](setup/COMPUTER_CONTROL_QUICK_START.md)** - Computer control setup
- **[WINDOWS_VOICE_ASSIST_SETUP.md](setup/WINDOWS_VOICE_ASSIST_SETUP.md)** - Windows Voice control setup
- **[WINDOWS_VOICE_CONTROL_QUICK_REF.md](setup/WINDOWS_VOICE_CONTROL_QUICK_REF.md)** - Windows Voice quick reference
- **[WINDOWS_VOICE_CLARITY_GUIDE.md](setup/WINDOWS_VOICE_CLARITY_GUIDE.md)** - Voice clarity optimization

### 🏗️ Architecture (`architecture/`)
System design and architecture documentation:

- **[MEMORY_INTEGRATION.md](architecture/MEMORY_INTEGRATION.md)** - Letta-style memory system (414 lines)
  - Comprehensive guide to the memory architecture
  - API endpoints and usage
  - Database schema
  - Performance optimization
  
- **[COMPUTER_CONTROL_ARCHITECTURE.md](architecture/COMPUTER_CONTROL_ARCHITECTURE.md)** - Computer control system design
  - Vision-based automation architecture
  - Integration with vision-gateway
  - Workflow descriptions
  
- **[COMPUTER_CONTROL_AGENT.md](architecture/COMPUTER_CONTROL_AGENT.md)** - Computer control agent details
  - Agent capabilities
  - Configuration options
  - Use cases

### 📝 Implementation Summaries (`implementation/`)
Summaries of completed features and PRs:

- **[memory-integration.md](implementation/memory-integration.md)** - Memory feature summary (245 lines)
- **[memory-integration-pr.md](implementation/memory-integration-pr.md)** - Memory PR summary (320 lines)
- **[qwen-pc-control.md](implementation/qwen-pc-control.md)** - Qwen PC control implementation (744 lines)
- **[computer-control-windows-voice.md](implementation/computer-control-windows-voice.md)** - Windows Voice integration (279 lines)
- **[voice-clarity.md](implementation/voice-clarity.md)** - Voice clarity enhancements (250 lines)
- **[windows-voice.md](implementation/windows-voice.md)** - Windows Voice implementation (319 lines)
- **[COMPUTER_CONTROL_WINDOWS_VOICE_INTEGRATION.md](implementation/COMPUTER_CONTROL_WINDOWS_VOICE_INTEGRATION.md)** - Integration details

### 🧪 Testing & Development

- **[TESTING_ROADMAP.md](TESTING_ROADMAP.md)** - Testing strategy and roadmap
- **[PR_COMMENTS_INTEGRATION.md](PR_COMMENTS_INTEGRATION.md)** - PR feedback integration notes

## Navigation Tips

### By Feature

**Memory System**:
1. Start with [architecture/MEMORY_INTEGRATION.md](architecture/MEMORY_INTEGRATION.md) for the full picture
2. See [implementation/memory-integration.md](implementation/memory-integration.md) for what was added
3. Check [implementation/memory-integration-pr.md](implementation/memory-integration-pr.md) for PR context

**Computer Control**:
1. Start with [setup/COMPUTER_CONTROL_QUICK_START.md](setup/COMPUTER_CONTROL_QUICK_START.md)
2. Read [architecture/COMPUTER_CONTROL_ARCHITECTURE.md](architecture/COMPUTER_CONTROL_ARCHITECTURE.md) for design
3. See [architecture/COMPUTER_CONTROL_AGENT.md](architecture/COMPUTER_CONTROL_AGENT.md) for agent details

**Windows Voice Control**:
1. Start with [setup/WINDOWS_VOICE_ASSIST_SETUP.md](setup/WINDOWS_VOICE_ASSIST_SETUP.md)
2. Use [setup/WINDOWS_VOICE_CONTROL_QUICK_REF.md](setup/WINDOWS_VOICE_CONTROL_QUICK_REF.md) as reference
3. Optimize with [setup/WINDOWS_VOICE_CLARITY_GUIDE.md](setup/WINDOWS_VOICE_CLARITY_GUIDE.md)

**Raspberry Pi Client**:
1. Start with [setup/PI_SETUP.md](setup/PI_SETUP.md)
2. For ethernet setup, see [setup/PI_ETHERNET_SETUP.md](setup/PI_ETHERNET_SETUP.md)

## Documentation Standards

- Setup guides are prescriptive (step-by-step)
- Architecture docs are descriptive (how it works)
- Implementation summaries capture what was built and why

## Contributing

When adding new documentation:
1. Place setup guides in `setup/`
2. Place architecture docs in `architecture/`
3. Place feature summaries in `implementation/`
4. Update this README to include the new document
