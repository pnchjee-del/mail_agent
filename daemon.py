import os
import sys
import time
import json
from datetime import datetime
from gmail_agent import GmailAIAgent

CONFIG_FILE = "config.json"
LOG_FILE = "agent_activity.log"

def load_config():
    default_config = {
        "poll_interval_seconds": 300,
        "max_scan": 10,
        "auto_delete": True,
        "designated_senders": ["client@example.com", "boss@company.com"],
        "delete_senders": ["spam@promos.com", "newsletter@ads.com"]
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**default_config, **json.load(f)}
        except Exception as e:
            print(f"[Warning] Could not read {CONFIG_FILE}: {e}. Using defaults.")
    return default_config

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"Failed to write to log file: {e}")

def run():
    log("==========================================")
    log("🚀 AI Gmail Agent Daemon Starting...")
    config = load_config()
    log(f"Polling Interval: {config['poll_interval_seconds']}s ({config['poll_interval_seconds'] // 60} minutes)")
    log(f"Auto-trash Blacklisted: {config['auto_delete']}")
    log(f"Designated Auto-Draft Senders: {config['designated_senders']}")
    log(f"Blacklisted Senders: {config['delete_senders']}")
    log("Press Ctrl+C to terminate the daemon.")
    log("==========================================")

    # Save PID so it can be stopped cleanly
    pid_file = "daemon.pid"
    with open(pid_file, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    agent = None
    try:
        agent = GmailAIAgent(
            designated_senders=config.get("designated_senders", []),
            delete_senders=config.get("delete_senders", [])
        )
        log("✅ Gmail Agent successfully authenticated and initialized.")
    except Exception as e:
        log(f"❌ Failed to initialize agent: {e}")
        if os.path.exists(pid_file):
            os.remove(pid_file)
        sys.exit(1)

    while True:
        try:
            # Reload config dynamically in case the user updated rules
            current_config = load_config()
            agent.designated_senders = [s.strip().lower() for s in current_config.get("designated_senders", []) if s.strip()]
            agent.delete_senders = [s.strip().lower() for s in current_config.get("delete_senders", []) if s.strip()]

            log("🔍 Scanning inbox for unread messages...")
            results = agent.process_unread_emails(
                auto_delete=current_config.get("auto_delete", True),
                max_results=current_config.get("max_scan", 10),
                grace_period_minutes=current_config.get("grace_period_minutes", 60)
            )

            if not results:
                log("📭 Inbox clean. No unread messages.")
            else:
                log(f"✨ Processed {len(results)} email(s):")
                for item in results:
                    log(f"  • [{item['category']}] '{item['subject']}' from {item['sender']} -> {item['action']}")
                    if item.get("attachments"):
                        att_names = [f"{a.get('filename')} ({a.get('file_type')})" for a in item["attachments"]]
                        log(f"    ├─ Read {len(item['attachments'])} attachment(s): {', '.join(att_names)}")
                    if item.get("draft"):
                        log(f"    └─ Drafted reply: '{item['draft']['subject']}'")

        except Exception as e:
            log(f"⚠️ Error during scan cycle: {e}")

        interval = current_config.get("poll_interval_seconds", 300)
        log(f"⏳ Sleeping for {interval}s ({interval // 60}m)...")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            log("🛑 Daemon stopped by user.")
            break
        finally:
            if os.path.exists(pid_file):
                try:
                    os.remove(pid_file)
                except Exception:
                    pass

if __name__ == "__main__":
    run()
