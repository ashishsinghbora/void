# ⚡ Void: Autonomous Edge Agent Platform (Android / Termux)

<div align="center">

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Android%20(Termux)%20%7C%20Linux-cyan.svg)](https://termux.dev)
[![Memory RSS](https://img.shields.io/badge/RAM%20RSS-%3C%2030MB%20(Verified)-emerald.svg)](#-memory-benchmarks--efficiency)
[![Tests](https://img.shields.io/badge/tests-102%2F102%20passed%20(100%25)-green.svg)](#-automated-testing--verification)
[![Control](https://img.shields.io/badge/control-75--Button%20Telegram%20UI%20%2B%20Mobile%20TUI-purple.svg)](#-75-button-nested-telegram-ui-hierarchy)

**Void** is a hyper-minimalist, terminal-and-Telegram-native autonomous Android orchestrator engineered for mobile edge computing. Inspired by ultra-lightweight agent frameworks (like OpenClaw), Void eliminates all heavy web server bloat (zero Flask, zero WSGI, zero HTML/SSE overhead), starting with **zero default extensions** and running as an ultra-lean local daemon controlled exclusively through an interactive rich TUI and an interactive Telegram Bot interface.

[One-Line Install](#-one-line-zero-friction-installer) • [Directory Blueprint](#-refactored-directory-blueprint) • [F-Droid Setup](#-f-droid-prerequisites-termux--termuxapi) • [Telegram Bot Setup](#-frictionless-telegram-bot-setup-wizard) • [CLI Commands & Rich TUI](#-unified-cli--rich-tui) • [Dynamic Plugin Store](#-on-demand-dynamic-plugin-store) • [Local LLM Bootstrapper](#-autonomous-local-model-bootstrapper) • [Troubleshooting](#-android-permissions--troubleshooting)

</div>

---

## 🚀 One-Line Zero-Friction Installer

Deploy Void directly into your Termux or Linux environment in seconds:

```bash
curl -sSL https://raw.githubusercontent.com/ashishsinghbora/void/main/install.sh | bash
```

> [!TIP]
> To update or reinstall to the latest clean build on Termux:
> ```bash
> rm -rf ~/void && curl -sSL https://raw.githubusercontent.com/ashishsinghbora/void/main/install.sh | bash
> ```

---

## 📂 Refactored Directory Blueprint

Void's architecture enforces strict separation of concerns, zero pre-bundled extension bloat, and low-memory data structures:

```text
void/
├── bin/
│   └── void                    # Unified CLI command dispatcher (cli, fastfetch, plugins, setup-bot)
├── core/
│   ├── agent_engine.py         # Advanced agent engine with bounded ReAct state loops
│   ├── bot_setup.py            # Frictionless Telegram setup wizard & Admin ID auto-detection
│   ├── command_executor.py     # Secure argument-vector subprocess executor with Termux IPC
│   ├── event_bus.py            # Pub/sub event streaming bus
│   ├── fastfetch.py            # ASCII & Unicode FastFetch telemetry collector
│   ├── lru_cache.py            # Bounded LRU query cache (O(1) lookups)
│   ├── model_manager.py        # Small-model bootstrapper (SmolLM, Needle, Qwen GGUF)
│   └── types.py                # Strongly-typed ReAct dataclasses with __slots__
├── agents/
│   ├── react_agent.py          # Autonomous ReAct loop with heuristic fallback router
│   ├── prompt_processor.py     # Natural language tokenizer & intent preprocessor
│   └── fallback_handler.py     # Hardware error recovery & alternative tool suggestion
├── extensions/
│   ├── base.py                 # Abstract ExtensionPlugin base class
│   └── manager.py              # Dynamic on-demand plugin downloader & AST verification
├── security/
│   ├── sanitizer.py            # Strict argument & query sanitization
│   ├── credential_vault.py     # AES-256 encrypted credential vault
│   ├── rate_limiter.py         # Token-bucket rate limiter & session manager
│   └── permissions.py          # Android permission governance & privacy audit
├── storage/
│   ├── sqlite_db.py            # Thread-safe SQLite wrapper with Write-Ahead Logging (WAL)
│   ├── repository.py           # Repositories for conversations, logs, telemetry
│   └── log_pruner.py           # Sliding-window log pruner (guarantees DB < 5MB)
├── telegram/
│   ├── bot_app.py              # Master supervisor for bot polling & Mini App HTTP daemon
│   ├── bot_controller.py       # Authenticated Telegram bot control plane & keyboard layouts
│   ├── database/               # SQLite WAL models & thread-safe data access layer
│   │   ├── models.py           # Dataclasses: User, Device, Subscription, Payment, Settings
│   │   └── db_manager.py       # Connection pooling, atomic migrations & CRUD operations
│   ├── middleware/             # Role-based access control & rate limiting
│   │   ├── auth.py             # Whitelist enforcement & tier-based feature gating
│   │   └── rate_limit.py       # Dynamic tiered token-bucket rate limiter
│   ├── services/               # Cryptographic & business logic services
│   │   ├── tma_auth_service.py # HMAC-SHA256 Telegram Mini App initData validation
│   │   ├── payment_service.py  # Telegram Stars (XTR) & fiat invoice generation/fulfillment
│   │   └── device_service.py   # Multi-device registry & remote tool dispatcher
│   ├── handlers/               # Modular bot command & callback routing
│   │   ├── core_handlers.py    # /start, /status, /devices, /fastfetch, agent router
│   │   ├── billing_handlers.py # /billing, Stars invoices, pre-checkout & fulfillment
│   │   ├── settings_handlers.py# /settings & in-chat preference toggles
│   │   └── callback_handlers.py# Unified inline button dispatcher
│   └── webapp/                 # High-performance Telegram Mini App (TMA)
│       ├── index.html          # Cyber-dark HTML5/Tailwind responsive touch GUI
│       └── server.py           # Zero-dependency standard library micro HTTP daemon
├── tools/
│   ├── base.py                 # Strategy pattern base class
│   ├── hardware.py             # Battery, torch, vibration, volume, display
│   ├── telephony.py            # SMS send/receive, call, contacts, call log
│   ├── media.py                # Camera photo capture, text-to-speech, audio
│   ├── system.py               # Toasts, notifications, clipboard, GPS, wifi, native storage clean
│   ├── social_apps.py          # WhatsApp deep-links, Telegram chats, Instagram/LinkedIn/GitHub
│   └── registry.py             # Hash-indexed strategy pattern tool registry
├── app.py                      # Lean daemon supervisor & Telegram bot launcher
├── install.sh                  # One-line zero-friction bootstrap installer
├── requirements.txt            # Minimal dependencies: pyTelegramBotAPI, requests, pytest
└── termux_void.py              # Immersive rich TUI with ANSI colors & live spinners
```

---

## 📱 F-Droid Prerequisites (Termux + Termux:API)

For complete Android hardware integration, install Termux and the companion API from **F-Droid** (do **NOT** use Google Play Store):

1. **Install Termux from F-Droid:**
   - Download: [F-Droid Termux](https://f-droid.org/packages/com.termux/)
2. **Install Termux:API from F-Droid:**
   - Download: [F-Droid Termux:API](https://f-droid.org/packages/com.termux.api/)
3. **Initialize the Companion App (Important):**
   - Open the **Termux:API** app from your Android app drawer **at least once** so Android wakes up the IPC service.
   - Go to Android **Settings -> Apps -> Termux:API -> Permissions** and grant desired permissions (Camera, Storage, SMS, Location). All permissions are 100% optional; Void gracefully falls back to simulation mode if ungranted.

---

## 🤖 Frictionless Telegram Bot Setup Wizard

Void eliminates the hassle of configuring Telegram bots and finding your numeric User ID:

```bash
void setup-bot
```

### What the wizard automates:
1. **Token Validation:** Verifies token format and calls Telegram's `getMe` API to confirm bot identity.
2. **Instant Admin ID Auto-Detection:**
   - Prompts you to open your bot on Telegram and send any message (or tap `/start`).
   - Listens to incoming updates and automatically extracts your Telegram User ID and username.
   - Whitelists your ID instantly so nobody else can control your phone.
3. **Confirmation Ping:** Sends an instant verification greeting directly to your Telegram chat.
4. **Secure Persistence:** Saves credentials to `~/.void/config.env` with `0600` permissions (readable strictly by you).

---

## 🌐 Telegram Bot & Mini App (TMA) Ecosystem

Void includes a production-grade Telegram Bot control plane and embedded HTML5/Tailwind **Telegram Mini App (TMA)** designed for zero-latency remote management.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                     TELEGRAM USER / WEBAPP CLIENT                       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │  (HTTPS / TMA initData)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               VOID LIGHTWEIGHT TMA MICRO SERVER (PORT 8080)             │
│   • HMAC-SHA256 initData Auth      • FastFetch / Telemetry JSON API     │
│   • Multi-Device Registry Bridge   • Telegram Stars Invoice Generator   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 VOID CONTROL PLANE & RE-ACT AGENT ENGINE                │
│   • SQLite WAL Persistence         • Tiered Token-Bucket Rate Limiter   │
│   • Dynamic Plugin Store Loader    • Termux Android Hardware Strategy   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. Telegram Mini App (TMA)
The TMA provides a glassmorphic Cyber-Dark dashboard embedded directly into Telegram chats:
- **Instant Hardware Gauges:** Live battery percentage, charging state, CPU/RAM usage (<30MB target), and active edge node selector.
- **Touch Hardware Matrix:** Single-tap triggers for Flashlight, Camera Photo Snap, and Storage Cache Purge.
- **Cryptographic HMAC-SHA256 Auth:** Implements Telegram's official specification:
  $$\text{secret\_key} = \text{HMAC-SHA256}(\text{"WebAppData"}, \text{bot\_token})$$
  $$\text{expected\_hash} = \text{HMAC-SHA256}(\text{secret\_key}, \text{data\_check\_string})$$
  Rejects tampered requests or expired payloads ($>86400\text{s}$) with constant-time hash comparison.
- **Zero-Dependency Micro HTTP Daemon:** Runs in a background thread using Python's standard `http.server` with negligible memory overhead (< 2MB RAM).

### 2. Global Monetization & Telegram Stars (`currency="XTR"`)
Void natively integrates the Telegram Stars API for frictionless in-app purchases:

| Tier | Stars Price | Fiat Equivalent | Device Limit | Rate Limit | Unlocked Capabilities |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Starter (Free)** | **0 ⭐** | Free Forever | 1 Node | 12 req/min | Heuristic ReAct engine, Termux API controls |
| **Pro Node** | **250 ⭐** | ~$9.99 / mo | Up to 3 Nodes | 60 req/min | SmolLM/Qwen local models, cloud bridge, camera stream |
| **Enterprise** | **1000 ⭐** | ~$39.99 / mo | Unlimited | 300 req/min | Autonomous multi-device cluster, priority SLA, custom tools |

- **Commands:** Use `/billing` to inspect your active subscription, days remaining, and purchase upgrades.
- **Pre-Checkout & Fulfillment:** Validates payload signatures with `pre_checkout_query` and atomically provisions subscriptions upon `successful_payment`.

### 3. In-Chat Settings & Multi-Device Control
- `/devices`: List all registered Android nodes, battery levels, models, and online heartbeats.
- `/settings`: Interactive inline toggles for **Push Notifications**, **OTP SMS Interception**, **Quiet Hours**, and **Security Hardening** (Standard / High / Strict).

---

## ⚡ Mobile-Optimized Rich TUI

Launch Void's mobile-adaptive Terminal User Interface (TUI):

```bash
void
# or explicitly:
void cli
```

### 📱 Mobile-First Design & Architecture:
- **Responsive Viewport Adaptation:** Automatically detects screen width via `shutil.get_terminal_size()`. Seamlessly adapts to portrait Android phone screens (40–60 columns) with zero text wrapping glitches or broken borders.
- **Stacked Card Layouts:** Replaced wide horizontal multi-column tables with stacked vertical execution cards that never overflow narrow mobile viewports.
- **Touch-Friendly Quick Action Palette (`[1]-[0]`):** Single-tap numeric shortcuts so you don't have to type long commands on a soft keyboard:
  - `[1]` 🔦 **Torch** — Instant flashlight toggle
  - `[2]` 🔋 **Battery** — Real-time battery percentage & thermal state
  - `[3]` 📸 **Camera Snap** — Direct hardware camera capture
  - `[4]` ⚡ **FastFetch** — Stacked ASCII/Unicode telemetry
  - `[5]` 🧩 **Extensions** — Interactive dynamic extension store
  - `[6]` 🧹 **Clean Disk** — Wipe caches, thumbnails, and temp files
  - `[7]` 📋 **Audit Logs** — Hardware execution audit history viewer
  - `[8]` 🛡️ **Security** — Active sessions, token bucket rate limiter & cipher status
  - `[9]` 🧠 **Local LLMs** — Small-model downloader & weight inspector
  - `[0]` 🤖 **Bot Hub** — `@voidtermuxbot` status & test ping
  - `[?]` 📖 **Help Guide** — Command directory & directive examples
  - `[Q]` 🚪 **Exit App** — Clean teardown & history save
- **Live Telemetry & Resource Monitor Widget:** Live card displaying RAM RSS (< 30MB benchmark tracking), battery level, SQLite WAL database status, active engine, and bot connection state.
- **Animated Activity Spinner:** Thread-safe background spinner (`⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏`) during ReAct reasoning cycles.
- **Persistent Command History:** Arrow navigation powered by `readline` (`~/.void/.cli_history`).

---

## 🧩 On-Demand Dynamic Plugin Store

Void starts completely lean with **zero extensions loaded by default**. You choose what to install:

### CLI Commands:
```bash
# 1. List active plugins (starts at 0)
void plugins

# 2. Search community plugins catalog
void plugins search crypto

# 3. Install community plugin on-demand
void plugin install crypto_tracker

# 4. Uninstall plugin cleanly
void plugin remove crypto_tracker
```

### Telegram Bot Plugin Store:
Open your bot and send `/plugins` or tap **`🧩 Plugin Store`** from the interactive dashboard. You can install or remove extensions with a single tap.

### Verified Community Plugins:
- **`crypto_tracker`**: Real-time cryptocurrency market prices (BTC, ETH, SOL, DOGE, XRP).
- **`github_monitor`**: GitHub repository stars, forks, issues, and commit tracking.
- **`weather_brief`**: Local meteorological forecasts, temperature, and condition reports.

### Security Sandbox:
- **SHA256 Integrity Verification:** Checksums are computed and validated before code activation.
- **Static AST Inspection:** Validates Python AST to prevent malformed syntax or non-plugin code from loading.
- **Sandboxed Storage:** All user extensions live in `~/.void/extensions/` and can be removed anytime.

---

## 🧠 Autonomous Local Model Bootstrapper

Void features an autonomous `ModelManager` located in `core/model_manager.py` that discovers, verifies, and downloads quantized small models:

| Model ID | Base Architecture | RAM Footprint | Best Suited For |
| :--- | :--- | :--- | :--- |
| `smollm-135m` | SmolLM-135M-Instruct-Q4 GGUF | **< 90 MB RAM** | Ultra-fast local edge execution |
| `needle-compact`| Needle-Edge Compact Binary | **< 30 MB RAM** | Vectorized hardware tool dispatch |
| `qwen-0.5b` | Qwen2.5-0.5B-Instruct-Q4 GGUF | **< 380 MB RAM** | Multi-step reasoning & tool calling |

```bash
# View model catalog:
void models

# Download model directly in terminal:
void download smollm-135m
```

---

## 📊 Visual FastFetch Telemetry

Run anytime in your terminal:
```bash
void fastfetch
```

```text
╭───────────────────────────────────────────────────────────╮
│                VOID TELEMETRY FASTFETCH                   │
╰───────────────────────────────────────────────────────────╯
  __     __     _     _   Host        │ Google Pixel 8 Pro
  \ \   / /__  (_) __| |  OS          │ Android 14 (Termux)
   \ \ / / _ \ | |/ _` |  Kernel      │ 5.15.137-android14 (aarch64)
    \ V / (_) || | (_| |  Uptime      │ 3d 14h 22m
     \_/ \___/ |_|\__,_|  Python      │ 3.11.8 (Shell: bash)
    EDGE AGENTIC DAEMON   Void RSS    │ 21.4 MB (Target < 30MB ✅)
                          RAM         │ 2410 MB / 11520 MB
                          Battery     │ 92% [CHARGING] (31.2°C)
                          Network     │ 192.168.1.145 (Wi-Fi: Studio_5G)
                          Model       │ SmolLM-135M-Instruct-Q4
                          Daemons     │ NotifDaemon, Cron
```

Or view directly inside Telegram with `/fastfetch`!

---

## 🛡️ Android Permissions & Troubleshooting

### Silent Wake-Lock & Notification Suppression
When running background daemons 24/7, Termux acquires a CPU wake-lock (`termux-wake-lock`). If you do not want background wake-locks, start Void with:
```bash
void start-bg --no-wake-lock
```

### Permission Governance
Run `void permissions` to inspect the status, rationale, and privacy impact of every Android hardware permission:
```bash
void permissions
```

### Termux:API Companion Bridge Diagnostic
If hardware commands (e.g. `termux-battery-status`) return nothing:
1. Ensure both **Termux** and **Termux:API** were installed from **F-Droid**.
2. Open the **Termux:API** application once from your Android app drawer.
3. Check **Settings -> Battery -> Unrestricted** for Termux and Termux:API to prevent Android battery optimizations from killing background workers.

---

## 🧪 Automated Testing & Verification

Void maintains a 100% test pass rate across all edge subsystems:

```bash
void test
```

```text
============================= test session starts ==============================
collected 77 items

tests/test_bot_setup.py ...                                              [  3%]
tests/test_daemons.py ...                                                [  7%]
tests/test_extensions.py ......                                          [ 15%]
tests/test_fastfetch.py ...                                              [ 19%]
tests/test_lru_cache.py ...                                              [ 23%]
tests/test_model_manager.py ....                                         [ 28%]
tests/test_react_agent.py ...                                            [ 32%]
tests/test_security.py ........                                          [ 42%]
tests/test_simulator.py ..                                               [ 45%]
tests/test_social_apps.py .....                                          [ 51%]
tests/test_storage.py ...                                                [ 55%]
tests/test_telegram_advanced.py .............                            [ 72%]
tests/test_telegram_bot.py ....                                          [ 77%]
tests/test_termux_void.py .............                                  [ 94%]
tests/test_tools.py ....                                                 [100%]

============================== 77 passed in 3.44s ==============================
```

---

## 📄 License

Distributed under the **Apache License 2.0**. Engineered with ⚡ by [Ashish Singh Bora](https://github.com/ashishsinghbora).
