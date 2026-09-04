# Void: Enterprise Edge Agentic Platform (Android / Termux)

**Void** is an enterprise-grade, high-performance, ultra-low-memory (< 50MB RAM) local agentic platform designed specifically for Android/Termux and embedded edge devices.

---

## 🌟 Key Architecture & Capabilities

- **Ultra-Low Memory Footprint (`< 15MB RAM` Peak):** Built with zero allocation overhead, strict `__slots__` memory optimization across all state classes, and generator-based streaming for large JSON parsing.
- **Deterministic ReAct State Machine:** Reason $\to$ Act $\to$ Observe execution loop with automated hardware permission error recovery (camera fallbacks, SMS-to-Share-Sheet fallbacks, and user remediation).
- **Hardened Cyber Defenses:** Whitelist-based regex sanitization on all dynamic inputs (phones, paths, URLs), strictly vector-based subprocess execution (`list[str]`, never `shell=True`), and an authenticated AES-256-GCM credential vault with PBKDF2 key derivation.
- **Zero-Bloat Persistence:** Local SQLite database operating in Write-Ahead Logging (`WAL`) mode with sliding-window index log pruning to prevent storage bloat.
- **Glassmorphic Web Dashboard:** Responsive Tailwind CSS interface with real-time Server-Sent Events (SSE) streaming reasoning steps, confidence metrics, and live telemetry served via the production Waitress WSGI server.
- **Remote Authenticated Telegram Bot:** Whitelisted control plane restricted by `ADMIN_TELEGRAM_ID`, backed by token-bucket rate limiting and session timeout protection.
- **Proactive Background Daemons:** Automated notification interception with OTP passcode extraction, spam suppression, scheduled morning voice briefings, and battery health alerts.

---

## 📁 Repository Structure

```
void/
├── core/                   # Architectural Foundation & Optimization
│   ├── types.py            # Slots-optimized dataclasses (__slots__)
│   ├── lru_cache.py        # O(1) Doubly-Linked List + Hash Map Bounded Cache
│   ├── command_executor.py # Command Pattern & zero-copy JSON streaming
│   ├── simulator.py        # High-fidelity desktop simulation layer
│   ├── event_bus.py        # Non-blocking Pub-Sub event distributor for SSE
│   └── agent_engine.py     # Master Implementation Blueprint engine
├── security/               # Cyber Hardening & Privilege Isolation
│   ├── sanitizer.py        # Whitelist-based regex validation & injection defense
│   ├── credential_vault.py # Authenticated AES-256-GCM vault with PBKDF2
│   └── rate_limiter.py     # Token-bucket rate limiting & session timeouts
├── storage/                # Zero-Bloat Persistence Layer
│   ├── sqlite_db.py        # Thread-safe SQLite with WAL journal mode
│   ├── repository.py       # Repositories for conversation, logs, clipboard, telemetry
│   └── log_pruner.py       # Sliding-window index pruner ensuring bounded disk usage
├── tools/                  # Strategy Pattern Dynamic Hardware APIs
│   ├── base.py             # ToolStrategy abstract base contract
│   ├── registry.py         # Hash-indexed O(1) ToolRegistry
│   ├── hardware.py         # Battery, torch, haptics, brightness, volume
│   ├── telephony.py        # SMS, voice calls, contacts, call log, telephony info
│   ├── media.py            # Camera photo, TTS speak, audio record, share sheet
│   └── system.py           # Toast, notifications, clipboard, GPS, Wi-Fi, app launcher
├── agents/                 # Autonomous ReAct Agent Loop
│   ├── react_agent.py      # Deterministic Reason + Act + Observe state machine
│   ├── fallback_handler.py # Android hardware permission error recovery
│   └── prompt_processor.py # Speech quotation wrapping & query normalization
├── api/                    # Production Web Server & Real-time SSE
│   ├── web_server.py       # Waitress production WSGI server factory
│   ├── routes.py           # REST endpoints (/api/chat, /api/status, /api/logs)
│   ├── sse_stream.py       # Server-Sent Events real-time event generator
│   └── templates/
│       └── dashboard.html  # Glassmorphic Tailwind CSS web dashboard
├── daemons/                # Proactive Automation & Routine Engine
│   ├── notification_daemon.py # Notification interceptor, OTP extractor & spam silencer
│   ├── routine_engine.py   # Background battery health alerts & morning briefings
│   └── service_runner.py   # Daemon supervisor with termux-wake-lock
├── telegram/               # Authenticated Remote Control Plane
│   └── bot_controller.py   # Whitelisted Telegram bot with rate limiting
├── tests/                  # Automated Test Suite (25 Tests)
├── app.py                  # Production entrypoint (Web UI + Telegram + Daemons)
├── termux_void.py          # Hardened interactive CLI assistant
├── termux_needle.py        # Backward compatibility wrapper
└── requirements.txt        # Pinned production dependencies
```

---

## 🚀 Quick Start

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Launch Web Dashboard & Background Daemons
```bash
# Start server on port 5000
python3 app.py

# Start with Telegram remote control and admin authorization
python3 app.py --telegram <YOUR_BOT_TOKEN> --admin-id <YOUR_TELEGRAM_USER_ID>
```
Open `http://localhost:5000` (or `http://<DEVICE_IP>:5000`) in any browser.

### 3. Launch Interactive Terminal CLI
```bash
python3 termux_void.py
```

### 4. Run Automated Test Suite
```bash
pytest -v
```
All 25 tests covering security sanitization, AES-256 vault, bounded LRU cache, ReAct deliberation, SQLite WAL persistence, and proactive daemons will execute.

---

## ⚡ Supported Hardware & System Directives

- **Battery Health:** *"what is the battery status?"* / *"battery percentage"*
- **Torch / Flashlight:** *"turn on the flashlight"* / *"turn off flashlight"*
- **Haptic Vibration:** *"vibrate phone for 1 second"*
- **Speech Synthesis:** *"say out loud that task completed"*
- **Camera Photo:** *"take a photo using camera"*
- **SMS Messaging:** *"send sms to +1234567 saying Hello"*
- **Voice Calling:** *"call +1234567"*
- **Clipboard Management:** *"what is on my clipboard?"* / *"copy Hello to clipboard"*
- **Network & Wi-Fi:** *"what network is the phone connected to?"* / *"scan nearby wifi"*
- **Application Launcher:** *"open whatsapp"* / *"launch chrome"* / *"open settings"*
- **Audio Control:** *"set volume music to 10"* / *"get volume info"*
- **Downloads:** *"download file from https://example.com/file.zip"*
