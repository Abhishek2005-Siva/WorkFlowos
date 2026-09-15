"""Shared OAuth scope list for every Google integration.

All three integrations (Gmail, Calendar, Sheets) authenticate against the
same token file, obtained once via scripts/google_auth_setup.py with this
exact scope list. That's the part that matters: each integration MUST
load credentials with this same full list, not just the scope(s) it
personally needs.

Why: passing a narrower scope list to
`Credentials.from_authorized_user_file(path, scopes)` doesn't just filter
what that client *uses* — google-auth carries that narrower list into the
next refresh request. Whichever integration happens to refresh the
token first silently re-requests only its own scope, and Google issues a
new access token scoped to just that, discarding the others — even
though the refresh token itself was granted all four. Every other
integration then starts failing with "insufficient authentication
scopes" until someone re-runs the auth script. Sharing one list across
every integration is what prevents that narrowing from ever happening.
"""
from __future__ import annotations

GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/pubsub",
]
