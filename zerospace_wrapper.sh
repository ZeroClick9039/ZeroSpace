#!/bin/bash
# Check if python3 is installed
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is required but not installed. Please install python3 to run ZeroSpace." >&2
    exit 1
fi

# Run the application using Python 3
exec python3 /usr/share/zerospace/main.py "$@"
