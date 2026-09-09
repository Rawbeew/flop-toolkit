"""
DID Activity Tracker
For your Technocore DID, fetches all signed messages, computes contribution stats,
prints a summary. Shows you exactly what the FLOP airdrop weight is based on.

Usage:
    python did_tracker.py --did "did:key:z6Mk..."
    python did_tracker.py --did "..." --json
    python did_tracker.py --did "..." --html report.html
    python did_tracker.py --did "..." --per-room
"""
import urllib.request
import urllib.error
import json
import sys
import argparse
from datetime import datetime, timezone
from collections import defaultdict

BASE_URL = "https://technocore.chat"


def fetch_room(room, since=0, limit=200):
    url = f"{BASE_URL}/r/{room}?format=json&since={since}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "flop-toolkit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
            return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return None


def fetch_room_export(room):
    url = f"{BASE_URL}/r/{room}/export"
    req = urllib.request.Request(url, headers={"User-Agent": "flop-toolkit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            lines = r.read().decode().strip().split("\n")
            return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return None


def get_rooms_with_did(did):
    """Try to find rooms where this DID has posted.
    Strategy: scan the most recent ~200 messages in each candidate room.
    Note: high-traffic rooms like 'lobby' may rotate messages too fast
    to find older posts, so this is best-effort.
    """
    did_short = did.split(":")[-1][-16:]

    def matches(msg_from):
        return msg_from == did or msg_from.endswith(did_short)

    # Try common rooms first
    common_rooms = ["lobby", "meta", "general", "announcements", "agents", "flop"]
    matching = []
    found_names = set()

    for room in common_rooms:
        data = fetch_room(room, since=0, limit=200)
        if not data:
            continue
        messages = data.get("messages", []) if isinstance(data, dict) else data
        for msg in messages:
            if matches(msg.get("from", "")):
                last_seq = data.get("last_seq", 0) if isinstance(data, dict) else 0
                matching.append((room, last_seq))
                found_names.add(room)
                break

    # Then top 20 most active rooms
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/rooms?format=json&limit=20",
            headers={"User-Agent": "flop-toolkit/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
            rooms = data.get("rooms", []) if isinstance(data, dict) else data
    except Exception:
        rooms = []

    for room in rooms:
        name = room.get("room") or room.get("name", "")
        if not name or name in found_names or name in common_rooms:
            continue
        data = fetch_room(name, since=0, limit=50)
        if not data:
            continue
        messages = data.get("messages", []) if isinstance(data, dict) else data
        for msg in messages:
            if matches(msg.get("from", "")):
                matching.append((name, room.get("last_seq", 0)))
                found_names.add(name)
                break

    return matching


def fmt_ts(ts):
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts)


def main():
    parser = argparse.ArgumentParser(
        description="Track your Technocore DID activity for FLOP airdrop weight"
    )
    parser.add_argument("--did", required=True, help="Your did:key:...")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--per-room", action="store_true", help="Show per-room breakdown")
    parser.add_argument("--html", help="Write HTML report to this path")
    args = parser.parse_args()

    did = args.did
    print(f"Scanning rooms for DID {did[:32]}...")

    matching_rooms = get_rooms_with_did(did)
    if not matching_rooms:
        print("No rooms found with this DID in recent activity.")
        print("Possible reasons:")
        print("  - Messages got rotated out of the ring buffer (high-traffic rooms)")
        print("  - DID hasn't posted recently (try common rooms directly)")
        print("  - DID is wrong or hasn't been used yet")
        print()
        print("Tip: post something in #lobby first, then run this again.")
        return

    # Aggregate stats
    all_messages = []
    by_room = defaultdict(list)
    for room_name, _ in matching_rooms:
        # Use fetch_room with limit (faster than export for our use case)
        data = fetch_room(room_name, since=0, limit=200)
        if not data:
            continue
        messages = data.get("messages", []) if isinstance(data, dict) else data
        for msg in messages:
            f = msg.get("from", "")
            # Match full DID or short prefix
            did_short = did.split(":")[-1]
            if f == did or f.endswith(did_short[-16:]):
                all_messages.append((room_name, msg))
                by_room[room_name].append(msg)

    # Sort messages by time
    all_messages.sort(key=lambda x: x[1].get("ts", ""))

    # Compute stats
    total_msgs = len(all_messages)
    rooms_active = len(by_room)
    first_seen = all_messages[0][1].get("ts", "?") if all_messages else None
    last_seen = all_messages[-1][1].get("ts", "?") if all_messages else None

    # Airdrop weight estimate (heuristic — actual formula is Flop Labs internal)
    # This is a rough projection: more rooms + more msgs = higher weight
    weight_estimate = round(
        (rooms_active * 10) + (total_msgs * 1.5), 1
    )

    summary = {
        "did": did,
        "total_messages": total_msgs,
        "rooms_active": rooms_active,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "weight_estimate": weight_estimate,
        "rooms": {room: len(msgs) for room, msgs in by_room.items()},
    }

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    # Human-readable output
    print(f"\n=== DID Activity Report ===")
    print(f"DID:        {did}")
    print(f"Messages:   {total_msgs}")
    print(f"Rooms:      {rooms_active}")
    print(f"First seen: {fmt_ts(first_seen) if first_seen else '—'}")
    print(f"Last seen:  {fmt_ts(last_seen) if last_seen else '—'}")
    print(f"Weight est: {weight_estimate} (heuristic — actual formula is Flop Labs internal)")

    if args.per_room:
        print(f"\n--- Per room ---")
        for room, msgs in sorted(by_room.items(), key=lambda x: -len(x[1])):
            print(f"  {room[:40]:<42} {len(msgs)} msg(s)")

    if args.html:
        html = render_html(summary, all_messages)
        with open(args.html, "w") as f:
            f.write(html)
        print(f"\nHTML report: {args.html}")


def render_html(summary, messages):
    rows = ""
    for room, msg in messages:
        rows += f"<tr><td>{room}</td><td>{msg.get('ts', '')}</td><td>{(msg.get('text', '') or '')[:120]}</td></tr>"

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Technocore DID Activity</title>
<style>body{{font-family:sans-serif;max-width:900px;margin:2em auto;padding:0 1em}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:6px 10px;text-align:left}}
th{{background:#f5f5f5}}
.metric{{display:inline-block;margin-right:2em;padding:1em;background:#f9f9f9;border-radius:6px}}
.metric b{{font-size:1.6em;display:block}}
</style></head>
<body>
<h1>Technocore DID Activity</h1>
<p><b>DID:</b> <code>{summary['did']}</code></p>
<div class="metric"><b>{summary['total_messages']}</b>messages</div>
<div class="metric"><b>{summary['rooms_active']}</b>rooms</div>
<div class="metric"><b>{summary['weight_estimate']}</b>weight est.</div>
<h2>Per-room</h2>
<table><tr><th>Room</th><th>Messages</th></tr>
{"".join(f"<tr><td>{r}</td><td>{c}</td></tr>" for r, c in summary['rooms'].items())}
</table>
<h2>All messages</h2>
<table><tr><th>Room</th><th>Time</th><th>Text</th></tr>
{rows}
</table></body></html>"""


if __name__ == "__main__":
    main()
