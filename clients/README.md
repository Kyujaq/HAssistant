# Client Scripts

This directory contains client scripts that connect to and interact with the HAssistant services.

## Available Clients

### pi_client.py
**Purpose**: Raspberry Pi voice client for wake word detection and voice processing

**Features**:
- Porcupine wake word detection
- Integrates with Home Assistant Assist API
- Audio capture and playback
- Automatic reconnection
- Status indicators

**Setup**: See [docs/setup/PI_SETUP.md](../docs/setup/PI_SETUP.md)

**Usage**:
```bash
# Copy configuration
cp config/pi_client.env.example pi_client.env
# Edit configuration
nano pi_client.env
# Run client
python3 clients/pi_client.py
```

---

## Running Clients

Most clients require configuration files:

```bash
# Copy example configs
cp config/pi_client.env.example pi_client.env

# Edit with your settings
nano pi_client.env

# Run the client
python3 clients/pi_client.py
```

## See Also

- [Configuration Files](../config/README.md) - Configuration documentation
- [Setup Guides](../docs/setup/) - Setup instructions
- [Main README](../README.md) - Overall project documentation
