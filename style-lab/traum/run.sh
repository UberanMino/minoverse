#!/bin/bash
# run.sh <seg> [test f1 f2 ...]
cd /home/claude/dream
exec /home/claude/bpyvenv/bin/python -c "import sys,runpy;sys.argv=['dream.py','--']+sys.argv[1:];runpy.run_path('dream.py',run_name='__main__')" "$@"
