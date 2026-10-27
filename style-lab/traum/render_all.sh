#!/bin/bash
cd /home/claude/dream
for s in 1 2 3 4 5 6 7 8 9; do
  start=$(date +%s)
  ./run.sh $s > log_s$s.txt 2>&1
  echo "seg $s: $(( $(date +%s) - start )) s, $(ls frames/s$s | wc -l) Bilder" >> render_times.txt
done
echo DONE >> render_times.txt
