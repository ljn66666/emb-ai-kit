# emb-ai-kit

> Minimal, battle-tested scaffolding to connect microcontrollers (ESP32 / STM32) to LLMs and MCP servers.

**Built from real hardware.** Every pitfall documented here was hit on actual silicon — a desktop robot with 4× SG90 servos and I2S audio on a Seeed XIAO ESP32S3 Sense — not copied from a tutorial. If you want your gadget to talk to an LLM without spending three days on brownout resets, start here.

---

## Why this exists

The "connect my device to AI" dream dies on three real killers that tutorials skip:

1. **Power starvation** — driving servos off the same 5 V rail that powers the MCU. The inrush when a servo starts pulls the rail down; the ESP32 brownouts and reboots. Symptom: *"it resets whenever it moves."*
2. **Missing common ground** — using two supplies (one for logic, one for servos) with no shared GND. Result: random servo twitch, corrupted UART, *"works on the bench, dies in the enclosure."*
3. **Boot-state jitter** — ESP32 GPIO strapping pins (GPIO0 / GPIO2 / GPIO15) float or get pulled at boot. If a servo sits on one, it snaps to a random angle the instant you power on. No firmware fixes this; only correct pin choice + a defined idle state.

Plus two quieter ones: I2S audio fragility (clock skew, buffer underrun) and fragile serial protocols (no framing → one dropped byte desyncs the whole link).

## What it is

A three-layer bridge:

```
┌──────────────┐   framed UART   ┌──────────────┐   HTTP / WS    ┌─────────────┐
│   Firmware   │ ──────────────▶ │ Host bridge  │ ─────────────▶ │  LLM / MCP  │
│ ESP32/STM32  │ ◀────────────── │   Python     │ ◀───────────── │ Claude / …   │
└──────────────┘   commands      └──────────────┘   tool calls   └─────────────┘
```

- **Firmware** — reads sensors / drives actuators, speaks a framed serial protocol, survives brownouts.
- **Host bridge** — the *only* place that touches the LLM API key. Turns serial events into LLM calls and LLM tool-calls into serial commands. Can also expose the device as an **MCP server** so any MCP client can drive your hardware.
- **LLM / MCP** — your model of choice; device actions are exposed as MCP tools.

## Supported hardware (tested)

| Part | Role | Notes |
|------|------|-------|
| Seeed XIAO ESP32S3 Sense | MCU + mic | 8 PWM pins (D1–D7 used for servos) |
| MAX98357A | I2S amp → speaker | BCLK=12, LRC=13, DIN=14 |
| SG90 / MG90S / MG996R | actuators | **independent 5 V supply, shared GND** |
| STM32 (F4/F1) | alternative MCU | port tracked in roadmap |

## Quick start

```bash
git clone https://github.com/ljn66666/emb-ai-kit
cd emb-ai-kit/examples/serial_voice_agent
# 1. flash firmware (PlatformIO)
cd firmware && pio run -t upload
# 2. run the host bridge (it calls the LLM and drives the servos)
cd ../host && pip install -r requirements.txt && python bridge.py --port COMx
```

## The real pitfalls (read before you wire anything)

### 1. Power — never share the MCU's 5 V with servos
A single SG90 can draw ~700 mA at stall. Four of them on a USB 2.0 port (500 mA budget) is mathematically impossible — you will brownout. Give servos their **own** 5 V supply (≥3 A for 4× SG90) and connect its GND to the MCU GND. Rule of thumb validated on real hardware: peak demand ÷ available current should stay under ~70 %; 70–120 % is flaky; above that it will reset.

### 2. Common ground is mandatory
Two supplies with no shared GND = floating reference = random twitch and corrupted UART. One wire from servo-supply GND to MCU GND fixes 80 % of "ghost" bugs.

### 3. Boot jitter — keep servos off the strapping pins
On ESP32, GPIO0 / GPIO2 / GPIO15 are sampled at boot. If a servo is wired there, it jerks on power-up. On the XIAO ESP32S3 we use **D1–D7** for servos and leave D0 (a strapping-adjacent pin) free. In firmware, set every servo pin to a defined idle (1500 µs = center) *before* attaching the PWM channel, so even a glitch can't snap it.

### 4. I2S audio
Clock skew between BCLK/LRCLK and the master causes clicks and underruns. Keep the I2S GPIOs short, set the sample rate explicitly, and size the DMA buffer for your frame size. The on-board mic on the Sense variant is the easiest path; an external INMP441 is more repeatable across units.

### 5. Serial framing
Never send raw `angle=90` strings. Use a length-prefixed or delimiter-framed protocol (see the example: `{"cmd":"move","id":2,"us":1500}\n`). One dropped byte in a positional protocol desyncs the parser permanently; a framed one recovers on the next delimiter.

## Project structure

```
emb-ai-kit/
├── README.md
├── examples/
│   └── serial_voice_agent/        # voice/text → LLM → servo actions
│       ├── README.md
│       ├── firmware/              # ESP32S3 firmware (PlatformIO)
│       │   ├── platformio.ini
│       │   └── src/main.cpp
│       └── host/
│           ├── bridge.py          # serial ↔ LLM, optional MCP exposure
│           └── requirements.txt
└── mcp-device-server/             # turn the device into an MCP server
    ├── server.py                  # stdlib MCP stdio transport (no 3rd-party deps)
    ├── requirements.txt
    └── README.md
```

## Roadmap

- [x] `mcp-device-server` — **shipped.** Zero-dependency MCP stdio server that turns any emb-ai-kit device into MCP tools (`move_servo` / `read_sensor` / `center_all`). See [`mcp-device-server/`](mcp-device-server/).
- [ ] `servo-stabilizer` library — deterministic boot init, anti-jitter, current-aware throttling
- [ ] STM32 HAL port
- [ ] Fritzing / KiCad reference schematic for the power-split board

## Contributing

MIT. PRs welcome — especially pitfall write-ups that include an oscilloscope trace or a minimal repro.

## Sponsorship

If emb-ai-kit saves you debug days, sponsor via **GitHub Sponsors**. Sponsors get priority issue response and early access to the `servo-stabilizer` and `mcp-device-server` modules.

## Commercial track

The core library is **MIT — free even for commercial use**. The paid track is custom work: a bespoke MCP device server, white-label firmware, or on-site integration. That is where the real leverage lives — *one build, many buyers* — instead of billing hours.

## License

MIT — use it commercially, just keep the attribution.
