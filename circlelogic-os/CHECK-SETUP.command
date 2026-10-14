#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 launcher.py check
result=$?
printf '\nPress Enter to close...'
read -r answer
exit "$result"
