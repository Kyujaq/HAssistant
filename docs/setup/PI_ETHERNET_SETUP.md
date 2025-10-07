# Raspberry Pi Client - Ethernet Setup Guide

Your Pi is connected via **Ethernet cable** to the same network as your Home Assistant server.

---

## 🔍 Step 1: Find Your Server's IP Address

On your **main server (glad0s)**, run:

```bash
# Find your Ethernet IP
ip addr show | grep inet | grep -v 127.0.0.1 | grep -v inet6
```

Look for something like: `192.168.x.x` or `10.x.x.x`

**Example output:**
```
inet 192.168.2.13/24 brd 192.168.2.255 scope global enp3s0
```

Your server IP: **192.168.2.13** ← Use this!

---

## 📡 Step 2: Test Connectivity from Pi

On your **Raspberry Pi**, test if you can reach the server:

```bash
# Test ping
ping -c 3 192.168.2.13  # Replace with your server IP

# Test HA is reachable
curl -I http://192.168.2.13:8123

# Test Wyoming services
nc -zv 192.168.2.13 10300  # Whisper
nc -zv 192.168.2.13 10200  # Piper
```

All should respond/connect successfully.

---

## 🔑 Step 3: Create Long-Lived Access Token in HA

1. Open **Home Assistant** web UI
2. Click your **profile** (bottom left, your username)
3. Scroll down to **"Long-Lived Access Tokens"**
4. Click **"Create Token"**
5. Name: `Raspberry Pi Voice Client`
6. Click **Create**
7. **Copy the token** (you can't see it again!)
   - Looks like: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (very long)

---

## 📦 Step 4: Install Dependencies on Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pip python3-venv portaudio19-dev \
    alsa-utils git curl

# Create virtual environment
cd ~
python3 -m venv glados-env
source glados-env/bin/activate

# Install Python packages
pip install --upgrade pip
pip install pvporcupine numpy sounddevice requests pyaudio
```

---

## 📥 Step 5: Copy Pi Client to Raspberry Pi

### Option A: Direct Copy (if you have SSH access)

From your **main server**:

```bash
# Copy client script
scp /home/qjaq/HAssistant/pi_client.py pi@raspberrypi.local:~/

# Copy env example
scp /home/qjaq/HAssistant/pi_client.env.example pi@raspberrypi.local:~/.env
```

### Option B: Clone from Git (if you push to GitHub)

On the **Raspberry Pi**:

```bash
git clone <your-repo-url> ~/HAssistant
cp ~/HAssistant/pi_client.py ~/
cp ~/HAssistant/pi_client.env.example ~/.env
```

### Option C: Manual Copy

Create the file manually on Pi:

```bash
nano ~/pi_client.py
# Paste the content, save with Ctrl+X, Y, Enter
```

---

## ⚙️ Step 6: Configure .env on Raspberry Pi

Edit the configuration file:

```bash
nano ~/.env

# Optional: align voice bridge with automation services
echo "WINDOWS_VOICE_CONTROL_URL=http://windows-voice-control:8085" >> ~/.env
```

**Set these values:**

```bash
# Picovoice Wake Word Key (get from https://console.picovoice.ai/)
PV_ACCESS_KEY=YOUR_PICOVOICE_KEY_HERE

# Home Assistant URL (use your server's IP!)
HA_URL=http://192.168.2.13:8123  # ← CHANGE TO YOUR IP!

# Home Assistant Token (from Step 3)
HA_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # ← PASTE YOUR TOKEN!

# Wake Word Model
WAKE_WORD_MODEL=computer  # or: jarvis, alexa, hey google, etc.
```

**Save with:** `Ctrl+X`, then `Y`, then `Enter`

---

## 🎤 Step 7: Test Audio Devices on Pi

```bash
# List playback devices
aplay -l

# List recording devices
arecord -l

# Test microphone (record 5 seconds)
arecord -d 5 -f cd test.wav
aplay test.wav

# Test speaker
speaker-test -t wav -c 2 -l 1
```

If no sound:
```bash
# Set default audio device
sudo raspi-config
# Select: System Options → Audio → Choose your device
```

---

## 🚀 Step 8: Run the Client!

```bash
# Activate virtual environment (if not already active)
source ~/glados-env/bin/activate

# Export environment variables
export $(cat ~/.env | xargs)

# Run the client
python3 ~/pi_client.py
```

**Expected output:**
```
🚀 GLaDOS Pi Client Starting...
   HA URL: http://192.168.2.13:8123
✅ Wake word detection initialized (sample rate: 16000)
👂 Listening for wake word: 'computer'...
```

---

## 🗣️ Step 9: Test Voice Interaction!

1. Say: **"Computer"** (or your chosen wake word)
2. You should hear a beep
3. Say: **"What time is it?"**
4. GLaDOS should respond!

**Flow:**
```
You: "Computer"
  → Pi detects wake word
  → Beep plays
You: "What time is it?"
  → Pi records your speech
  → Sends to HA Whisper (STT)
  → HA processes with Ollama
  → HA responds with Piper (GLaDOS voice)
  → Pi plays response
```

---

## 🔧 Troubleshooting

### "Could not connect to HA"

```bash
# Verify HA URL is correct
curl http://192.168.2.13:8123/api/

# Should return: "API running"
```

### "401 Unauthorized"

- Your HA_TOKEN is wrong or expired
- Create a new token in HA

### "No audio output"

```bash
# Check ALSA config
alsamixer  # Adjust volume

# Test speaker directly
aplay /usr/share/sounds/alsa/Front_Center.wav
```

### "Wake word not detected"

- Check PV_ACCESS_KEY is correct
- Try different wake word: `WAKE_WORD_MODEL=jarvis`
- Adjust microphone volume in `alsamixer`
- Speak closer to microphone

### "Microphone not found"

```bash
# List audio devices
python3 << EOF
import sounddevice as sd
print(sd.query_devices())
EOF

# Set specific device in pi_client.py if needed
```

---

## 🔄 Auto-Start on Boot

Once it's working, make it auto-start:

```bash
# Create systemd service
sudo nano /etc/systemd/system/glados-client.service
```

**Paste:**

```ini
[Unit]
Description=GLaDOS Voice Client
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
EnvironmentFile=/home/pi/.env
ExecStart=/home/pi/glados-env/bin/python3 /home/pi/pi_client.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable glados-client
sudo systemctl start glados-client

# Check status
sudo systemctl status glados-client

# View logs
journalctl -u glados-client -f
```

---

## 📊 Network Diagram

```
┌─────────────────┐
│ Raspberry Pi    │
│ (Ethernet)      │
│ 192.168.2.X     │
└────────┬────────┘
         │
         │ Ethernet Cable
         │
┌────────┴────────────────────┐
│ Main Server (glad0s)        │
│ 192.168.2.13                │
│                             │
│  ┌────────────────────┐     │
│  │ Home Assistant     │     │
│  │ Port 8123          │     │
│  └─────┬──────────────┘     │
│        │                    │
│  ┌─────┴──────┐            │
│  │ Wyoming    │            │
│  │ - Whisper  │ :10300     │
│  │ - Piper    │ :10200     │
│  └────────────┘            │
│                             │
│  ┌────────────┐            │
│  │ Ollama     │ :11434     │
│  └────────────┘            │
└─────────────────────────────┘
```

---

## ✅ Complete Test Checklist

- [ ] Server IP found: `192.168.2.13`
- [ ] Pi can ping server
- [ ] Pi can reach HA: `curl http://192.168.2.13:8123`
- [ ] HA token created
- [ ] Dependencies installed on Pi
- [ ] `pi_client.py` copied to Pi
- [ ] `.env` configured with IP and token
- [ ] Microphone working: `arecord -d 5 test.wav`
- [ ] Speaker working: `aplay test.wav`
- [ ] `PV_ACCESS_KEY` set (from Picovoice)
- [ ] Client runs without errors
- [ ] Wake word detected: "Computer"
- [ ] Speech recorded after wake word
- [ ] GLaDOS responds!

---

## 🎉 Success!

You now have:
- 🎤 Wake word detection on Pi
- 🗣️ Voice commands via HA Assist
- 🧠 AI responses via Ollama
- 🔊 GLaDOS voice via Piper
- 🏠 Smart home control

**All running locally on your network!**
