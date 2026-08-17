#!/bin/bash
# mc — 가상환경 자동 활성화 후 실행
source /Users/twinssn/projects2/mc/.venv/bin/activate
exec python -m cli.mc "$@"
