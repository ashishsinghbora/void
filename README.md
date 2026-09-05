# ⚡ Void: Autonomous Edge Agent Platform (Android / Termux)

<div align="center">

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Android%20(Termux)%20%7C%20Linux-cyan.svg)](https://termux.dev)
[![Memory RSS](https://img.shields.io/badge/RAM%20RSS-%3C%2030MB%20(Verified)-emerald.svg)](#-memory-benchmarks--efficiency)
[![Models](https://img.shields.io/badge/Models-Strictly%20%3C%202GB%20(LMK--Immune)-orange.svg)](#-ultra-efficient-local-edge-models-strictly--2gb)
[![Tests](https://img.shields.io/badge/tests-136%2F136%20passed%20(100%25)-green.svg)](#-automated-testing--verification)
[![Control](https://img.shields.io/badge/control-6--Hub%20Telegram%20UI%20%2B%20Mobile%20TUI-purple.svg)](#-permanent-extensible-6-hub-telegram-ui)

**Void** is a hyper-minimalist, terminal-and-Telegram-native autonomous Android orchestrator engineered for mobile edge computing. Inspired by ultra-lightweight agent frameworks (like OpenClaw), Void eliminates all heavy web server bloat (zero Flask, zero WSGI, zero HTML/SSE overhead), starting with **zero default extensions** and running as an ultra-lean local daemon controlled exclusively through an interactive rich TUI and an interactive Telegram Bot interface.

[One-Line Install](#-one-line-zero-friction-installer) • [Directory Blueprint](#-refactored-directory-blueprint) • [F-Droid Setup](#-f-droid-prerequisites-termux--termuxapi) • [Telegram Bot Setup](#-frictionless-telegram-bot-setup-wizard) • [6-Hub Control Center](#-permanent-extensible-6-hub-telegram-ui) • [Cloud Vault & Brain Sync](#-dual-brain--bidirectional-cloud-vault-sync) • [Remote SSH & Shell](#-remote-openssh--live-bash-execution) • [Local Models (<2GB)](#-ultra-efficient-local-edge-models-strictly--2gb) • [CLI Commands & Rich TUI](#-mobile-optimized-rich-tui) • [Testing](#-automated-testing--verification)

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
├── config/
│   └── settings.py             # Configuration manager with strict 2048 MB RAM ceiling & compute profiles
├── core/
│   ├── agent_engine.py         # Advanced agent engine with bounded ReAct state loops
│   ├── bot_setup.py            # Frictionless Telegram setup wizard & Admin ID auto-detection
│   ├── command_executor.py     # Secure argument-vector subprocess executor with Termux IPC
│   ├── event_bus.py            # Pub/sub event streaming bus
│   ├── fastfetch.py            # ASCII & Unicode FastFetch telemetry collector
│   ├── lru_cache.py            # Bounded LRU query cache (O(1) lookups)
│   ├── model_manager.py        # Small-model bootstrapper (< 2GB GGUF models: SmolLM, Needle, Qwen)
│   └── types.py                # Strongly-typed ReAct dataclasses with __slots__
├── agents/
│   ├── react_agent.py          # Autonomous ReAct loop with heuristic fallback router
│   ├── prompt_processor.py     # Natural language tokenizer & intent preprocessor
│   └── fallback_handler.py     # Hardware error recovery & alternative tool suggestion
├── modules/
│   ├── terminal_service.py     # Remote OpenSSH daemon management & safe bash execution engine
│   ├── brain_sync.py           # Bidirectional Telegram group cloud vault & local brain synchronizer
│   ├── deep_links.py           # Android deep links (YouTube research, UPI, WhatsApp, Maps, Settings)
│   ├── notification_watcher.py # Proactive 2FA/OTP interception with clipboard auto-copy
│   ├── scraper_vault.py        # Autonomous web scraping & article ingestion pipeline
│   └── voice_handler.py        # Voice note transcription & call screening auto text-back
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
│   ├── middleware/             # Role-based access control & rate limiting
│   ├── services/
│   │   ├── cloud_vault.py      # Cloud Vault media storage service
│   │   ├── device_service.py   # Multi-device registry & remote tool dispatcher
│   │   ├── payment_service.py  # Telegram Stars (XTR) invoice generator
│   │   └── tma_auth_service.py # HMAC-SHA256 Telegram Mini App auth
│   ├── handlers/
│   │   ├── core_handlers.py    # /start, /sh, /bash, /ssh, /ram, /status, /fastfetch
│   │   ├── hub_handlers.py     # Permanent 6-Hub Control Center & Dynamic Extension Registry
│   │   ├── menu_router.py      # Centralized callback router with backward compatibility
│   │   ├── vault_handlers.py   # /vault, /set_vault, /link_vault pairing
│   │   ├── billing_handlers.py # /billing, Stars invoices, pre-checkout & fulfillment
│   │   └── settings_handlers.py# /settings & in-chat preference toggles
│   └── webapp/                 # High-performance Telegram Mini App (TMA)
├── tools/
│   ├── base.py                 # Strategy pattern base class
│   ├── hardware.py             # Battery, torch, vibration, volume, display
│   ├── telephony.py            # SMS send/receive, call, contacts, call log
│   ├── media.py                # Camera photo capture, text-to-speech, audio
│   ├── system.py               # Toasts, notifications, clipboard, GPS, wifi, native storage clean
│   ├── social_apps.py          # WhatsApp deep-links, Telegram chats, social profile intents
│   ├── mobile_actions.py       # Simulated touch tap, swipe, keyevent, typing, screen capture
│   ├── advanced_modules.py     # Bash execution, SSH management, Brain sync, YouTube research
│   └── registry.py             # Hash-indexed strategy pattern tool registry
├── tests/                      # Comprehensive 136-test automated test suite
├── app.py                      # Lean daemon supervisor, async runners & Telegram controller
├── termux_void.py              # Mobile-optimized terminal user interface (TUI)
├── install.sh                  # One-line zero-friction bootstrap installer
└── requirements.txt            # Minimal dependencies: pyTelegramBotAPI, requests, pytest
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
   - Go to Android **Settings -> Apps -> Termux:API -> Permissions** and grant desired permissions (Camera, Storage, SMS, Location). All permissions are optional; Void gracefully falls back to simulation mode if ungranted.

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

## 🎮 Permanent, Extensible 6-Hub Telegram UI

Void features a consolidated, ergonomic **6-Hub Control Center** on Telegram, designed to be permanent across updates while allowing dynamic extension integration:

```text
┌────────────────────────────────────────────────────────┐
│        ⚡ VOID EDGE AGENT ROOT CONTROL CENTER         │
├──────────────────────────┬─────────────────────────────┤
│  📱 Screen & Touch       │  ☁️ Vault & Brain           │
├──────────────────────────┼─────────────────────────────┤
│  💻 Terminal & SSH       │  🔬 Research & YouTube      │
├──────────────────────────┼─────────────────────────────┤
│  ⚡ Apps & Intents        │  🛡️ Security & Interceptor  │
└──────────────────────────┴─────────────────────────────┘
```

### The 6 Core Hubs:
1. **📱 Screen & Touch (`menu_screen`):**
   - High-speed screen capture & OCR text inspection.
   - Coordinate tap simulation (`/tap <x> <y>`).
   - Smooth gesture swiping (`/swipe <x1> <y1> <x2> <y2> [duration]`).
   - Software keyboard typing input (`/type <text>`).
   - Hardware keyevent simulation (`HOME`, `BACK`, `RECENTS`, `POWER`, `VOLUME`).
2. **☁️ Vault & Brain (`menu_vault`):**
   - Decentralized cloud vault memory status and statistics.
   - One-tap manual local-to-cloud bidirectional synchronization (`#DOC`, `#NOTE`, `#SCREEN`, `#RESEARCH`).
   - Telegram group file explorer & media indexer.
3. **💻 Terminal & SSH (`menu_terminal`):**
   - Remote OpenSSH daemon (`sshd`) status and one-tap Start / Stop controls.
   - Network IP interface discovery (`wlan0`, cellular, localhost).
   - One-tap quick connect command card (`ssh user@ip -p 8022`).
   - Live bash command execution (`/sh <cmd>` or `/bash <cmd>`).
4. **🔬 Research & YouTube (`menu_research`):**
   - Automated YouTube topic deep research and video playback.
   - Autonomous research note summarization archived to local brain dataset.
   - Background article scraper and digest generator.
5. **⚡ Apps & Intents (`menu_apps`):**
   - Instant 1-on-1 WhatsApp messaging via Android intents.
   - Telegram profile & channel deep navigation.
   - Google Maps turn-by-turn navigation intents (`d` driving, `w` walking, `b` bicycling).
   - Instant UPI payments (Google Pay, PhonePe, Paytm).
   - Android System Settings deep links (WiFi, Bluetooth, Battery, Display, Accessibility).
6. **🛡️ Security & Interceptor (`menu_security`):**
   - Real-time 2FA / Banking OTP interceptor with clipboard auto-copy.
   - Smart call-screening and auto text-back on missed calls.
   - Hardware security audit logs, rate limit status, and active sessions.

### 🧩 Dynamic Extension Registry
External plugins and community extensions dynamically hook into any of the 6 hubs via `register_hub_extension()` in `telegram/handlers/hub_handlers.py`:
```python
from telegram.handlers.hub_handlers import register_hub_extension

# Register an action button into the Terminal & SSH hub:
register_hub_extension("terminal", "⚡ Fast Diagnostic", "cb_fast_diag")
```

---

## ☁️ Dual Brain & Bidirectional Cloud Vault Sync

Void bridges local on-device datasets with an unlimited, decentralized **Telegram Group Cloud Vault**:

- **Local Phone Brain:** `~/.void/vault/` and `~/.void/brain/`
- **Cloud Vault:** Your private Telegram group where the Void bot is an **Admin**
- **Automatic Hashtag Classification:**
  - `#DOC` — PDFs, office documents
  - `#NOTE` — Text summaries, logs
  - `#SCREEN` — Screenshots, camera frames
  - `#RESEARCH` — Web and YouTube research syntheses
  - `#OTP` — Intercepted banking 2FA tokens
  - `#MEDIA` — Audio recordings, videos, images
  - `#CODE` — Python scripts, shell files, JSON payloads
- **SHA-256 Deduplication:** Ensures zero duplicate bandwidth usage.
- **Pairing Onboarding Wizard:**
  - Add your bot to any private Telegram group as an **Administrator**.
  - Send `/link_vault` inside the group to bind it permanently.
  - Or configure via DM: `/set_vault <chat_id_or_invite_link>`.

---

## 💻 Remote OpenSSH & Live Bash Execution

Turn your Android device into a secure, accessible remote workstation:

- **Interactive Bash Execution:**
  ```bash
  /sh uname -a
  /sh free -m
  /sh pkg list-installed
  ```
- **OpenSSH Daemon Management:**
  ```bash
  /ssh start    # Launches sshd on port 8022
  /ssh stop     # Gracefully terminates sshd
  /ssh          # Displays connection card with available IPs and command
  ```
- **Dynamic RAM Control:**
  ```bash
  /ram          # Displays current RAM limit, model ceiling, and compute profile
  /ram 1024     # Sets dynamic RAM limit to 1024 MB (strictly clamped <= 2048 MB)
  ```

---

## 🧠 Ultra-Efficient Local Edge Models (Strictly < 2GB)

To guarantee that Android's Low Memory Killer (LMK) **never** terminates Void, all supported models are strictly capped under **2000 MB** (`MAX_MODEL_SIZE_MB = 2000.0`, `MAX_ALLOWED_RAM_MB = 2048`):

| Model ID | Architecture | File Size | Recommended Device RAM | Profile |
| :--- | :--- | :--- | :--- | :--- |
| `needle-compact` | Needle-Edge Binary | **28.5 MB** | 1 GB - 2 GB | Micro Edge Tool Router |
| `smollm-135m` | SmolLM-135M-Instruct Q4 | **85.0 MB** | 1.5 GB - 3 GB | Fast Edge Execution |
| `qwen-0.5b` | Qwen2.5-0.5B-Instruct Q4 | **350.0 MB** | 2 GB - 4 GB | Balanced Tool Calling |
| `llama-3.2-1b` | Llama-3.2-1B-Instruct Q4 | **850.0 MB** | 3 GB - 6 GB | High-Accuracy Autonomy |
| `smollm2-1.7b` | SmolLM2-1.7B-Instruct Q4 | **1050.0 MB** | 4 GB - 8 GB | Multi-Step Reasoning |
| `qwen2.5-1.5b` | Qwen2.5-1.5B-Instruct Q4 | **1150.0 MB** | 4 GB - 12 GB | Elite Mobile Digital Twin |

```bash
# Inspect available models:
void models

# Download model directly in terminal:
void download qwen-0.5b

# Run the interactive LLM setup wizard:
void wizard
```

---

## ⚡ Mobile-Optimized Rich TUI

Launch Void's mobile-adaptive Terminal User Interface (TUI):

```bash
void
# or explicitly:
void cli
```

### 📱 Key Features:
- **Responsive Viewport Adaptation:** Automatically detects screen width via `shutil.get_terminal_size()` (40–60 columns) with zero horizontal overflow.
- **Stacked Card Layouts:** Vertical cards designed specifically for mobile touchscreens.
- **Touch-Friendly Quick Action Palette (`[1]-[0], [V], [W], [X], [S], [Q]`):**
  - `[1]` 🔦 **Torch** — Instant flashlight toggle
  - `[2]` 🔋 **Battery** — Real-time battery percentage & thermal state
  - `[3]` 📸 **Camera Snap** — Direct hardware camera capture
  - `[4]` ⚡ **FastFetch** — Stacked ASCII/Unicode telemetry
  - `[5]` 🧩 **Extensions** — Dynamic plugin store
  - `[6]` 🧹 **Clean Disk** — Wipe caches, thumbnails, and temp files
  - `[7]` 📋 **Audit Logs** — Hardware execution audit history viewer
  - `[8]` 🛡️ **Security** — Active sessions, token bucket rate limiter & cipher status
  - `[9]` 🧠 **Local LLMs** — Small-model downloader & weight inspector
  - `[0]` 🤖 **Bot Hub** — `@voidtermuxbot` status & test ping
  - `[V]` ☁️ **Cloud Vault** — Telegram group memory & file explorer
  - `[W]` 🧙 **LLM Wizard** — Guided model setup for device RAM
  - `[X]` 💻 **Remote SSH** — OpenSSH daemon status & connection card
  - `[S]` 📱 **Screenshot** — Instant Android screen capture
  - `[Q]` 🚪 **Exit App** — Clean teardown & history save
- **Live Telemetry & Resource Monitor Widget:** Tracks RAM RSS (< 30MB benchmark), RAM Cap (< 2048 MB), battery, SQLite WAL, model engine, SSH status, and bot connectivity.
- **Persistent Command History:** Arrow navigation powered by `readline` (`~/.void/.cli_history`).

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
                          RAM         │ 2410 MB / 11520 MB (Cap: 2048MB)
                          Battery     │ 92% [CHARGING] (31.2°C)
                          Network     │ 192.168.1.145 (Wi-Fi: Studio_5G)
                          SSH         │ Active (Port 8022)
                          Model       │ SmolLM-135M-Instruct-Q4
                          Daemons     │ NotifDaemon, Scraper, BrainSync
```

Or view directly inside Telegram with `/fastfetch`!

---

## 🧪 Automated Testing & Verification

Void maintains a 100% test pass rate across 136 automated test cases:

```bash
void test
# or:
python3 -m pytest
```

```text
============================= test session starts ==============================
collected 136 items

tests/test_75_button_hierarchy.py ......                                 [  4%]
tests/test_advanced_modules.py ............                              [ 13%]
tests/test_bot_setup.py ...                                              [ 15%]
tests/test_cloud_vault.py ....                                           [ 18%]
tests/test_daemons.py ...                                                [ 20%]
tests/test_extensions.py ......                                          [ 25%]
tests/test_fastfetch.py ...                                              [ 27%]
tests/test_lru_cache.py ...                                              [ 29%]
tests/test_media_vault.py ...                                            [ 31%]
tests/test_mobile_actions.py ........                                    [ 37%]
tests/test_model_manager.py ....                                         [ 40%]
tests/test_react_agent.py ...                                            [ 42%]
tests/test_safe_telegram.py ....                                         [ 45%]
tests/test_security.py ........                                          [ 51%]
tests/test_simulator.py ..                                               [ 52%]
tests/test_social_apps.py .....                                          [ 56%]
tests/test_storage.py ...                                                [ 58%]
tests/test_submenus_callbacks.py ....                                    [ 61%]
tests/test_super_master.py ..................                            [ 75%]
tests/test_telegram_advanced.py .............                            [ 84%]
tests/test_telegram_bot.py ....                                          [ 87%]
tests/test_termux_void.py .............                                  [ 97%]
tests/test_tools.py ....                                                 [100%]

============================= 136 passed in 6.35s ==============================
```

---

## 📄 License

Distributed under the **Apache License 2.0**. Engineered with ⚡ by [Ashish Singh Bora](https://github.com/ashishsinghbora).
