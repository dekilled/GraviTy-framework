#!/bin/sh
# Compara, pixel a pixel, os exemplos em .gvt com os originais em C do Gravity.
#
#   cmake -B build && cmake --build build
#   tests/pixels.sh build
#
# Precisa de weston (o backend headless e o weston-screenshooter) e do Pillow (python3 -m pip install pillow).
set -eu

build=${1:-build}
GRAVITY_DIR=${GRAVITY_DIR:-$(cd "$(dirname "$0")/../gravity" && pwd)}
make -s -C "$GRAVITY_DIR" mixer galeria  # os originais em C
tmp=$(mktemp -d)
export XDG_RUNTIME_DIR="$tmp"
export WAYLAND_DISPLAY=gvt-pixels
chmod 700 "$tmp"

weston --backend=headless --renderer=pixman --width=600 --height=800 --socket="$WAYLAND_DISPLAY" \
	--debug --no-config --shell=kiosk --idle-time=0 >"$tmp/weston.log" 2>&1 &
weston_pid=$!
trap 'kill $weston_pid 2>/dev/null; rm -rf "$tmp"' EXIT
sleep 2

shot() {
	(cd "$tmp" && rm -f wayland-screenshot-*.png)
	timeout 4 "$1" >/dev/null 2>&1 &
	sleep 2.5
	(cd "$tmp" && weston-screenshooter >/dev/null 2>&1 && mv wayland-screenshot-*.png "$2")
	wait $! 2>/dev/null || true
}

status=0
for app in mixer galeria; do
	shot "$GRAVITY_DIR/$app" "original-$app.png"
	shot "$build/$app" "gvt-$app.png"
	python3 -W ignore - "$tmp/original-$app.png" "$tmp/gvt-$app.png" "$app" <<'EOF' || status=1
import sys
from PIL import Image, ImageChops
a, b = (Image.open(p).convert("RGB") for p in sys.argv[1:3])
diff = ImageChops.difference(a, b)
n = sum(1 for p in diff.getdata() if max(p) > 16)
print(f"{sys.argv[3]}: {n} pixels diferentes")
sys.exit(1 if n else 0)
EOF
done
exit $status
