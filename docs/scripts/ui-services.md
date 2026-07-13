# UI services

`ui/server.py` serves the local control plane and API on the validated bind host/port. It builds the safe documentation index, exposes redacted configuration, and persists MCP Builder/workflow/audit state in SQLite. `ui/voice_server.py` is a separate optional paid-inference process with a hard local ledger. Neither service should bind remotely without production authentication, authorization, TLS, CSRF, rate-limit, and secret-manager controls.
