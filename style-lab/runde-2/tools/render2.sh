#!/bin/bash
# render2.sh NN → mp4_2/NN-name.mp4
S=/tmp/claude-0/-home-claude-minoverse/d0b0dcbb-1da6-5514-bbe7-67ef6d35f634/scratchpad
mkdir -p $S/mp4_2 $S/rp2
for id in "$@"; do
  f=$(ls $S/build2/clips/$id-*.html | head -1); name=$(basename $f .html)
  P=$S/rp2/$id; rm -rf $P; mkdir -p $P/audio
  cp $f $P/index.html; cp -r $S/build2/clips/lib $S/build2/clips/fonts $P/
  cp $S/build2/clips/audio/$id.mp3 $S/build2/clips/audio/vo_$id.js $P/audio/
  (cd $P && npx --prefix $S/hf hyperframes lint . 2>&1 | tail -3; HYPERFRAMES_NO_TELEMETRY=1 $S/hf/node_modules/.bin/hyperframes render . -o $S/mp4_2/$name.mp4 2>&1 | grep -E "rendered in|rror|warn" )
done
