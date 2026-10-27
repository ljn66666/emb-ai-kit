# Example: serial_voice_agent

A minimal **text/voice → LLM → servo** pipeline running on a Seeed XIAO ESP32S3 Sense with 4× SG90 servos and a MAX98357A I2S amplifier. It proves the three-layer bridge from the root README on real hardware.

## Bill of materials

| Qty | Part | Notes |
|-----|------|-------|
| 1 | Seeed XIAO ESP32S3 Sense | MCU + onboard mic |
| 4 | SG90 servo | 5 V, ~700 mA stall each |
| 1 | MAX98357A breakout | I2S → speaker |
| 1 | 5 V / ≥3 A supply | **servo rail only** |
| — | wire, 470 µF cap | across servo 5 V/GND |

## Wiring

**Servos (use D1–D7, never D0 — strapping safety):**
```
Servo 1 → D1   Servo 2 → D2   Servo 3 → D3   Servo 4 → D4
Servo 5 → D5   Servo 6 → D6   Servo 7 → D7   (D0 left free)
VCC → servo 5 V supply   GND → servo 5 V supply GND → ALSO to XIAO GND
Signal → D1..D7
```

**MAX98357A (I2S out):**
```
BCLK → GPIO12   LRCLK → GPIO13   DIN → GPIO14
Vin → 5 V (logic ok at 3.3 V too)   GND → shared GND
```

**Power rule (non-negotiable):** servos get their own 5 V / 3 A supply. Connect that supply's GND to the XIAO GND. Do **not** power servos from the XIAO 5 V pin.

## Run it

```bash
# firmware
cd firmware && pio run -t upload
# host bridge (replace COMx and set OPENAI_API_KEY)
cd ../host
pip install -r requirements.txt
OPENAI_API_KEY=sk-... python bridge.py --port COMx
```

Then type: `wave hello` or `turn to the left` — the bridge calls the LLM, gets back a JSON action, and writes it to the serial port; the firmware moves the servos.

## What this example proves

- Servos survive boot with **zero jitter** (idle state set before PWM attach — see `main.cpp`).
- A framed serial protocol recovers from dropped bytes.
- The API key never touches the device — only the host bridge holds it.
- Swapping the LLM or exposing the device as an MCP server is a one-file change in `bridge.py`.
