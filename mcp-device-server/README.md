# mcp-device-server

Expose any emb-ai-kit device as a **standards-compliant MCP server**, so Claude,
ChatGPT, Cursor, or any MCP client can drive your hardware through natural-language
tool calls — no custom glue code on the client side.

```
 firmware (ESP32/STM32)  --framed UART-->  server.py  --MCP/stdio-->  LLM client
```

- **Zero third-party deps for the transport.** The MCP stdio transport is
  implemented directly on JSON-RPC 2.0 with the Python standard library, so it
  runs anywhere `python3` does.
- **Works without hardware.** With no `--port`, every tool returns a clear
  `[simulated]` message — perfect for client-side smoke tests.
- **Only `pyserial` is needed to talk to real silicon** (optional until then).

## Install

```bash
pip install pyserial          # only required for real hardware
```

## Run

```bash
# real device
python server.py --port COM3          # Windows
python server.py --port /dev/ttyUSB0  # Linux/macOS

# smoke test, no hardware
python server.py
```

## Wire it to an MCP client

Point your client at this command (example for Claude Desktop /
`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "emb-ai-kit": {
      "command": "python",
      "args": ["/absolute/path/to/mcp-device-server/server.py", "--port", "COM3"]
    }
  }
}
```

Once connected, the client sees three tools:

| Tool | Purpose |
|------|---------|
| `move_servo` | Drive one servo by pulse width (500–2500 µs). Validates range, never snaps. |
| `read_sensor` | Read a sensor value from the device (mic level, distance, ADC…). |
| `center_all` | Send every servo to its defined idle/center — safe to call on boot. |

## How it maps to the firmware

The server speaks the same framed serial protocol the firmware expects
(`{"cmd":"move","id":2,"us":1500}\n`). Add your own tools by appending to the
`build_tools()` list in `server.py` — each entry is a name, a JSON-schema
`inputSchema`, and a handler that receives the parsed `arguments` plus the live
`DeviceConnection`. The firmware counterpart lives in
`examples/serial_voice_agent/firmware/src/main.cpp`.

## Why this is the leverage

One server, many buyers. A client who needs "my [robot/sensor/box] controlled by
Claude" gets the same battle-tested bridge — that is the paid track described in
the root README's *Commercial track* section.
