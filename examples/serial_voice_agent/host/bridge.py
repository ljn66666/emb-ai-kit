#!/usr/bin/env python3
"""emb-ai-kit · host bridge for serial_voice_agent.

Reads text from stdin (or a microphone later), calls an LLM, parses the
returned action, and writes it to the device over serial.

The device NEVER sees the API key. Swap the model or expose the device as an
MCP server by editing only this file.

Usage:
    OPENAI_API_KEY=sk-... python bridge.py --port COMx
"""
import argparse
import json
import os
import sys
import serial
from openai import OpenAI

# ---- device contract ----------------------------------------------------
# Servo ids 0..6 map to the firmware's D1..D7. us = pulse width in
# microseconds (500=max CCW, 1500=center, 2500=max CW).
SYSTEM_PROMPT = """You are the motion controller for a 7-servo desktop robot.
Translate the user's instruction into ONE servo action and reply with ONLY
JSON of the form:
  {"cmd":"move","id":<0-6>,"us":<500-2500>}
or {"cmd":"center"} to recenter all servos.
Never output anything except the JSON object."""

def llm_action(client, model, text):
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content.strip()
    return json.loads(raw)  # raises if the LLM misbehaved -> caller handles

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--model", default="gpt-4o-mini")
    args = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("set OPENAI_API_KEY first")
    client = OpenAI(api_key=key)

    ser = serial.Serial(args.port, args.baud, timeout=1)
    print(f"[bridge] connected to {args.port}; type instructions, Ctrl-C to quit")

    while True:
        try:
            text = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        try:
            action = llm_action(client, args.model, text)
            ser.write((json.dumps(action) + "\n").encode())
            # wait for device ack
            line = ser.readline().decode(errors="ignore").strip()
            print(f"[device] {line}")
        except Exception as e:
            print(f"[bridge] {type(e).__name__}: {e}")

    ser.close()

if __name__ == "__main__":
    main()
