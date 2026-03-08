#!/bin/bash
# Ensure data directories are writable by appuser
# When bind-mounted from the host, they may be owned by root

if [ "$(id -u)" = "0" ]; then
    chown -R appuser:appuser /app/data /app/static/uploads
    exec gosu appuser "$@"
else
    exec "$@"
fi
