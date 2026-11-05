# 📬 AI Gmail Agent

An intelligent, autonomous AI-powered assistant for Gmail featuring cognitive natural language processing, sender-wise folder organization, automated drafting, attachment parsing, and an interactive desktop/web avatar companion.

---

## ✨ Features

- **🧠 Cognitive NLP Engine ([`agent_brain.py`](agent_brain.py)):**
  Understands natural language instructions for mailbox organization, sender blocking, draft generation, and synopsis queries with zero-latency heuristic fallbacks.
- **📁 Sender-Wise Folder Organization ([`gmail_agent.py`](gmail_agent.py)):**
  Automatically routes and groups emails into clean, dedicated Gmail label folders named after senders (e.g. all mails from IndusInd into folder `indusind`).
- **🎯 Targeted Sender Sorting:**
  Target a particular sender via voice/chat command or UI to consolidate their emails into a folder without touching the rest of your mailbox.
- **⚡ Automated Smart Drafting:**
  Generates contextual draft responses for designated contacts using OmniRoute, OpenAI, or Gemini.
- **📂 Multi-Format File Reader ([`file_reader.py`](file_reader.py)):**
  Reads, inspects, and analyzes attachments including PDFs, Word documents (`.docx`), Excel spreadsheets (`.xlsx`), images (`.png`, `.gif`), and arbitrary binaries.
- **🚫 Sender Blacklist & Spam Purge:**
  Blocks unwanted senders and automatically moves both incoming and historical emails to Trash.
- **🖥️ Dual Interface:**
  - Interactive Streamlit Dashboard ([`app.py`](app.py)) with an animated avatar companion.
  - Background Service Daemon ([`daemon.py`](daemon.py)) and REST API server ([`server.py`](server.py)) for continuous 24/7 inbox management.
- **🧩 Gmail Browser Extension ([`extension/`](extension/)):**
  Direct Gmail web integration widget.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- A Google Cloud Project with the **Gmail API** enabled and OAuth credentials downloaded as `credentials.json`.

### 2. Installation
```bash
git clone https://github.com/pnchjee-del/mail_agent.git
cd mail_agent
pip install -r requirements.txt
```

### 3. Setup Credentials & Configuration
1. Place your Google Cloud OAuth credentials file as `credentials.json` in the root folder.
2. Copy `config.example.json` to `config.json`:
   ```bash
   cp config.example.json config.json
   ```
3. Authenticate with Gmail by running:
   ```bash
   python reauth.py
   ```
   *(A browser window will open to authorize the Gmail scopes)*

### 4. Running the Agent
- **Launch Interactive Web Dashboard:**
  ```bash
  streamlit run app.py
  ```
- **Launch REST API Server:**
  ```bash
  python server.py
  ```
- **Run Continuous Background Daemon:**
  ```bash
  python daemon.py
  ```

---

## 💬 Example Natural Language Commands

You can prompt the agent through the web chat or the API:
- *"Put all mails from indusind in a folder named indusind"*
- *"Put all mails from client@example.com in a folder named after the sender"*
- *"Sort my mails sender wise"*
- *"Block sender spam@promos.com"*
- *"Who is blocked?"*
- *"Draft a reply to the latest mail"*
- *"How many unread emails do I have?"*

---

## 🔒 Security & Privacy

- `credentials.json`, `token.json`, and `extension/auth_config.json` are excluded via `.gitignore` to safeguard personal authentication tokens and API keys.
- Legitimate newly arrived emails are protected with a default 1-hour grace period on top of your inbox before auto-archiving.

---

## 📄 License
MIT License.
