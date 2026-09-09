"""
Technocore Room Scanner
Fetches all public rooms, ranks by activity, surfaces what's worth contributing to.

Usage:
    python technocore_scanner.py
    python technocore_scanner.py --top 20
    python technocore_scanner.py --json
    python technocore_scanner.py --export rooms.json
"""
import urllib.request
import urllib.error
import json
import sys
import time
from datetime import datetime, timezone

BASE_URL = "https://technocore.chat"
TIMEOUT = 15


def fetch_json(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "flop-toolkit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return 0, str(e)


def fetch_rooms(limit=200):
    status, body = fetch_json(f"/rooms?format=json&limit={limit}")
    if status != 200:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


def score_room(r):
    """Higher score = more worth contributing to for airdrop weight."""
    last_seq = r.get("last_seq", 0) or 0
    size = r.get("bytes", 0) or 0
    idle = r.get("idle_seconds", 0) or 0
    topic = (r.get("topic") or "").strip()
    name = r.get("room") or r.get("name", "")
    room_class = name.split("-")[0] if "-" in name else "public"
    engagement = r.get("engagement", {}) or {}
    nick_diversity = engagement.get("nick_diversity") or 0
    zero_response = engagement.get("zero_response_share") or 0

    score = 0
    # Recency dominates — fresh rooms get airdrop weight
    if idle < 3600:
        score += 100
    elif idle < 86400:
        score += 50
    elif idle < 604800:
        score += 10
    # Activity volume
    score += min(last_seq / 10, 50)
    # Diversity — many distinct voices = good signal
    if nick_diversity and nick_diversity > 0.5:
        score += 30
    elif nick_diversity and nick_diversity > 0.2:
        score += 15
    # Penalize dead conversations
    if zero_response and zero_response > 0.8:
        score -= 20
    # Bonus for "p-", "d-", "mb-" because those are ownable/contribute-able
    if room_class in ("p", "mb", "d", "e"):
        score += 5
    return round(score, 1)


def fmt_idle(secs):
    if secs < 60:
        return f"{int(secs)}s"
    if secs < 3600:
        return f"{int(secs//60)}m"
    if secs < 86400:
        return f"{int(secs//3600)}h"
    return f"{int(secs//86400)}d"


def print_table(rooms, top):
    print(f"\n{'#':<4} {'Room':<32} {'Class':<6} {'Msgs':<6} {'Idle':<8} {'Diversity':<10} {'Score':<7}")
    print("-" * 90)
    for i, r in enumerate(rooms[:top], 1):
        name = r.get("room") or r.get("name", "?")
        room_class = name.split("-")[0] if "-" in name else "public"
        last_seq = r.get("last_seq", 0) or 0
        idle = r.get("idle_seconds", 0) or 0
        eng = r.get("engagement", {}) or {}
        diversity = eng.get("nick_diversity")
        diversity_str = f"{diversity:.2f}" if isinstance(diversity, (int, float)) else "—"
        score = score_room(r)
        print(f"{i:<4} {name[:30]:<32} {room_class:<6} {last_seq:<6} {fmt_idle(idle):<8} {diversity_str:<10} {score:<7}")


def main():
    args = sys.argv[1:]
    top = 20
    json_out = False
    export_path = None
    for i, a in enumerate(args):
        if a == "--top" and i + 1 < len(args):
            top = int(args[i + 1])
        elif a == "--json":
            json_out = True
        elif a == "--export" and i + 1 < len(args):
            export_path = args[i + 1]
        elif a == "--help":
            print(__doc__)
            return

    print(f"Fetching rooms from {BASE_URL}...")
    data = fetch_rooms(limit=200)
    if data is None:
        print("Failed to fetch rooms. Check the API status or your network.")
        return

    rooms = data.get("rooms", []) if isinstance(data, dict) else data
    rooms_with_scores = [(r, score_room(r)) for r in rooms]
    rooms_with_scores.sort(key=lambda x: x[1], reverse=True)

    if export_path:
        with open(export_path, "w") as f:
            json.dump([{"room": r, "score": s} for r, s in rooms_with_scores], f, indent=2)
        print(f"Exported {len(rooms_with_scores)} rooms to {export_path}")
        return

    if json_out:
        print(json.dumps([{"room": r, "score": s} for r, s in rooms_with_scores[:top]], indent=2))
        return

    print(f"Found {len(rooms)} public rooms.\n")
    # Unpack tuples for print_table
    rooms_only = [r for r, _ in rooms_with_scores]
    print_table(rooms_only, top)

    print(f"\nTip: contribute to rooms with score > 100 to maximize airdrop weight.")
    print(f"     Use --top N to see more, --export to save JSON, --json for raw output.")


if __name__ == "__main__":
    main()
