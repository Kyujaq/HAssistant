# Configuration Files

This directory contains example configuration files for HAssistant services and clients.

## Environment Files

### .env.example
**Purpose**: Main environment configuration for docker-compose services

**Contains**:
- PostgreSQL credentials
- Redis credentials
- Letta Bridge API key
- Home Assistant URL and token
- Model names and endpoints

**Usage**:
```bash
# Copy to root directory
cp config/.env.example .env
# Edit with your values
nano .env
```

**Required Variables**:
- `POSTGRES_PASSWORD` - PostgreSQL password
- `REDIS_PASSWORD` - Redis password
- `BRIDGE_API_KEY` - Letta Bridge API key
- `HA_URL` - Home Assistant URL
- `HA_TOKEN` - Home Assistant long-lived token

---

### pi_client.env.example
**Purpose**: Raspberry Pi client configuration

**Contains**:
- Porcupine wake word API key
- Home Assistant connection details
- Audio device configuration
- Wake word settings

**Usage**:
```bash
# On your development machine
scp config/pi_client.env.example pi@raspberrypi.local:~/pi_client.env
# On Raspberry Pi
nano ~/pi_client.env
```

---

### computer_control_agent.env.example
**Purpose**: Computer control agent configuration

**Contains**:
- Vision gateway URL
- Ollama model settings
- Home Assistant integration
- Action confirmation settings
- Safety limits

**Usage**:
```bash
cp config/computer_control_agent.env.example computer_control_agent.env
nano computer_control_agent.env
```

---

### windows_voice_control.env.example
**Purpose**: Windows Voice control bridge configuration

**Contains**:
- Piper TTS endpoint
- Voice model selection
- Audio output device
- Command timing settings

**Usage**:
```bash
cp config/windows_voice_control.env.example .env
nano .env
```

---

## Requirements Files

### computer_control_requirements.txt
**Purpose**: Python dependencies for computer control agent

**Installation**:
```bash
pip install -r config/computer_control_requirements.txt
```

**Includes**:
- pyautogui - Mouse/keyboard automation
- pytesseract - OCR
- opencv-python - Image processing
- pillow - Image handling
- numpy - Array operations
- requests - HTTP client
- flask - Web server (for HA integration)

---

## Configuration Best Practices

### Security
1. **Never commit actual credentials** - Keep `.env` files in `.gitignore`
2. **Use strong passwords** - For PostgreSQL, Redis, and API keys
3. **Restrict API access** - Use network isolation where possible
4. **Rotate credentials** - Especially long-lived tokens

### File Placement
- `.env` - Repository root (for docker-compose)
- `pi_client.env` - Raspberry Pi home directory
- `computer_control_agent.env` - Repository root or agent directory
- `windows_voice_control.env` - Repository root or client directory

### Environment Variables Priority
1. Environment variables set in shell
2. `.env` file (for docker-compose)
3. Service-specific config files
4. Default values in code

---

## Quick Start Checklist

- [ ] Copy `config/.env.example` to `.env`
- [ ] Set PostgreSQL password
- [ ] Set Redis password
- [ ] Generate Bridge API key (or use dev-key for testing)
- [ ] Get Home Assistant long-lived token
- [ ] Set Home Assistant URL
- [ ] (Optional) Configure Pi client
- [ ] (Optional) Configure computer control
- [ ] (Optional) Configure Windows Voice control

---

## Troubleshooting

**Problem**: Docker Compose can't find `.env`  
**Solution**: Make sure `.env` is in the repository root, not in `config/`

**Problem**: Services can't connect  
**Solution**: Check network settings in docker-compose.yml

**Problem**: Authentication errors  
**Solution**: Verify API keys and tokens are correct and not expired

---

## See Also

- [Main README](../README.md) - Overall setup instructions
- [Quick Start Guide](../docs/setup/QUICK_START.md) - Fast track setup
- [Memory Integration](../docs/architecture/MEMORY_INTEGRATION.md) - Memory system configuration
