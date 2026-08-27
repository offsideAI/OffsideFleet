"""M1's hard-coded Blueprint IR. Replaced by real Blueprint/BlueprintVersion rows in M2."""

from typing import Any

M1_BLUEPRINT_IR: dict[str, Any] = {
    "schemaVersion": "0-m1",
    "identity": {
        "name": "Pathfinder",
        "persona": "A terse, precise operations analyst. Answers in under 120 words.",
    },
    "model": {"provider": "anthropic", "id": "claude-opus-5", "maxTokens": 1024},
    "systemPrompt": (
        "You are Pathfinder, OffsideFleet's first agent. Answer the user's request "
        "directly and concisely."
    ),
    "tools": [],
    "budget": {},
    "triggers": [],
}
