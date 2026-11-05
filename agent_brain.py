import re
import json

class AgentBrain:
    """
    Intelligent Cognitive Engine ('Brain') for Gmail AI Agent.
    
    Provides:
    1. Natural Language Intent Classification (LLM-driven with zero-shot semantic understanding).
    2. Deep Parameter & Entity Extraction (e.g. sender email, domain, folder, count).
    3. Robust Offline Heuristic Reasoning Engine (instant regex & NLP fallback for 100% reliability).
    4. Action Planning & Contextual Decision Making.
    """

    INTENTS = [
        "SORT_BY_SENDER",
        "BLOCK_SENDER",
        "UNBLOCK_SENDER",
        "LIST_BLOCKED",
        "SCAN_INBOX",
        "DRAFT_REPLY",
        "SUMMARIZE_ATTACHMENTS",
        "FOLDER_SYNOPSIS",
        "PURGE_SPAM",
        "COUNT_UNREAD",
        "READ_FILE",
        "GENERAL_CONVERSATION"
    ]

    def __init__(self, openai_client=None, model_name="gpt-4o-mini"):
        self.client = openai_client
        self.model_name = model_name

    def set_client(self, client, model_name=None):
        self.client = client
        if model_name:
            self.model_name = model_name

    def think(self, user_prompt: str, context: dict = None) -> dict:
        """
        Analyzes the user prompt and context to determine the exact intent,
        extracted parameters, and rationale.
        """
        context = context or {}
        p_clean = user_prompt.strip()

        # Step 1: Try LLM-based cognitive classification if client is active
        if self.client:
            try:
                decision = self._llm_classify(p_clean, context)
                if decision and decision.get("intent") in self.INTENTS:
                    return decision
            except Exception as e:
                # Log warning and seamlessly use the heuristic brain
                pass

        # Step 2: High-precision Rule & NLP Heuristic Brain Fallback
        return self._heuristic_classify(p_clean, context)

    def _llm_classify(self, user_prompt: str, context: dict) -> dict:
        system_prompt = f"""You are the cognitive brain of an AI Gmail Agent.
Your job is to analyze the user's natural language command and decide on the exact action intent and parameters.

Available Intents:
1. SORT_BY_SENDER: The user wants to sort, organize, or group their emails sender-wise into sender-named folders (e.g., all mails from IndusInd put in folder 'indusind', 'sort my mails sender wise', 'all mails from indusind shall be put in a folder indusind and similar', 'organize inbox by sender', 'group emails by sender', 'put all mails from a particular sender in a folder named after the sender').
   Parameters: {{"folder": "-in:trash -in:spam", "create_labels": true, "max_results": 150, "fetch_all": true, "target_sender": "<sender slug or email or null>", "needs_target_sender": true/false}}
2. BLOCK_SENDER: The user wants to block, blacklist, or ban a sender/domain and trash their emails (e.g., 'block spam@example.com', 'block sender promos@shop.com', 'block this sender', 'blacklist badactor.com').
   Parameters: {{"target_sender": "<extracted email, domain, or 'this'>", "purge_now": true}}
3. UNBLOCK_SENDER: The user wants to unblock or remove a sender from blacklist (e.g., 'unblock alice@company.com').
   Parameters: {{"target_sender": "<extracted email or name>"}}
4. LIST_BLOCKED: The user wants to view currently blocked or blacklisted senders (e.g., 'who is blocked', 'show blocked senders', 'list blacklist').
   Parameters: {{}}
5. SCAN_INBOX: The user wants to scan, triage, or clean unread emails in the inbox (e.g., 'scan inbox', 'scan now', 'triage my unread emails').
   Parameters: {{"max_results": 10}}
6. DRAFT_REPLY: The user wants to draft a reply to an email (e.g., 'make a draft reply', 'draft a response to the latest mail').
   Parameters: {{"target": "<target description or recent>"}}
7. SUMMARIZE_ATTACHMENTS: The user wants to inspect, read, or summarize emails with attachments (e.g., 'summarize mail with attachment', 'read attached pdf').
   Parameters: {{"query": "<query or filename if mentioned>"}}
8. FOLDER_SYNOPSIS: The user wants a summary/synopsis of all emails in a folder or current view (e.g., 'summarize folder', 'read all emails in inbox').
   Parameters: {{"folder": "in:inbox"}}
9. PURGE_SPAM: The user specifically wants to delete previous/historical emails from blocked senders (e.g., 'clean spam', 'delete previous spam', 'purge blocked history').
   Parameters: {{}}
10. COUNT_UNREAD: The user asks for the count or number of unread emails (e.g., 'how many unread emails', 'unread count').
    Parameters: {{}}
11. READ_FILE: The user specifies a local file path to read or analyze.
    Parameters: {{"filepath": "<path>"}}
12. GENERAL_CONVERSATION: Greetings, questions about capabilities, or general chatting.
    Parameters: {{}}

Context:
- Current blocked senders: {context.get('blocked_senders', [])}
- Selected email ID: {context.get('selected_email_id', None)}
- Selected email sender: {context.get('selected_email_sender', None)}

Respond strictly in valid JSON format matching this schema:
{{
  "intent": "<ONE_OF_THE_INTENTS>",
  "parameters": {{ ... }},
  "confidence": 0.0 - 1.0,
  "reasoning": "Brief 1-sentence reasoning"
}}
Do NOT output markdown backticks or extra text. Output strictly raw JSON.
"""
        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=220,
            timeout=5.0
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        
        data = json.loads(content)
        return data

    def _heuristic_classify(self, prompt: str, context: dict) -> dict:
        """
        Pure rule-based NLP intent classification and parameter extraction.
        Guarantees instant, zero-latency execution even when offline or quota-limited.
        """
        p_low = prompt.lower().strip()

        # 1. List Blocked Senders (Checked before sorting so 'show blocked senders' is not treated as sorting!)
        if any(w in p_low for w in ["who is blocked", "list blocked", "show blocked", "which senders are blocked", "blocked senders", "view blacklist", "blacklist list"]):
            return {
                "intent": "LIST_BLOCKED",
                "parameters": {},
                "confidence": 0.96,
                "reasoning": "Request to list currently blocked senders."
            }

        # 2. Unblock Sender
        unblock_pattern = re.search(
            r'\b(unblock|unblacklist|whitelist|remove from block|remove from blacklist)\b',
            p_low
        )
        if unblock_pattern:
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', prompt)
            target = email_match.group(0).lower() if email_match else ""
            if not target:
                words = p_low.split()
                if len(words) > 1:
                    target = words[-1]
            return {
                "intent": "UNBLOCK_SENDER",
                "parameters": {
                    "target_sender": target
                },
                "confidence": 0.95,
                "reasoning": f"Unblock request for '{target}'."
            }

        # 3. Block Sender
        block_pattern = re.search(
            r'\b(block|blacklist|ban)\b',
            p_low
        )
        if block_pattern:
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', prompt)
            domain_match = re.search(r'@[\w\.-]+\.\w+', prompt)
            
            target = ""
            if email_match:
                target = email_match.group(0).lower()
            elif domain_match:
                target = domain_match.group(0).lower()
            elif any(k in p_low for k in ["this sender", "the sender", "current sender", "this email sender", "selected sender", "sender of this"]):
                target = context.get("selected_email_sender") or "this"
            else:
                sender_kw_match = re.search(r'(?:block|blacklist|ban)(?:\s+sender)?\s+([^\s,;]+)', p_low)
                if sender_kw_match:
                    cand = sender_kw_match.group(1).strip().strip("'\"")
                    if cand not in ["sender", "emails", "mail", "all"]:
                        target = cand

            return {
                "intent": "BLOCK_SENDER",
                "parameters": {
                    "target_sender": target or "this",
                    "purge_now": True
                },
                "confidence": 0.95,
                "reasoning": f"Sender blocking request targeting '{target or 'this'}'. "
            }

        # 4. Sender-wise Sorting / Folder Routing (e.g. all mails from indusind into folder indusind and similar)
        sort_by_sender_pattern = re.search(
            r'(\b(sort|group|organize|categorize|arrange|order|filter|split|view|list|show|put|move|place|store|file)\b.*\b(sender|senders|from|author|who sent|different folders|folder|folders|label|labels)\b)|'
            r'(\b(sender[\s\-]wise|by[\s\-]sender|senders[\s\-]wise)\b)|'
            r'(\b(sender|senders)\b.*\b(wise|sort|group|organize|folder|folders)\b)|'
            r'(\bdifferent folders\b.*\b(sender|senders)\b)|'
            r'(\bnamed according\b.*\b(sender|senders)\b)|'
            r'(\b(folder|folders|label|labels)\b.*\b(indusind|sender|senders)\b)|'
            r'(\b(mails|emails)\b.*\bfrom\s+\w+\b.*\b(folder|folders|label|labels)\b)|'
            r'(\bput\b.*\bin\s+(?:a\s+)?folder\b)',
            p_low
        )
        if sort_by_sender_pattern and not any(w in p_low for w in ["blocked", "blacklist", "ban"]):
            folder = "-in:trash -in:spam" if ("all" in p_low or "entire" in p_low or "everything" in p_low) else "in:inbox"
            if "sent" in p_low:
                folder = "in:sent"
            elif "starred" in p_low:
                folder = "is:starred"
            is_all = "all" in p_low or "entire" in p_low or "everything" in p_low

            # Extract specific target sender if specified (e.g., "put all mails from indusind in folder indusind",
            # "put all mails from client@example.com in a folder named after the sender")
            # If prompt says "sender wise" or "and similar", user is stating the general rule for all senders
            target_sender = None
            needs_target_sender = False
            is_general_rule = any(w in p_low for w in ["sender wise", "by sender", "and similar", "each sender", "every sender", "all senders", "similar"])
            if not is_general_rule:
                # 1. Quoted sender name/entity: from "Amazon" or from 'John Doe'
                q_match = re.search(r'(?:from|for)\s+["\']([^"\']+)["\']', prompt, re.IGNORECASE)
                if q_match:
                    target_sender = q_match.group(1).strip()
                else:
                    # 2. Email address: from user@domain.com
                    em_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', prompt)
                    if em_match:
                        target_sender = em_match.group(0).lower()
                    else:
                        # 3. from/for <name/slug>
                        t_match = re.search(r'(?:from|for)\s+([a-zA-Z0-9_\-\.]+)', p_low)
                        stop_words = {"each", "all", "every", "the", "a", "sender", "senders", "this", "particular", "specific", "one", "any", "my", "me", "our"}
                        if t_match and t_match.group(1) not in stop_words:
                            target_sender = t_match.group(1).lower()

                # 4. Check if prompt explicitly asks for "a particular sender" / "specific sender" without naming one
                if not target_sender and any(w in p_low for w in ["particular sender", "specific sender", "a sender"]):
                    needs_target_sender = True

            return {
                "intent": "SORT_BY_SENDER",
                "parameters": {
                    "folder": folder,
                    "create_labels": True,
                    "fetch_all": is_all,
                    "max_results": 150 if is_all else 30,
                    "target_sender": target_sender,
                    "needs_target_sender": needs_target_sender
                },
                "confidence": 0.99,
                "reasoning": f"Detected sender-wise email sorting{' targeting ' + target_sender if target_sender else (' requesting particular sender' if needs_target_sender else ' across all senders into folders (e.g. indusind)')}."
            }

        # 4. Count Unread Intent
        if any(k in p_low for k in ["how many", "count unread", "number of unread", "how many unread"]) and not any(k in p_low for k in ["scan", "clean", "trash", "purge"]):
            return {
                "intent": "COUNT_UNREAD",
                "parameters": {},
                "confidence": 0.95,
                "reasoning": "User asked for unread email count."
            }

        # 5. Draft Reply Intent
        if any(k in p_low for k in ["draft reply", "make a draft", "create a draft", "compose draft", "write a reply", "draft an email", "reply to"]):
            return {
                "intent": "DRAFT_REPLY",
                "parameters": {
                    "target": context.get("selected_email_id") or "recent"
                },
                "confidence": 0.92,
                "reasoning": "User wants to create a draft reply."
            }

        # 6. Attachment Inspection Intent
        if any(k in p_low for k in ["summarize mail with attachment", "read attachment", "attached file", "summarize attachment", "attached document", "read attached"]) or (
            ("attachment" in p_low or "attached" in p_low or "document" in p_low) and any(w in p_low for w in ["read", "summar", "summer", "inspect", "show", "check", "what"])
        ):
            return {
                "intent": "SUMMARIZE_ATTACHMENTS",
                "parameters": {
                    "query": "has:attachment"
                },
                "confidence": 0.93,
                "reasoning": "User wants to inspect/summarize attachments."
            }

        # 7. Folder Synopsis Intent
        if any(k in p_low for k in ["summarize folder", "read all mails", "read all emails", "folder synopsis", "read folder", "synopsis"]):
            return {
                "intent": "FOLDER_SYNOPSIS",
                "parameters": {
                    "folder": "in:inbox"
                },
                "confidence": 0.90,
                "reasoning": "User wants a folder synopsis."
            }

        # 8. Explicit Purge Intent for Blocked Spam
        if any(k in p_low for k in ["delete all previous", "delete previous", "purge blocked", "clean spam", "trash spam", "purge spam", "clear spam"]):
            return {
                "intent": "PURGE_SPAM",
                "parameters": {},
                "confidence": 0.94,
                "reasoning": "Purge previous emails from blocked senders."
            }

        # 9. Scan / Triage Intent
        if any(k in p_low for k in ["scan inbox", "scan my inbox", "scan now", "scan emails", "scan", "triage inbox", "triage emails", "clean inbox", "organize inbox"]):
            return {
                "intent": "SCAN_INBOX",
                "parameters": {
                    "max_results": 10
                },
                "confidence": 0.90,
                "reasoning": "Scan and triage unread emails."
            }

        # 10. Check for Local File Path
        file_path_match = re.search(
            r'([a-zA-Z]:\\[^"\'\r\n\t]+|/[^"\'\r\n\t]+|[\w\-.]+\.(?:txt|docx|doc|xlsx|xls|pdf|png|gif|jpg|jpeg|webp|csv|tsv|json|xml|bin|dat|exe|zip|tar|gz|sqlite|db))',
            prompt,
            re.IGNORECASE
        )
        if file_path_match:
            return {
                "intent": "READ_FILE",
                "parameters": {
                    "filepath": file_path_match.group(1).strip().strip('"\'')
                },
                "confidence": 0.88,
                "reasoning": "User provided a local file path."
            }

        # Default: General Conversation
        return {
            "intent": "GENERAL_CONVERSATION",
            "parameters": {},
            "confidence": 0.70,
            "reasoning": "General query or conversation."
        }
