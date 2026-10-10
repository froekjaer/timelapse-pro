#!/bin/sh
# Forced command for the shared Headend wake key (Peter, 2026-10-10).
# The key is only accepted through the SSH tunnel (from="127.0.0.1,::1") with
# `restrict` (no pty, forwarding or file transfer), and whatever the client
# asks for, only this runs: it bumps the mtime of a file the Edge agent
# watches, and the agent then runs its normal authenticated /sync at once.
# -c: never create the file (the agent owns it); nothing else is possible.
exec /usr/bin/touch -c /run/timelapse/wake-request
