import os
import sys
import json
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from gmail_agent import GmailAIAgent

app = Flask(__name__)

CONFIG_FILE = "config.json"
LOG_FILE = "agent_activity.log"
PID_FILE = "server.pid"

# Global state
state = {
    "agent": None,
    "latest_remark": "Hello! I'm your AI Gmail Assistant. What would you like me to do with your inbox today?",
    "is_scanning": False,
    "last_scan_time": None,
    "unread_count": 0,
    "last_results": []
}

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def load_config():
    default_cfg = {
        "poll_interval_seconds": 300,
        "max_scan": 10,
        "auto_delete": True,
        "designated_senders": ["client@example.com", "boss@company.com"],
        "delete_senders": ["spam@promos.com", "newsletter@ads.com"]
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**default_cfg, **json.load(f)}
        except Exception:
            pass
    return default_cfg

def get_agent():
    if state["agent"] is None:
        cfg = load_config()
        state["agent"] = GmailAIAgent(
            designated_senders=cfg.get("designated_senders", []),
            delete_senders=cfg.get("delete_senders", []),
            api_key=cfg.get("openai_api_key"),
            gemini_api_key=cfg.get("gemini_api_key")
        )
    return state["agent"]

# Enable CORS for all routes
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp

@app.route("/api/status", methods=["GET", "OPTIONS"])
def get_status():
    if request.method == "OPTIONS":
        return "", 204
    try:
        agent = get_agent()
        res = agent.service.users().messages().list(userId='me', q='is:unread', maxResults=50).execute()
        msgs = res.get('messages', [])
        state["unread_count"] = len(msgs)
    except Exception as e:
        log(f"Error fetching unread count: {e}")

    return jsonify({
        "online": True,
        "unread_count": state["unread_count"],
        "latest_remark": state["latest_remark"],
        "is_scanning": state["is_scanning"],
        "last_scan_time": state["last_scan_time"],
        "last_results_count": len(state["last_results"])
    })

@app.route("/api/prompt", methods=["POST", "OPTIONS"])
def handle_prompt():
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or {}
    user_prompt = data.get("prompt", "").strip()
    selected_id = data.get("selected_id") or data.get("message_id") or data.get("id")
    selected_sender = data.get("selected_sender") or data.get("sender")
    if not user_prompt:
        return jsonify({"error": "Empty prompt"}), 400

    cfg = load_config()
    try:
        agent = get_agent()
        state["is_scanning"] = True
        log(f"Handling prompt from Gmail widget: '{user_prompt}' (selected_id: {selected_id}, selected_sender: {selected_sender})")
        remark, results = agent.handle_user_prompt(
            user_prompt,
            auto_delete=cfg.get("auto_delete", True),
            max_results=cfg.get("max_scan", 10),
            grace_period_minutes=cfg.get("grace_period_minutes", 60),
            selected_email_id=selected_id,
            selected_email_sender=selected_sender
        )
        state["latest_remark"] = remark
        if results:
            state["last_results"] = results
            state["last_scan_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["is_scanning"] = False
        log(f"Avatar remark: '{remark}'")
        return jsonify({
            "remark": remark,
            "results": results,
            "sender_groups": getattr(agent, "last_sender_groups", [])
        })
    except Exception as e:
        state["is_scanning"] = False
        err_msg = f"Sorry, I encountered an error: {e}"
        log(err_msg)
        return jsonify({"remark": err_msg, "error": str(e)}), 500

@app.route("/api/draft", methods=["POST", "OPTIONS"])
def create_draft():
    if request.method == "OPTIONS":
        return "", 204
    try:
        agent = get_agent()
        log("Draft generation requested via API.")
        remark, results = agent.handle_user_prompt("make a draft reply")
        state["latest_remark"] = remark
        if results:
            state["last_results"] = results
        return jsonify({
            "remark": remark,
            "results": results
        })
    except Exception as e:
        log(f"Draft generation failed: {e}")
        return jsonify({"remark": f"Draft generation failed: {e}", "error": str(e)}), 500

@app.route("/api/scan", methods=["POST", "OPTIONS"])
def run_scan():
    if request.method == "OPTIONS":
        return "", 204
    cfg = load_config()
    try:
        agent = get_agent()
        state["is_scanning"] = True
        log("Manual scan triggered from Gmail avatar widget.")
        results = agent.process_unread_emails(
            auto_delete=cfg.get("auto_delete", True),
            max_results=cfg.get("max_scan", 10),
            grace_period_minutes=cfg.get("grace_period_minutes", 60),
            purge_history=True
        )
        state["last_results"] = results
        state["last_scan_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["is_scanning"] = False

        if not results:
            remark = "I scanned your inbox and found 0 unread emails. Everything is up to date!"
        else:
            historical_purged = sum(1 for r in results if r.get('is_historical_purge'))
            active_results = [r for r in results if not r.get('is_historical_purge')]
            intact = sum(1 for r in active_results if r.get('is_intact'))
            triaged = [r for r in active_results if not r.get('is_intact')]
            drafts = sum(1 for r in triaged if r.get('draft'))
            trashed = sum(1 for r in triaged if r.get('category') == 'Trash')
            categorized = len(triaged) - trashed

            parts = []
            if historical_purged > 0:
                parts.append(f"Deleted {historical_purged} previous email{'s' if historical_purged > 1 else ''} from blocked senders.")
            if intact > 0:
                parts.append(f"Kept {intact} newly arrived email{'s' if intact > 1 else ''} intact on top of your inbox for 1 hour.")
            if triaged:
                parts.append(f"Processed {len(triaged)} older emails: {categorized} categorized, {drafts} drafted, and {trashed} trashed.")
            remark = " ".join(parts) or "Scan complete!"

        state["latest_remark"] = remark
        log(f"Scan finished: {remark}")
        return jsonify({
            "remark": remark,
            "results": results
        })
    except Exception as e:
        state["is_scanning"] = False
        log(f"Scan failed: {e}")
        return jsonify({"remark": f"Scan failed: {e}", "error": str(e)}), 500

@app.route("/api/purge_blocked", methods=["POST", "OPTIONS"])
def purge_blocked():
    if request.method == "OPTIONS":
        return "", 204
    try:
        agent = get_agent()
        log("Purging all previous emails from blocked senders...")
        purge_res = agent.purge_blocked_senders_history()
        count = purge_res["total_purged"]
        senders_str = ", ".join(agent.delete_senders) if agent.delete_senders else "None configured"
        if count > 0:
            remark = f"Deleted {count} previous email{'s' if count > 1 else ''} from blocked senders ({senders_str}). All past spam has been moved to Trash!"
        else:
            remark = f"Checked your entire mailbox for blocked senders ({senders_str}): 0 previous emails found. Mailbox is clean!"

        state["latest_remark"] = remark
        log(remark)
        return jsonify({
            "remark": remark,
            "total_purged": count,
            "per_sender": purge_res["per_sender"],
            "details": purge_res["details"]
        })
    except Exception as e:
        log(f"Purge failed: {e}")
        return jsonify({"remark": f"Purge failed: {e}", "error": str(e)}), 500

@app.route("/api/folder_synopsis", methods=["POST", "OPTIONS"])
def folder_synopsis():
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or {}
    folder_query = data.get("query", "in:inbox")
    max_scan = data.get("max_scan", 20)
    try:
        agent = get_agent()
        log(f"Reading folder emails for query '{folder_query}'...")
        emails = agent.read_folder_emails(folder_query=folder_query, max_results=max_scan)
        total = len(emails)
        action_count = sum(1 for e in emails if e.get("synopsis", {}).get("urgency") == "Urgent" or "no action" not in e.get("synopsis", {}).get("action_item", "").lower())
        info_count = total - action_count
        remark = f"Analyzed {total} emails in folder '{folder_query}'. {action_count} require action, {info_count} informational."
        state["latest_remark"] = remark
        return jsonify({
            "remark": remark,
            "total": total,
            "emails": emails
        })
    except Exception as e:
        log(f"Folder synopsis failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/sort_sender", methods=["POST", "OPTIONS"])
def api_sort_sender():
    """Sorts emails sender-wise, creates Gmail sender labels, and returns sender groupings."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or {}
    target_sender = data.get("target_sender", None)
    folder_query = data.get("query")
    if not folder_query:
        if target_sender:
            folder_query = f"from:{target_sender} -in:trash -in:spam"
        else:
            folder_query = "in:inbox"
    max_scan = data.get("max_scan", 30)
    create_labels = data.get("create_labels", True)
    folder_prefix = data.get("folder_prefix", None)
    try:
        agent = get_agent()
        log(f"Sorting emails sender-wise for query '{folder_query}' (target: {target_sender})...")
        res = agent.sort_emails_by_sender(
            folder_query=folder_query,
            max_results=max_scan,
            create_labels=create_labels,
            folder_prefix=folder_prefix,
            target_sender=target_sender
        )
        state["latest_remark"] = res["remark"]
        if res.get("details"):
            state["last_results"] = res["details"]
        return jsonify(res)
    except Exception as e:
        log(f"Sender-wise sorting failed: {e}")
        return jsonify({"error": str(e), "remark": f"Sender sorting failed: {e}"}), 500

@app.route("/api/block_sender", methods=["POST", "OPTIONS"])
def api_block_sender():
    """Blocks a sender, adds to config blacklist, and purges all existing emails from them."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or {}
    sender_target = data.get("sender") or data.get("target") or data.get("email") or ""
    selected_id = data.get("selected_id") or data.get("message_id")
    try:
        agent = get_agent()
        log(f"Block sender requested for '{sender_target}' (selected_id: {selected_id})...")
        res = agent.block_sender(sender_target, selected_email_id=selected_id, purge_now=True)
        state["latest_remark"] = res["remark"]
        return jsonify(res)
    except Exception as e:
        log(f"Block sender failed: {e}")
        return jsonify({"error": str(e), "remark": f"Block sender failed: {e}"}), 500

@app.route("/api/unblock_sender", methods=["POST", "OPTIONS"])
def api_unblock_sender():
    """Unblocks a sender and removes them from the blacklist."""
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or {}
    sender_target = data.get("sender") or data.get("target") or data.get("email") or ""
    try:
        agent = get_agent()
        log(f"Unblock sender requested for '{sender_target}'...")
        res = agent.unblock_sender(sender_target)
        state["latest_remark"] = res["remark"]
        return jsonify(res)
    except Exception as e:
        log(f"Unblock sender failed: {e}")
        return jsonify({"error": str(e), "remark": f"Unblock sender failed: {e}"}), 500

@app.route("/api/blocked_senders", methods=["GET", "OPTIONS"])
def api_blocked_senders():
    """Lists currently blocked senders."""
    if request.method == "OPTIONS":
        return "", 204
    try:
        agent = get_agent()
        res = agent.list_blocked_senders()
        return jsonify(res)
    except Exception as e:
        log(f"List blocked senders failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/synopsis", methods=["POST", "OPTIONS"])
def single_synopsis():
    if request.method == "OPTIONS":
        return "", 204
    data = request.get_json(silent=True) or {}
    sender = data.get("sender", "Unknown")
    subject = data.get("subject", "No Subject")
    snippet = data.get("snippet", "")
    msg_id = data.get("id") or data.get("message_id")
    attachments = data.get("attachments", [])
    try:
        agent = get_agent()
        body = data.get("body", "")
        # If msg_id provided and no attachments passed, fetch full email and attachments
        if msg_id and not attachments:
            try:
                msg = agent.service.users().messages().get(userId='me', id=msg_id, format='full').execute()
                full_body, atts = agent.extract_email_body_and_attachments(msg_id, msg.get('payload', {}))
                if full_body:
                    body = full_body
                if atts:
                    attachments = atts
            except Exception as e:
                log(f"Warning: Could not fetch attachments for {msg_id}: {e}")

        synopsis = agent.generate_synopsis(sender, subject, snippet, body=body, attachments=attachments)
        return jsonify({"synopsis": synopsis})
    except Exception as e:
        log(f"Synopsis generation failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/read_file", methods=["POST", "OPTIONS"])
def api_read_file():
    """Reads and analyzes any uploaded file or local file path (.txt, .docx, .xlsx, .pdf, .png, .gif, binary)."""
    if request.method == "OPTIONS":
        return "", 204
    try:
        agent = get_agent()
        file_res = None

        # Check if file uploaded via multipart form data
        if 'file' in request.files:
            uploaded = request.files['file']
            fn = uploaded.filename or "uploaded.bin"
            file_bytes = uploaded.read()
            log(f"Received file upload '{fn}' ({len(file_bytes)} bytes) for AI analysis.")
            file_res = agent.file_reader.read_bytes(file_bytes, filename=fn)
        else:
            # Check JSON payload for filepath or base64 data
            data = request.get_json(silent=True) or {}
            filepath = data.get("filepath", "").strip()
            b64_data = data.get("base64", "")
            fn = data.get("filename", "file.bin")

            if filepath:
                log(f"Reading local file path '{filepath}'...")
                file_res = agent.file_reader.read_file(filepath)
            elif b64_data:
                import base64
                file_bytes = base64.b64decode(b64_data)
                log(f"Received base64 file '{fn}' ({len(file_bytes)} bytes) for AI analysis.")
                file_res = agent.file_reader.read_bytes(file_bytes, filename=fn)
            else:
                return jsonify({"error": "No file, filepath, or base64 payload provided."}), 400

        remark = f"I've analyzed '{file_res['filename']}' ({file_res['file_type']}, {file_res['size_human']})! {file_res['summary']}"
        state["latest_remark"] = remark
        log(f"File analysis complete: {remark}")

        return jsonify({
            "remark": remark,
            "file": file_res
        })
    except Exception as e:
        log(f"Error reading file: {e}")
        return jsonify({"error": str(e), "remark": f"Failed to analyze file: {e}"}), 500

@app.route("/api/logs", methods=["GET", "OPTIONS"])
def get_logs():
    if request.method == "OPTIONS":
        return "", 204
    if not os.path.exists(LOG_FILE):
        return jsonify({"logs": []})
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return jsonify({"logs": lines[-40:]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Background autonomous polling thread
def background_worker():
    time.sleep(5) # Wait for server to boot
    log("Autonomous background email worker active.")
    while True:
        try:
            cfg = load_config()
            interval = cfg.get("poll_interval_seconds", 300)
            agent = get_agent()
            
            # Check for unread emails automatically
            res = agent.service.users().messages().list(userId='me', q='is:unread', maxResults=cfg.get("max_scan", 10)).execute()
            unread_msgs = res.get('messages', [])
            state["unread_count"] = len(unread_msgs)
            
            if unread_msgs and not state["is_scanning"]:
                log(f"[Background Worker] Found {len(unread_msgs)} unread email(s). Auto-triaging...")
                state["is_scanning"] = True
                results = agent.process_unread_emails(
                    auto_delete=cfg.get("auto_delete", True),
                    max_results=cfg.get("max_scan", 10),
                    grace_period_minutes=cfg.get("grace_period_minutes", 60)
                )
                state["last_results"] = results
                state["last_scan_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                state["is_scanning"] = False

                if results:
                    drafts = sum(1 for r in results if r.get('draft'))
                    trashed = sum(1 for r in results if r.get('category') == 'Trash')
                    categorized = len(results) - trashed
                    remark = f"Auto-triaged inbox: {categorized} categorized, {drafts} reply drafted, {trashed} spam cleaned."
                    state["latest_remark"] = remark
                    log(f"[Background Worker] {remark}")
        except Exception as e:
            state["is_scanning"] = False
            log(f"[Background Worker Warning]: {e}")

        cfg = load_config()
        sleep_sec = cfg.get("poll_interval_seconds", 300)
        time.sleep(sleep_sec)

if __name__ == "__main__":
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    log("==========================================")
    log("🚀 AI Gmail Avatar Server Starting on http://127.0.0.1:5000")
    log("Ready to connect with Gmail Chrome/Edge Extension.")
    log("==========================================")

    # Start background autonomous triage loop
    worker_thread = threading.Thread(target=background_worker, daemon=True)
    worker_thread.start()

    try:
        app.run(host="127.0.0.1", port=5000, debug=False)
    finally:
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass

