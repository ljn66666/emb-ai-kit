#!/usr/bin/env python3
"""
emb-ai-kit · mcp-device-server
==============================

Turn any microcontroller that speaks the emb-ai-kit framed serial protocol into
a standards-compliant **MCP (Model Context Protocol) server**, so that Claude,
ChatGPT, Cursor, or any MCP client can drive your hardware with natural-language
tool calls.

    firmware (ESP32/STM32)  --framed UART-->  this server  --MCP/stdio-->  LLM client

Zero third-party dependencies: the MCP stdio transport is implemented directly
on top of the JSON-RPC 2.0 spec with the Python standard library, so it runs
anywhere `python3` does. (If you prefer the official SDK, swap the transport —
the tool handlers are SDK-agnostic.)

Protocol reference: https://modelcontextprotocol.io

Quick start
-----------
    pip install pyserial            # only needed for real hardware
    python server.py --port COM3    # or /dev/ttyUSB0
    # point your MCP client at:  ["python", "server.py", "--port", "COM3"]

Without --port the server still starts and every tool returns a clear
"device not connected" message — handy for client-side smoke tests.
"""

import argparse
import json
import sys
import time

try:
    import serial  # pyserial; optional until you connect real hardware
except Exception:  # pragma: no cover - environment without pyserial
    serial = None


# --------------------------------------------------------------------------- #
# Device layer — wraps the framed serial protocol from emb-ai-kit firmware.
# One JSON object per line:  {"cmd":"move","id":2,"us":1500}
# --------------------------------------------------------------------------- #
class DeviceConnection:
    """Talks to the firmware over a framed UART link."""

    def __init__(self, port=None, baud=115200, timeout=2.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._ser = None
        if port:
            self.connect()

    def connect(self):
        if serial is None:
            raise RuntimeError("pyserial not installed (pip install pyserial)")
        self._ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        time.sleep(1.5)  # let the MCU boot and the PWM idle settle
        return True

    @property
    def connected(self):
        return self._ser is not None and self._ser.is_open

    def send(self, obj):
        if not self.connected:
            return None
        line = (json.dumps(obj) + "\n").encode()
        self._ser.write(line)
        return self._read_ack()

    def _read_ack(self):
        try:
            raw = self._ser.readline()
        except Exception:
            return {"ok": False, "error": "read timeout"}
        if not raw:
            return {"ok": True}  # firmware is fire-and-forget by default
        try:
            return json.loads(raw.decode().strip())
        except Exception:
            return {"ok": True, "raw": raw.decode(errors="replace")}


# --------------------------------------------------------------------------- #
# Tool registry — add your own tools here. Each entry: name, schema, handler.
# Handlers receive the parsed `arguments` dict and the live DeviceConnection.
# --------------------------------------------------------------------------- #
def build_tools(device: DeviceConnection):
    def move_servo(args):
        servo_id = int(args.get("id", 0))
        us = int(args.get("us", 1500))
        if not 500 <= us <= 2500:
            return _err(f"us must be in [500, 2500], got {us}")
        ack = device.send({"cmd": "move", "id": servo_id, "us": us})
        if ack is None:
            return _msg(f"[simulated] servo {servo_id} -> {us} us (no device connected)")
        return _msg(f"servo {servo_id} -> {us} us  ack={ack}")

    def read_sensor(args):
        sensor_id = int(args.get("id", 0))
        ack = device.send({"cmd": "read", "id": sensor_id})
        if ack is None:
            return _msg(f"[simulated] sensor {sensor_id} read (no device connected)")
        return _msg(f"sensor {sensor_id} -> {ack}")

    def center_all(args):
        ack = device.send({"cmd": "center_all"})
        if ack is None:
            return _msg("[simulated] all servos centered (no device connected)")
        return _msg(f"all servos centered  ack={ack}")

    return [
        {
            "name": "move_servo",
            "description": "Drive one servo to a pulse width in microseconds "
                           "(500=max CCW, 1500=center, 2500=max CW). Matches the "
                           "emb-ai-kit firmware 'move' command.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Servo index, 0-based"},
                    "us": {"type": "integer", "description": "Pulse width in microseconds (500-2500)"},
                },
                "required": ["id", "us"],
            },
            "handler": move_servo,
        },
        {
            "name": "read_sensor",
            "description": "Read a sensor value from the connected device "
                           "(e.g. mic level, ultrasonic distance, ADC).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Sensor index, 0-based"},
                },
                "required": ["id"],
            },
            "handler": read_sensor,
        },
        {
            "name": "center_all",
            "description": "Send every servo to its defined idle/center position. "
                           "Safe to call on boot — the firmware sets idle before "
                           "attaching PWM so nothing snaps.",
            "inputSchema": {"type": "object", "properties": {}},
            "handler": center_all,
        },
    ]


def _msg(text):
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _err(text):
    return {"content": [{"type": "text", "text": text}], "isError": True}


# --------------------------------------------------------------------------- #
# MCP stdio transport (JSON-RPC 2.0 over newline-delimited stdout/stdin).
# --------------------------------------------------------------------------- #
SUPPORTED_PROTOCOL = "2024-11-05"


class MCPServer:
    def __init__(self, device: DeviceConnection):
        self.device = device
        self.tools = build_tools(device)
        self._initialized = False

    def _tool_by_name(self, name):
        for t in self.tools:
            if t["name"] == name:
                return t
        return None

    def handle(self, message: dict) -> dict | None:
        method = message.get("method")
        msg_id = message.get("id")

        # notifications have no id and need no response
        if msg_id is None and method == "notifications/initialized":
            self._initialized = True
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": message["params"].get("protocolVersion", SUPPORTED_PROTOCOL),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "emb-ai-kit-device-server", "version": "0.1.0"},
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": t["name"],
                            "description": t["description"],
                            "inputSchema": t["inputSchema"],
                        }
                        for t in self.tools
                    ]
                },
            }

        if method == "tools/call":
            params = message.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            tool = self._tool_by_name(name)
            if tool is None:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": _err(f"unknown tool: {name}"),
                }
            try:
                result = tool["handler"](arguments)
            except Exception as e:  # never crash the server on a bad call
                result = _err(f"tool {name} failed: {e}")
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}

        # method not implemented
        if msg_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }
        return None

    def run(self):
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            response = self.handle(message)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="emb-ai-kit MCP device server")
    parser.add_argument("--port", default=None, help="Serial port, e.g. COM3 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    device = DeviceConnection(port=args.port, baud=args.baud)
    MCPServer(device).run()


if __name__ == "__main__":
    main()
