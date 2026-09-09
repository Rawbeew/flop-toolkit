"""
FLOP Announcement Watcher
Polls public sources for FLOP-related news and airdrop announcements.
Alerts you via Telegram when something new is found.

Usage:
    python flop_watcher.py --check          # one-shot check
    python flop_watcher.py --loop 600      # poll every 600 seconds
    python flop_watcher.py --seen-file seen.json
"""
import urllib.request
import urllib.error
import json
import sys
import argparse
import time
import re
from datetime import datetime, timezone
from pathlib import Path

# Public sources to watch for FLOP/Technocore news
SOURCES = [
    {
        "name": "technocore-events",
        "url": "https://technocore.chat/r/events",
        "type": "text",
    },
    {
        "name": "arthur-hayes-substack",
        "url": "https://arthurhayes.substack.com/",
        "type": "html",
        "keywords": ["flop", "technocore", "ai agent", "inference", "airdrop"],
    },
    {
        "name": "flop-labs-x",
        "url": "https://nitter.net/FlopLabs/rss",
        "type": "rss",
        "fallback_url": "https://nitter.privacydev.net/FlopLabs/rss",
        "keywords": ["flop", "technocore", "airdrop", "mainnet"],
    },
    {
        "name": "arthur-hayes-x",
        "url": "https://nitter.net/cryptohayes/rss",
        "type": "rss",
        "fallback_url": "https://nitter.privacydev.net/cryptohayes/rss",
        "keywords": ["flop", "technocore", "ai", "inference", "airdrop"],
    },
]


def fetch_url(url, timeout=15):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "flop-toolkit/1.0 (+https://github.com/Rawbeew/flop-toolkit)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return 0, str(e)


def extract_fresh_items(source, body, keywords, seen_keys):
    items = []
    if source["type"] == "text":
        # One item per non-empty line that mentions a keyword
        for line in body.splitlines():
            line = line.strip()
            if not line or len(line) < 5:
                continue
            if keywords and not any(k.lower() in line.lower() for k in keywords):
                continue
            key = f"{source['name']}:{line[:80]}"
            if key not in seen_keys:
                items.append({"source": source["name"], "key": key, "text": line[:300]})
    elif source["type"] == "rss":
        # Parse RSS items
        for match in re.finditer(r"<item>(.*?)</item>", body, re.DOTALL):
            item_xml = match.group(1)
            title_m = re.search(r"<title>(.*?)</title>", item_xml, re.DOTALL)
            link_m = re.search(r"<link>(.*?)</link>", item_xml)
            desc_m = re.search(r"<description>(.*?)</description>", item_xml, re.DOTALL)
            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""
            link = link_m.group(1).strip() if link_m else ""
            desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip() if desc_m else ""
            full = f"{title} {desc}"
            if keywords and not any(k.lower() in full.lower() for k in keywords):
                continue
            key = f"{source['name']}:{link or title[:80]}"
            if key not in seen_keys:
                items.append({
                    "source": source["name"],
                    "key": key,
                    "title": title,
                    "link": link,
                    "text": desc[:300],
                })
    elif source["type"] == "html":
        for line in re.split(r"<[^>]+>", body):
            line = line.strip()
            if len(line) < 30:
                continue
            if keywords and not any(k.lower() in line.lower() for k in keywords):
                continue
            key = f"{source['name']}:{line[:80]}"
            if key not in seen_keys:
                items.append({"source": source["name"], "key": key, "text": line[:300]})
    return items


def load_seen(path):
    if Path(path).exists():
        try:
            return set(json.loads(Path(path).read_text()))
        except Exception:
            return set()
    return set()


def save_seen(path, seen):
    Path(path).write_text(json.dumps(sorted(seen), indent=2))


def send_telegram(message, bot_token, chat_id):
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Watch for FLOP/Technocore announcements")
    parser.add_argument("--check", action="store_true", help="One-shot check")
    parser.add_argument("--loop", type=int, help="Loop every N seconds")
    parser.add_argument("--seen-file", default=".flop_seen.json", help="Where to persist seen items")
    parser.add_argument("--telegram-token", help="Telegram bot token (or set FLOP_BOT_TOKEN env)")
    parser.add_argument("--telegram-chat", help="Telegram chat ID (or set FLOP_CHAT_ID env)")
    args = parser.parse_args()

    if not args.check and not args.loop:
        parser.print_help()
        return

    seen = load_seen(args.seen_file)
    bot_token = args.telegram_token or ""
    chat_id = args.telegram_chat or ""

    def do_check():
        new_items = []
        for src in SOURCES:
            urls_to_try = [src["url"]]
            if "fallback_url" in src:
                urls_to_try.append(src["fallback_url"])
            body, status = "", 0
            for u in urls_to_try:
                status, body = fetch_url(u)
                if status == 200:
                    break
            if status != 200:
                print(f"  [{src['name']}] failed: HTTP {status}")
                continue
            items = extract_fresh_items(src, body, src.get("keywords", []), seen)
            for it in items:
                seen.add(it["key"])
                new_items.append(it)
        return new_items

    if args.check:
        items = do_check()
        if not items:
            print("No new items found.")
        for it in items:
            print(f"\n--- [{it['source']}] ---")
            print(it.get("text") or it.get("title", ""))
            if it.get("link"):
                print(f"Link: {it['link']}")
        save_seen(args.seen_file, seen)
        return

    if args.loop:
        print(f"Watching FLOP/Technocore sources every {args.loop}s. Ctrl+C to stop.")
        while True:
            try:
                items = do_check()
                if items:
                    for it in items:
                        msg = f"*[{it['source']}]* FLOP/Technocore update\n\n{it.get('title', '')}\n{it.get('text', '')}\n{it.get('link', '')}"
                        if bot_token and chat_id:
                            send_telegram(msg, bot_token, chat_id)
                        else:
                            print(f"\n--- [{it['source']}] ---")
                            print(msg)
                save_seen(args.seen_file, seen)
            except KeyboardInterrupt:
                print("\nStopped.")
                break
            except Exception as e:
                print(f"  Error: {e}")
            time.sleep(args.loop)


if __name__ == "__main__":
    main()
