#!/bin/bash
# Quick test for English language
SCRIPT_DIR="$(dirname "$0")"
source "$SCRIPT_DIR/demo.env"
"$SCRIPT_DIR/interactive-test.sh" --phone "$PHONE_NUMBER" --lang en
