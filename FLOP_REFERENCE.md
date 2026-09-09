# FLOP Network — Complete Reference (Sep 2026)

*Compiled from: flop.finance teaser (Aug 26 draft), yellow paper (in progress), Bitrue/Bydfi/Gate News reports, Hayes' Substack essays, GitHub tools (flop-agent-one-click, flop-labs-simplified-technocore-guide, flop-airdrop-skill)*

---

## TL;DR

FLOP is the **native token of the Flop Network** — a Proof-of-Useful-Inference (PoUI) blockchain where AI agents pay miners in FLOP for actual inference compute. The token is in **testnet phase**, airdrop scheduled **Q4 2026**, genesis block **Q1 2027**.

---

## 1. What FLOP actually is

| Field | Value |
|---|---|
| Token | $FLOP |
| Project | Flop Network |
| Founder | Arthur Hayes (BitMEX co-founder) |
| Concept | "Food for your AI agent" |
| Name origin | Floating-point operations (FLOPs) |
| Type | PoUI + account-based blockchain |
| Fair launch | ✅ Yes — no VC, no presale, no team allocation |
| Token standard | Native |
| Live at | flop.finance / Technocore.chat (testnet faucet) |

**The pitch (paraphrased):** AI agents need a currency to buy compute. FLOP is that currency. Miners run real inference, get paid in FLOP. Verifiable, transparent, decentralized.

---

## 2. Network architecture

### Three roles

| Role | What | Reward |
|---|---|---|
| **Agent** | Posts inference requests (model hash, latency, FLOPs, fee) | Pays FLOP, gets inference back |
| **Miner** | Receives requests, runs them on hardware | 85% of inference fee + share of block reward |
| **Validator** | Verifies work, produces blocks | 10% of block reward + slashing power |

### The verification stack (4 layers)

To prevent faking computation:

| Layer | What | Cost |
|---|---|---|
| 1. **TEE attestation** | Enterprise GPUs with Trusted Execution Environment cryptographically attest the model ran untampered | High (optional HARD tier) |
| 2. **TOPLOC activation commitment** | Compact fingerprint of model activations, sampled verification | Cheap |
| 3. **Independent re-execution** | Validators re-run a random sample of sessions | Random but expensive for cheaters |
| 4. **Staked tokens (slashing)** | Miners stake FLOP proportional to compute offered; 100% slash possible | The deterrent |

### Recommended hardware

| Role | Specs |
|---|---|
| **Miner** | Single GPU or cluster, **16 GB+ VRAM per unit** |
| **Validator** (provisional) | 8+ core CPU, 64 GB RAM, 2 TB NVMe, 1 Gbps redundant connection |

---

## 3. Tokenomics

| Metric | Value |
|---|---|
| Total supply at year 10 | ~17.2 billion FLOP |
| Genesis airdrop | 3.5 billion (20.4% of supply) |
| Miner share (year 10) | ~51% (~8.8 billion) |
| Team + Foundation | 11.4% (~2.0 billion) |
| Block reward (start) | 96 FLOP |
| Halving | every 730 days (2 years) |
| Halvings | 5 then fixed at 3 FLOP |
| Block reward split | 75% miners, 10% validators, 10% agents, 5% stakers |

**Genesis supply was originally announced as 2.48 billion but revised up to 17.2 billion by year 10 with 0.6% annual terminal inflation.** Numbers are draft and may change before mainnet.

---

## 4. Airdrop eligibility — multiple paths

Airdrop weighted by **testnet activity**, ~20% of supply distributed over 10 years.

### Path A: Miner path
- Provide GPU compute during testnet
- Reward proportional to verified compute delivered
- ~25% liquid at TGE, rest released over opening months of mainnet as you continue serving

### Path B: Validator path
- Run a validator node, verify work, produce blocks
- Top 1,000 by uptime/accuracy/latency selected for mainnet
- Airdrop = stake required at launch, locked through first halving, released over 1,000 days

### Path C: Agent path (**your path, easiest**)
- Claim test tokens from faucet (need DID)
- Spend them on inference over the testnet
- Every 3 FLOP spent on inference unlocks 1 FLOP from your airdrop allocation
- Airdrop arrives locked, spendable only on inference or staking — you must USE the network to make it liquid

### Path D: Contributor/Creator path
- Tools, documentation, education content
- Apply via flop.finance/apply/kol

---

## 5. Timeline

| Date | Event |
|---|---|
| 2026-08-18 | Hayes announces FLOP, returns as CEO of Flop Labs |
| 2026-08-26 | Teaser document (draft v0.1) published |
| 2026-09-01 | Technocore.chat launches (chat + notes platform, holds FLOP testnet faucet) |
| 2026-09-07 | Yellow Paper details (PoUI consensus, 4-layer verification) |
| **Q4 2026** | **Testnet launch (~90 days), airdrop distribution** |
| Q1 2027 | Genesis block, mainnet launch, TGE |

---

## 6. How to participate RIGHT NOW (pre-testnet)

The testnet isn't live yet (Q4 2026). What's available NOW:

### Required for any participation
- ✅ DID key (Ed25519, generated locally) — DONE for you
- ✅ DID published to Technocore registry (`/kv/did-...`) — works
- ✅ Signed check-in in lobby — DONE (seq 37801828, 37843407)

### Recommended actions (in priority order)

| Priority | Action | Where |
|---|---|---|
| 1 | Follow @flop_labs and @cryptohayes on X | Hayes: "this is the basic eligibility requirement" |
| 2 | Apply for KOL/Creator role | flop.finance/apply/kol |
| 3 | Apply for Miner role (if you have GPU) | flop.finance/apply/miner |
| 4 | Apply for Validator role (if you have server) | flop.finance/apply/validator |
| 5 | Build tools + contribute to FLOP ecosystem | GitHub, articles, videos |
| 6 | Subscribe to Hayes' Substack | cryptohayes.substack.com |
| 7 | Engage with Technocore.chat | Daily check-ins, useful content in rooms |

### Important caveat from Hayes (Aug 25)
> "test tokens from the faucet will hold no value and will not count toward the exchange weight for mainnet tokens if users do not actively interact with the network"

→ Just claiming test tokens isn't enough. You have to **use** them (spend on inference) during the testnet.

---

## 7. Mining — what we know

### Hardware
- **Min GPU**: 16 GB+ VRAM (single GPU or cluster)
- Examples of qualifying hardware: NVIDIA RTX 4090 (24GB), A5000 (24GB), A100 (40GB+), H100 (80GB)
- For TEE attestation tier: enterprise GPUs like H100/H200/Blackwell

### What mining actually is
- Receive session request from agent (model hash, compute, latency, fee)
- Run inference on your GPU
- Submit proof of computation (TOPLOC fingerprint + work certificate)
- Validators check random sample
- Get paid 85% of inference fee + share of block reward

### Steps to set up (when testnet is live)
1. Stake FLOP tokens (proportional to compute you'll offer)
2. Run Flop Labs miner node software (TBD - not released yet)
3. Configure your hardware specs, accepted models, latency SLAs
4. Connect to the network, start receiving session requests
5. Earn FLOP continuously

### What you should do NOW
- Apply for miner role at flop.finance/apply/miner
- Get GPU hardware (or rent from Colab/RunPod when testnet is live)
- Wait for miner software release (testnet Q4 2026)
- The detailed miner setup guide hasn't been published yet

---

## 8. Validator — what we know

### Specs (provisional)
- 8+ core CPU
- 64 GB RAM
- 2 TB NVMe
- 1 Gbps redundant connection
- Top 1,000 selected by uptime, accuracy, latency
- Bottom 50 rotated monthly

### What you should do NOW
- Apply for validator role at flop.finance/apply/validator
- Get a server (VPS would work — you have one!)
- Wait for validator software release

---

## 9. Your situation specifically

### What you have
| Asset | Status |
|---|---|
| DID key | ✅ did:key:z6MkkM5ALAh52QM3utd46Yxug1BwJLtyTsPNe4xBAXWSb2Lw |
| Signed Technocore check-in | ✅ seq 37801828 (lobby), 37843407 (flop-toolkit announcement) |
| VPS (QXL virtual GPU) | ⚠️ Not mining-capable (0MB VRAM), but possibly validator-capable |
| iPhone | ❌ Not mining-capable |
| GitHub repo (flop-toolkit) | ✅ Live, public |
| BA Linguistics + AI training fit | ✅ Agent pathway is yours |

### Best paths for you
1. **Agent path (Path C)** — claim testnet tokens, spend on inference
2. **Validator path (Path B)** — your VPS meets specs (CPU/RAM/storage), if it gets GPU access
3. **Creator/contributor path (Path D)** — keep building tools, content, docs

### Honest assessment
- **Mining is out for you right now** — QXL virtual GPU is 0MB VRAM, no real compute
- **Validator is possible** — your VPS specs are in the ballpark
- **Agent is your best path** — your whole setup is built for it

---

## 10. Tools built by the community (in case you want to fork/build-on)

| Tool | Repo | What |
|---|---|---|
| Official starter kit | github.com/flop-labs/technocore-chat | DID gen + signed messages |
| One-click installer | github.com/Shahzuby/flop-agent-one-click | Linux VPS auto-setup for all 4 steps |
| Docker guide | github.com/0xkinno/flop-labs-simplified-technocore-guide | No VPS needed, runs in Docker |
| Airdrop skill | github.com/dizcorvus/flop-airdrop-skill | Autonomous agent for the workflow |
| Our contribution | github.com/Rawbeew/flop-toolkit | Scanner, tracker, watcher |

---

## 11. Sources

| URL | Use |
|---|---|
| flop.finance/teaser | Primary tokenomics + testnet details |
| flop.finance/intro/yellowpaper | PoUI verification stack, hardware specs |
| cryptohayes.substack.com | Hayes' essays (most detailed tokenomics) |
| github.com/flop-labs/technocore-chat | Source code |
| technocore.chat | Live test platform |
| Hayes' Aug 25 X post | Confirms testnet activity = airdrop |

---

## 12. Open questions (not yet answered publicly)

- Exact agent activity metric for airdrop weighting
- Daily/weekly contribution required to qualify
- Whether staking-as-agent counts
- Whether non-X platforms (Reddit, Substack) count as much
- Whether we'd need to be a verified entity on Flop Labs' side
- Exact testnet launch date (still "Q4 2026" with no specific date)
- Total token supply (revised between essays: 2.48B → 17.2B by year 10)

---

## Sources last updated
- Sep 8-9, 2026
