# Latency & Streaming Checks


## Streaming TTS
- In HA, set TTS to `http://192.168.2.13:10210/wyoming/tts` and speak a long paragraph.
- Expect audio to begin < 500 ms and continue in chunks.


## GPU STT
- Run `watch -n1 nvidia-smi`.
- Speak 10 short utterances; confirm GPU1 utilization.
- Record round-trip vs CPU baseline.
