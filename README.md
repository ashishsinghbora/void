# ⚡ Void: Autonomous Edge Agent Platform (Android / Termux)

<div align="center">

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Android%20%7C%20Termux%20%7C%20Linux-cyan.svg)](https://termux.dev)
[![Memory RSS](https://img.shields.io/badge/RAM%20RSS-%3C%2030MB-emerald.svg)](#-memory-benchmarks--performance)
[![Tests](https://img.shields.io/badge/tests-49%2F49%20passed%20(100%25)-green.svg)](#-automated-testing--verification)
[![UI](https://img.shields.io/badge/control-Terminal%20CLI%20%2B%20Telegram-purple.svg)](#-rich-telegram-bot-control-hub)

**Void** is a hyper-minimalist, terminal-and-Telegram-native autonomous Android orchestrator engineered for mobile edge computing. Inspired by ultra-lightweight agent frameworks (like OpenClaw), Void eliminates all heavy web server bloat (zero Flask, zero WSGI, zero HTML/SSE overhead), running as an ultra-lean local daemon controlled exclusively through an interactive terminal session and a rich, interactive Telegram Bot interface.

[One-Line Install](#-one-line-zero-friction-installer) • [Architecture](#-architectural-pivot--zero-web-bloat) • [CLI Commands](#-unified-cli-commands) • [Telegram Control](#-rich-telegram-bot-control-hub) • [FastFetch](#-visual-fastfetch-telemetry) • [Local LLM Bootstrapper](#-autonomous-local-model-bootstrapper) • [Social & Cross-App Tools](#-social-media--cross-app-automation) • [Testing](#-automated-testing--verification)

</div>

---

## 🚀 One-Line Zero-Friction Installer

Deploy Void directly into your Termux or Linux environment in seconds:

```bash
curl -sSL https://raw.githubusercontent.com/ashishsinghbora/void/main/install.sh | bash
```

> [!TIP]
> To update or reinstall to the latest build on Termux:
> ```bash
> rm -rf ~/void && curl -sSL https://raw.githubusercontent.com/ashishsinghbora/void/main/install.sh | bash
> ```

---

## 🏛️ Architectural Pivot: Zero-Web-Bloat

Void has been re-architected from the ground up for maximum edge efficiency and security:

| Feature / Metric | Legacy Web Agent | Void Ultra-Lean Edge Platform |
| :--- | :--- | :--- |
| **Control Planes** | Heavy Flask / Waitress / HTML / SSE | **Interactive Terminal CLI + Rich Telegram Bot** |
| **RAM RSS Footprint** | ~75 MB – 120 MB | **< 30 MB RAM** |
| **Dependencies** | Flask, Waitress, Jinja2, Werkzeug, etc. | **`pyTelegramBotAPI`, `requests`, `pytest`** |
| **Port Conflicts** | Socket collision (`Errno 98`), port 5000 | **Zero open network ports required** |
| **Model Runtime** | Cloud API or bulky dependencies | **Local Quantized GGUF / Needle + Heuristic Fallback** |
| **Hardware Bridge** | HTTP Polling | **Zero-overhead direct IPC (`termux-api` vectors)** |

---

## ⚡ Unified CLI Commands

The global `void` command provides single-keystroke control over the entire edge stack:

```bash
# 1. Interactive ReAct Terminal Assistant (default)
void
# or explicitly:
void cli

# 2. Visual ASCII / Unicode FastFetch Telemetry
void fastfetch

# 3. Inspect Local Small-Model Catalog & Weights
void models

# 4. Start Background Daemon Supervisor & Telegram Bot (foreground)
void start

# 5. Start Void as a Background 24/7 Service (nohup daemon)
void start-bg

# 6. Check Active Daemon Status, Memory RSS & Battery
void status

# 7. Stop Background Daemon Cleanly
void stop

# 8. Run Full Automated Test Suite (49/49 tests)
void test

# 9. Clean Temporary Caches & Storage
void clean

# 10. Inspect Android Privacy & Permissions Status
void permissions

# 11. Pull Latest Updates from GitHub
void update
```

---

## 📱 Rich Telegram Bot Control Hub

Control your Android phone remotely with bank-grade security, whitelisted admin access, rate limiting, and interactive inline keyboards:

```
╭─────────────────────────────────────────╮
│  ⚡ VOID EDGE REMOTE CONTROL HUB        │
├────────────────────┬────────────────────┤
│  🔦 Torch [OFF]    │  🔋 Battery Meter  │
├────────────────────┼────────────────────┤
│  📸 Take Photo     │  🧹 Clean Storage  │
├────────────────────┼────────────────────┤
│  ⚡ FastFetch      │  📋 Recent Logs    │
├────────────────────┼────────────────────┤
│  🚀 Apps Hub       │  🧠 Model Status   │
╰────────────────────┴────────────────────╯
```

### Interactive Telegram Commands & Callbacks:
- **`🔦 Torch Toggle`**: Instantly switches phone camera flashlight ON or OFF and updates button state.
- **`🔋 Battery Meter`**: Real-time battery %, charge state, and temperature alert.
- **`📸 Take Photo`**: Captures photo using front or back camera and **sends the image directly into Telegram** via `bot.send_photo`.
- **`⚡ FastFetch`**: Renders full Unicode system telemetry, process RSS, and daemon health directly in chat.
- **`🧹 Clean Storage`**: Executes safe cache cleanup and reports freed disk space.
- **`🚀 Apps Hub`**: Quick submenu to launch WhatsApp, Telegram, Camera, YouTube, Chrome, or Settings on the device.
- **`🧠 Model Status`**: Shows active model engine and available downloads.
- **`/download <model_id>`**: Triggers streaming background download of local model weights with a live progress bar updated in Telegram.

### Launching with Telegram Bot:
```bash
# Pass credentials via CLI:
void start --telegram YOUR_BOT_TOKEN --admin-id YOUR_TELEGRAM_USER_ID

# Or configure via environment variables:
export TELEGRAM_TOKEN="YOUR_BOT_TOKEN"
export ADMIN_TELEGRAM_ID="YOUR_TELEGRAM_USER_ID"
void start-bg
```

---

## 📊 Visual FastFetch Telemetry

Void includes a built-in `FastFetchCollector` that provides instant system diagnostics:

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

Run anytime in your terminal with:
```bash
void fastfetch
```

---

## 🧠 Autonomous Local Model Bootstrapper

Void integrates a dedicated `ModelManager` located in `core/model_manager.py` that discovers, verifies, and downloads quantized small models to `~/.void/models/`:

| Model Identifier | Architecture | RAM Footprint | Best Suited For |
| :--- | :--- | :--- | :--- |
| `smollm-135m` | SmolLM-135M-Instruct-Q4 GGUF | **< 90 MB RAM** | Ultra-fast local edge execution |
| `needle-compact`| Needle-Edge Compact Binary | **< 30 MB RAM** | Vectorized hardware tool dispatch |
| `qwen-0.5b` | Qwen2.5-0.5B-Instruct-Q4 GGUF | **< 380 MB RAM** | Multi-step reasoning & tool calling |

### Features:
- **Resilient Streaming Downloads:** Chunked downloads via `requests` with live percentage and speed callbacks (CLI and Telegram).
- **SHA256 Integrity Verification:** Automatically validates checksums before activating weights.
- **Zero-Latency Heuristic Fallback:** If models are offline or downloading, Void automatically routes user directives through its zero-weight ReAct heuristic state machine.

---

## 🌐 Social Media & Cross-App Automation

Void includes first-class tools for mobile application dispatch and cross-app communication (`tools/social_apps.py`):

1. **`send_whatsapp_message`**:
   - Opens WhatsApp with a pre-filled message draft to any phone number.
   - Example directive: `"whatsapp +15551234567 saying I am on my way"`
2. **`open_telegram_chat`**:
   - Opens direct chat with any user or channel.
   - Example directive: `"open telegram chat with durov"`
3. **`open_social_profile`**:
   - Direct profile navigation for Instagram, LinkedIn, GitHub, or X.
   - Example directive: `"open github profile ashishsinghbora/void"`
4. **`launch_installed_app`**:
   - Launches any installed Android app via package intent with smart alias matching (`whatsapp`, `youtube`, `camera`, `settings`, `spotify`, `chrome`, etc.).
   - Example directive: `"launch camera"`, `"open settings"`

---

## 🛡️ Security, Privacy & Android Permissions

- **100% On-Device:** Zero data is transmitted to external telemetry servers. All conversations and execution logs reside in local SQLite databases (`~/.void_agent.db`) configured with Write-Ahead Logging (WAL).
- **Arg-Vector Sanitization:** All tool directives execute via tokenized argument vectors (`subprocess.run(["cmd", arg])`), eliminating command injection vulnerabilities.
- **Silent Wake-Lock Management:** Background wake-locks (`termux-wake-lock`) can be disabled via `--no-wake-lock` to suppress foreground notification sounds.
- **Permission Transparency:** Type `void permissions` anytime to view the rationale, scope, and status of every Android hardware permission.

---

## 🧪 Automated Testing & Verification

Void maintains a 100% test pass rate across all edge subsystems:

```bash
void test
```

```text
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1
collected 49 items

tests/test_daemons.py ...                                                [  6%]
tests/test_extensions.py .......                                         [ 20%]
tests/test_fastfetch.py ...                                              [ 26%]
tests/test_lru_cache.py ...                                              [ 32%]
tests/test_model_manager.py ....                                         [ 40%]
tests/test_react_agent.py ...                                            [ 46%]
tests/test_security.py ........                                          [ 63%]
tests/test_simulator.py ..                                               [ 67%]
tests/test_social_apps.py .....                                          [ 77%]
tests/test_storage.py ...                                                [ 83%]
tests/test_telegram_bot.py ....                                          [ 91%]
tests/test_tools.py ....                                                 [100%]

============================= 49 passed in 16.65s ==============================
```

---

## 📄 License

Distributed under the **Apache License 2.0**. Engineered with ⚡ by [Ashish Singh Bora](https://github.com/ashishsinghbora).
