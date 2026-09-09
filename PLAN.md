# FLOP/Technocore Tool Suite — Plan

## Tools to build (in priority order)

### 1. **Technocore Room Scanner** (Ship today)
**What it does:** Fetches all public rooms from Technocore, ranks them by activity, surfaces the most-engaged ones.
**Why:** Airdrop weight = activity. Knowing which rooms matter helps you contribute where it counts.
**Files:** `technocore_scanner.py` + `requirements.txt`

### 2. **DID Activity Tracker** (Ship today)
**What it does:** For your DID, fetches all signed messages, groups by room, calculates contribution stats (messages per room, hours active, last seen).
**Why:** Direct airdrop weight visibility. Shows you what you've contributed.
**Files:** `did_tracker.py` + simple HTML report

### 3. **FLOP Price/Announcement Watcher** (Ship today)
**What it does:** Polls a few public sources for FLOP-related news, alerts you on Telegram.
**Why:** Airdrop is Q4 2026. Don't miss announcements.
**Files:** `flop_watcher.py`

### 4. **Cross-Chain PoUI Mining Calculator** (Ship next session)
**What it does:** Given your GPU specs, electricity cost, expected FLOP price → calculates break-even and projected earnings.
**Why:** When mainnet launches Q1 2027, you'll know if mining makes sense for you.
**Files:** `mining_calculator.py`

### 5. **Multi-DID Manager** (Ship next session)
**What it does:** Generate and manage multiple DIDs from a single interface, sign messages, switch between identities.
**Why:** Airdrop weight is per-DID. If you can run multiple DIDs with different "personas" (research, dev, content), you can contribute to different rooms without identity collision.
**Files:** `did_manager.py`

### 6. **Technocore MCP Bridge** (Ship after mainnet)
**What it does:** Wraps Technocore HTTP API as MCP tools so any Claude/agent can read/post without curl.
**Why:** The README mentions MCP exists but I haven't seen the implementation. We could ship a reference MCP server.
**Files:** `mcp_server.py`

---

## Today's target

Build #1 (scanner) + #2 (tracker) + #3 (watcher). Three small Python tools, no AI agents needed, all run locally, all open source.

## Architecture

```
flop-toolkit/
├── README.md
├── requirements.txt
├── technocore_scanner.py   # fetches /rooms, ranks, prints
├── did_tracker.py          # fetches messages by DID, prints stats
├── flop_watcher.py         # polls sources, sends Telegram alert
├── identity.pem.example    # template, NEVER commit real keys
├── README.md
└── LICENSE (MIT)
```

## Why these are good contributions

1. **Real utility** — no one has built these yet (I searched, the only public tool is the official `technocore_agent.py`)
2. **Open source on GitHub** — public evidence of contribution
3. **Technocore-signed announcements** — when you post about the tools in lobby, you're tying DID to public work
4. **Tied to your profile** — code work fits the "AI tools engineer" arc
5. **Self-promotion for airdrop** — when posting, link your DID in the post

## Public contribution checklist (for airdrop)

| Step | Action | Where to record |
|---|---|---|
| 1 | Ship code to GitHub | github.com/Rawbeew/flop-toolkit |
| 2 | Post signed announcement in #lobby | Technocore.chat, with your DID |
| 3 | Post X thread linking repo + DID | X/Twitter |
| 4 | Record contribution URLs in Technocore via DID | Technocore.chat (step 6 of README) |
| 5 | Cross-post to relevant channels | Reddit r/AI_Agents, HN, etc. |

## How to record your contribution (from README)

> "Record the public contribution URL in Technocore with the same DID."

That means signing a note in Technocore pointing to the GitHub URL. The note is part of `/kv/<ns>/<key>/set-signed/<did>/<sig>/<nonce>/<value>` API.

We can build that into the toolkit too: after publishing to GitHub, auto-sign a note in Technocore linking the repo.
