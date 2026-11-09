import sys
print("intentional tool failure", file=sys.stderr)
raise SystemExit(7)
