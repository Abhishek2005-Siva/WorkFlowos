"""Master live/stopped switch for the automated pipeline.

Defaults to NOT live on every boot — a fresh deploy should never silently
resume taking real-world actions (real calendar invites, real Slack
posts) without an explicit "Go Live" click. Manual dashboard buttons
("Run Demo", "Process Inbox") are the user's own explicit action each
time and aren't gated by this; this specifically controls whether the
Gmail push webhook actually processes what it receives, since that's the
one entry point that can fire without the user actively choosing to at
that moment.
"""
from __future__ import annotations


class SystemState:
    def __init__(self) -> None:
        self.is_live: bool = False
        self.last_watch_renewal: float | None = None


system_state = SystemState()
