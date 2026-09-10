#!/usr/bin/env bash
# Mux the rendered picture with the synthesised bed, then cut the short version.
set -euo pipefail
FF="${FF:?}"; B="$(cd "$(dirname "$0")" && pwd)"; OUT="${OUT:-$B/out}"
mkdir -p "$OUT"

# 1. full 75 s reel, loudness-normalised for social platforms (-14 LUFS)
"$FF" -y -loglevel error -i "$B/video_silent.mp4" -i "$B/music.wav" \
  -filter:a "loudnorm=I=-14:TP=-1.0:LRA=11" \
  -c:v copy -c:a aac -b:a 320k -ar 44100 -ac 2 -shortest \
  -movflags +faststart "$OUT/campus-drive-reel-75s.mp4"

# 2. 30 s WhatsApp cut: hook -> college -> date -> salary -> package -> CTA.
#    Picture is cut from the reel; the bed is laid down continuously underneath
#    so the music does not jump at every splice.
SEGS=(0.0:4.6 6.0:5.0 12.0:3.6 28.0:6.6 59.6:3.4 68.0:7.0)
i=0; SHORT=0; : > "$B/concat.txt"
for s in "${SEGS[@]}"; do
  st="${s%%:*}"; du="${s##*:}"
  "$FF" -y -loglevel error -ss "$st" -t "$du" -i "$B/video_silent.mp4" \
    -an -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p "$B/seg$i.mp4"
  echo "file 'seg$i.mp4'" >> "$B/concat.txt"
  SHORT=$(echo "$SHORT + $du" | bc); i=$((i+1))
done
"$FF" -y -loglevel error -f concat -safe 0 -i "$B/concat.txt" -an \
  -c:v copy "$B/short_silent.mp4"
"$FF" -y -loglevel error -i "$B/short_silent.mp4" -i "$B/music.wav" \
  -filter:a "atrim=0:${SHORT},afade=t=out:st=$(echo "$SHORT-1.2"|bc):d=1.2,loudnorm=I=-14:TP=-1.0:LRA=11" \
  -c:v copy -c:a aac -b:a 320k -ar 44100 -ac 2 -shortest \
  -movflags +faststart "$OUT/campus-drive-whatsapp-30s.mp4"
rm -f "$B"/seg*.mp4 "$B/concat.txt" "$B/short_silent.mp4"

# 3. cover still for the Reels / Shorts thumbnail
"$FF" -y -loglevel error -ss 70.6 -i "$OUT/campus-drive-reel-75s.mp4" \
  -frames:v 1 "$OUT/thumbnail-1080x1920.png"

for f in "$OUT"/*; do printf '%-42s %7.2f MB\n' "$(basename "$f")" "$(echo "scale=2;$(stat -c%s "$f")/1048576"|bc)"; done
