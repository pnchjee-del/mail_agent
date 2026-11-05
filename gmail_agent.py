import os
import sys
import re
import json
import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from openai import OpenAI
from file_reader import FileReader, human_size
from agent_brain import AgentBrain

# Required Gmail permissions for reading, categorizing (labels), drafting, and trashing
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify'
]

VALID_CATEGORIES = ['Work', 'Finance', 'Promotions', 'Personal', 'Support']

MULTI_PART_TLDS = (
    '.co.in', '.net.in', '.org.in', '.gov.in', '.ac.in', '.res.in', '.edu.in', '.mil.in',
    '.co.uk', '.org.uk', '.me.uk', '.ltd.uk', '.plc.uk', '.net.uk', '.sch.uk', '.ac.uk', '.gov.uk',
    '.com.au', '.net.au', '.org.au', '.edu.au', '.gov.au',
    '.co.nz', '.net.nz', '.org.nz',
    '.co.jp', '.ne.jp', '.ac.jp', '.go.jp',
    '.com.br', '.net.br', '.org.br',
    '.com.sg', '.edu.sg', '.gov.sg', '.net.sg',
    '.com.my', '.net.my', '.org.my',
    '.co.za', '.net.za', '.org.za',
    '.com.mx', '.org.mx',
    '.com.tr', '.net.tr',
    '.bank.in'
)

PUBLIC_WEBMAIL_DOMAINS = {
    'gmail.com', 'googlemail.com', 'yahoo.com', 'yahoo.co.in', 'yahoo.co.uk',
    'ymail.com', 'hotmail.com', 'outlook.com', 'live.com', 'msn.com',
    'icloud.com', 'me.com', 'mac.com', 'aol.com', 'proton.me', 'protonmail.com',
    'zoho.com', 'mail.com', 'gmx.com', 'rediffmail.com'
}

DELIVERY_RELAY_DOMAINS = {
    'sendgrid.net', 'sendgrid.com', 'mailchimp.com', 'billdesk.com', 'razorpay.com',
    'amazonses.com', 'cmail19.com', 'cmail20.com', 'mandrillapp.com', 'hubspot.com',
    'salesforce.com', 'exacttarget.com', 'intercom-mail.com', 'zendesk.com', 'freshdesk.com',
    'sparkpostmail.com', 'mailgun.org', 'mailgun.com', 'postmarkapp.com', 'campaignmonitor.com'
}

NAME_STOPWORDS = {
    'bank', 'ltd', 'limited', 'pvt', 'inc', 'corp', 'corporation', 'llc',
    'team', 'support', 'care', 'customer', 'service', 'services', 'official',
    'alerts', 'alert', 'notifications', 'notification', 'updates', 'update',
    'india', 'statement', 'statements', 'estatement', 'e-statement', 'netbanking',
    'cards', 'credit', 'card', 'debit', 'online', 'the', 'and'
}


class GmailAIAgent:
    def __init__(self, designated_senders=None, delete_senders=None, api_key=None, gemini_api_key=None,
                 use_omniroute=None, omniroute_base_url=None, omniroute_api_key=None, omniroute_model=None,
                 credentials_path='credentials.json', token_path='token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        
        # Filter out empty strings to avoid matching all senders
        self.designated_senders = [s.strip().lower() for s in (designated_senders or []) if s.strip()]
        self.delete_senders = [s.strip().lower() for s in (delete_senders or []) if s.strip()]
        self.last_sender_groups = []

        # Sender Folder Configuration (default empty prefix for clean folders like 'indusind', 'sbi', etc.)
        cfg_init = {}
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    cfg_init = json.load(f)
            except Exception:
                pass
        self.sender_folder_prefix = cfg_init.get("sender_folder_prefix", "")
        self.sender_folder_mappings = cfg_init.get("sender_folder_mappings", {
            "indusindbank": "indusind",
            "indusind": "indusind"
        })
        
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        self.use_omniroute = use_omniroute if use_omniroute is not None else (os.environ.get("USE_OMNIROUTE", "false").lower() == "true")
        self.omniroute_base_url = omniroute_base_url or os.environ.get("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
        self.omniroute_api_key = omniroute_api_key or os.environ.get("OMNIROUTE_API_KEY", "omniroute")
        self.omniroute_model = omniroute_model or os.environ.get("OMNIROUTE_MODEL", "auto")

        self.client = None
        self.model_name = "gpt-4o-mini"
        self._init_llm_client()
            
        self.file_reader = FileReader(openai_client=self.client)
        self.brain = AgentBrain(openai_client=self.client, model_name=self.model_name)
        self.creds = None
        self.service = None
        self.authenticate()

    def _init_llm_client(self):
        """Initializes client with OmniRoute, Gemini, or OpenAI."""
        if self.use_omniroute:
            try:
                self.client = OpenAI(
                    api_key=self.omniroute_api_key,
                    base_url=self.omniroute_base_url
                )
                self.model_name = self.omniroute_model
                if hasattr(self, 'brain') and self.brain:
                    self.brain.set_client(self.client, self.model_name)
                print(f"[AI Agent] Initialized OmniRoute client ({self.omniroute_base_url}, model={self.model_name}).")
                return
            except Exception as e:
                print(f"[AI Agent] Failed to init OmniRoute client: {e}")

        if self.gemini_api_key:
            try:
                self.client = OpenAI(
                    api_key=self.gemini_api_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
                )
                self.model_name = "gemini-2.5-flash"
                if hasattr(self, 'brain') and self.brain:
                    self.brain.set_client(self.client, self.model_name)
                return
            except Exception as e:
                print(f"[AI Agent] Failed to init Gemini client: {e}")

        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                self.model_name = "gpt-4o-mini"
                if hasattr(self, 'brain') and self.brain:
                    self.brain.set_client(self.client, self.model_name)
            except Exception as e:
                print(f"[AI Agent] Failed to init OpenAI client: {e}")

    def get_openai_client(self):
        """Returns the active LLM client, initializing lazily if needed."""
        if not self.client:
            self._init_llm_client()
        if not self.client:
            raise ValueError("No AI API key (OpenAI or Gemini) configured or functional.")
        self.file_reader.set_openai_client(self.client)
        if hasattr(self, 'brain') and self.brain:
            self.brain.set_client(self.client, self.model_name)
        return self.client

    def authenticate(self):
        """Authenticates with the Gmail API via OAuth2."""
        if not os.path.exists(self.credentials_path) and not os.path.exists(self.token_path):
            raise FileNotFoundError(
                f"OAuth credentials file '{self.credentials_path}' not found. "
                "Please download credentials.json from Google Cloud Console and place it in the application folder."
            )

        if os.path.exists(self.token_path):
            try:
                self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                print(f"[AI Agent] Cached token invalid or scope changed ({e}). Re-authenticating...")
                self.creds = None

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"[AI Agent] Failed to refresh token ({e}). Starting full OAuth flow...")
                    self.creds = None

            if not self.creds or not self.creds.valid:
                # If running in interactive terminal, prompt user for OAuth;
                # otherwise avoid hanging indefinitely
                try:
                    if sys.stdin and sys.stdin.isatty():
                        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                        self.creds = flow.run_local_server(port=0, prompt='consent')
                        with open(self.token_path, 'w', encoding='utf-8') as token:
                            token.write(self.creds.to_json())
                        self._sync_creds_to_extension()
                    else:
                        print("[AI Agent] Non-interactive environment detected. Skipping automatic browser OAuth popup to avoid blocking.")
                except Exception as e:
                    print(f"[AI Agent] OAuth authentication did not complete: {e}")
                    self.creds = None

        if self.creds and self.creds.valid:
            self.service = build('gmail', 'v1', credentials=self.creds)
        else:
            self.service = None
            print("[AI Agent] Note: Gmail API service not authenticated yet. Browser OAuth login required.")

    def get_or_create_label(self, label_name):
        """Retrieves or creates a Gmail label (folder)."""
        clean_name = label_name.strip()
        labels_resp = self.service.users().labels().list(userId='me').execute()
        labels = labels_resp.get('labels', [])
        for label in labels:
            if label.get('name', '').lower() == clean_name.lower():
                return label['id']

        created = self.service.users().labels().create(
            userId='me',
            body={'name': clean_name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
        ).execute()
        return created['id']

    def extract_email_body_and_attachments(self, msg_id, payload):
        """Recursively walks message payload parts to extract full email text and attachments.
        Reads .txt, .docx, .xlsx, .pdf, .png, .gif, and other binary files.
        """
        body_texts = []
        attachments = []

        def walk_part(part):
            if len(attachments) >= 4:
                return
            filename = part.get('filename', '').strip()
            mime_type = part.get('mimeType', '')
            body = part.get('body', {})
            att_id = body.get('attachmentId')
            data_b64 = body.get('data')

            # Check headers for filename and inline dispositions
            is_inline = False
            has_cid = False
            for h in part.get('headers', []):
                h_name = h.get('name', '').lower()
                h_val = h.get('value', '').lower()
                if h_name == 'content-disposition' and 'inline' in h_val:
                    is_inline = True
                if h_name == 'content-id':
                    has_cid = True
                if not filename and h_name in ['content-disposition', 'content-type']:
                    fn_match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)', h.get('value', ''), re.IGNORECASE)
                    if not fn_match:
                        fn_match = re.search(r'name=["\']?([^"\';\r\n]+)', h.get('value', ''), re.IGNORECASE)
                    if fn_match:
                        filename = fn_match.group(1).strip()

            # Ignore promotional newsletter inline layout images, social icons, and CID assets
            fn_low = filename.lower()
            doc_exts = ('.pdf', '.docx', '.xlsx', '.doc', '.xls', '.csv', '.txt', '.zip', '.rar', '.7z', '.json', '.xml', '.ppt', '.pptx', '.odt', '.ods')
            is_doc = any(fn_low.endswith(ext) for ext in doc_exts)

            if not is_doc and (is_inline or has_cid or fn_low.startswith('images/') or (fn_low and mime_type.startswith('image/') and not part.get('attachmentId'))):
                for sub_part in part.get('parts', []):
                    walk_part(sub_part)
                return

            # Infer filename if this part has an attachmentId or non-inline attachment
            if not filename and att_id and not is_inline:
                ext = mime_type.split('/')[-1] if '/' in mime_type else 'bin'
                filename = f"attachment_{msg_id[:6]}.{ext}"

            if filename:
                att_bytes = None
                try:
                    if att_id:
                        att_res = self.service.users().messages().attachments().get(
                            userId='me', messageId=msg_id, id=att_id
                        ).execute()
                        raw_data = att_res.get('data', '')
                        if raw_data:
                            # Pad base64 string to multiple of 4
                            raw_data += "=" * (-len(raw_data) % 4)
                            att_bytes = base64.urlsafe_b64decode(raw_data.encode('utf-8'))
                    elif data_b64:
                        data_b64_padded = data_b64 + ("=" * (-len(data_b64) % 4))
                        att_bytes = base64.urlsafe_b64decode(data_b64_padded.encode('utf-8'))

                    if att_bytes:
                        read_res = self.file_reader.read_bytes(att_bytes, filename=filename)
                        attachments.append(read_res)
                    else:
                        attachments.append({
                            "filename": filename,
                            "file_type": mime_type or "Attachment",
                            "size_human": human_size(body.get('size', 0)),
                            "summary": f"Attachment '{filename}' (not downloaded)",
                            "text_content": ""
                        })
                except Exception as e:
                    print(f"[AI Agent] Error downloading/reading attachment '{filename}': {e}")
                    attachments.append({
                        "filename": filename,
                        "file_type": mime_type or "Attachment",
                        "size_human": human_size(body.get('size', 0)),
                        "summary": f"Attachment '{filename}' ({e})",
                        "text_content": ""
                    })
            else:
                if mime_type == 'text/plain' and data_b64:
                    try:
                        data_b64_padded = data_b64 + ("=" * (-len(data_b64) % 4))
                        decoded = base64.urlsafe_b64decode(data_b64_padded.encode('utf-8')).decode('utf-8', errors='replace')
                        body_texts.append(decoded)
                    except Exception:
                        pass
                elif mime_type == 'text/html' and data_b64 and not body_texts:
                    try:
                        data_b64_padded = data_b64 + ("=" * (-len(data_b64) % 4))
                        decoded = base64.urlsafe_b64decode(data_b64_padded.encode('utf-8')).decode('utf-8', errors='replace')
                        clean_text = re.sub(r'<[^>]+>', ' ', decoded)
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                        body_texts.append(clean_text)
                    except Exception:
                        pass

            for sub_part in part.get('parts', []):
                walk_part(sub_part)

        walk_part(payload)
        full_body = "\n\n".join(body_texts).strip()
        return full_body, attachments

    def heuristic_classify(self, sender, subject, snippet, text=""):
        """Fast, robust keyword-based email classification for offline or quota-exceeded conditions."""
        combined = f"{sender} {subject} {snippet} {text}".lower()
        if any(k in combined for k in ["invoice", "payment", "receipt", "billing", "bank", "statement", "salary", "tax", "wire", "transfer", "pension", "$", "₹", "rs."]):
            return "Finance"
        if any(k in combined for k in ["sale", "discount", "deal", "promo", "off", "coupon", "shop", "newsletter", "unsubscribe", "digest"]):
            return "Promotions"
        if any(k in combined for k in ["support", "ticket", "helpdesk", "issue", "bug", "case", "service request", "troubleshoot"]):
            return "Support"
        if any(k in combined for k in ["project", "client", "team", "meeting", "agenda", "proposal", "contract", "deadline", "task", "report", "review", "deliverable"]):
            return "Work"
        return "Personal"

    def classify_email(self, sender, subject, snippet, body=None, attachments=None):
        """Uses AI to assign a folder/category, with instant heuristic fallback."""
        try:
            client = self.get_openai_client()
            content_preview = body if body else snippet
            att_info_str = ""
            if attachments:
                att_details = [f"- {a.get('filename')} ({a.get('file_type')}, {a.get('size_human')}): {a.get('summary', '')}" for a in attachments]
                att_info_str = "\nAttachments:\n" + "\n".join(att_details)

            prompt = f"""
Classify this email into exactly one category: 'Work', 'Finance', 'Promotions', 'Personal', or 'Support'.
Sender: {sender}
Subject: {subject}
Content: {content_preview[:1500]}
{att_info_str}

Respond with ONLY the category name.
"""
            response = client.chat.completions.create(
                model=getattr(self, 'model_name', 'gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                timeout=8.0
            )
            raw_category = response.choices[0].message.content.strip().strip("'\"").strip()
            
            # Match against valid categories
            for cat in VALID_CATEGORIES:
                if cat.lower() in raw_category.lower():
                    return cat
            return self.heuristic_classify(sender, subject, snippet, text=body or "")
        except Exception as e:
            print(f"[Warning] AI classification unavailable ({e}). Using intelligent heuristic classification.")
            return self.heuristic_classify(sender, subject, snippet, text=body or "")

    def generate_fallback_draft_text(self, sender, subject, snippet, body="", attachments=None):
        """Generates a professional, context-rich email reply when LLM is offline or rate-limited."""
        sender_name = sender.split('<')[0].replace('"', '').strip() or "there"
        att_mention = ""
        if attachments:
            att_names = ", ".join(f"'{a.get('filename', 'attachment')}'" for a in attachments)
            att_mention = f" I have also received the attached document(s) ({att_names}) and am currently reviewing them."

        comb = f"{subject} {snippet} {body}".lower()
        if any(w in comb for w in ["meeting", "call", "schedule", "sync", "zoom", "calendar"]):
            core = f"Thank you for reaching out regarding '{subject}'. I am reviewing my calendar and will follow up shortly to confirm our availability.{att_mention}"
        elif any(w in comb for w in ["invoice", "payment", "bill", "due date", "balance due", "remit"]):
            core = f"Thank you for the update regarding '{subject}'. I am verifying the details and will proceed with the necessary steps promptly.{att_mention}"
        elif any(w in comb for w in ["application", "licence", "license", "renewal", "form", "sarathi"]):
            core = f"Thank you for the update on the application '{subject}'. I have noted the details and am ensuring all required documentation is in order.{att_mention}"
        elif any(w in comb for w in ["attachment", "attached", "document", "file", "pdf", "docx"]):
            core = f"Thank you for sending this over. I have received your email and the attached files.{att_mention}"
        elif any(w in comb for w in ["question", "inquiry", "status", "update", "help"]):
            core = f"Thank you for reaching out regarding '{subject}'. I am looking into this matter and will get back to you with an update shortly.{att_mention}"
        else:
            core = f"Thank you for your email regarding '{subject}'.{att_mention} I am looking into this and will follow up with you as soon as possible."

        return f"Hello {sender_name},\n\n{core}\n\nPlease let me know if you need any additional information in the meantime.\n\nBest regards,\n[Your Name]"

    def draft_reply(self, message_id, thread_id, sender, subject, snippet, body=None, attachments=None):
        """Generates a contextual reply and saves it to Gmail Drafts, addressing any attachments."""
        body_text = None
        clean_subject = subject if subject.lower().startswith('re:') else f"Re: {subject}"

        try:
            client = self.get_openai_client()
            content_preview = body if body else snippet
            att_info_str = ""
            if attachments:
                att_details = [f"- File '{a.get('filename')}' ({a.get('file_type')}): {a.get('summary', '')}" for a in attachments]
                att_info_str = "\nAttached Files in Message:\n" + "\n".join(att_details)

            prompt = f"""
Write a professional, concise email reply to the following message. If the email contains attachments, acknowledge and reference them appropriately.
Sender: {sender}
Subject: {subject}
Content: {content_preview[:2000]}
{att_info_str}
"""
            response = client.chat.completions.create(
                model=getattr(self, 'model_name', 'gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                timeout=6.0
            )
            body_text = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[AI Agent] LLM draft generation unavailable ({e}). Using intelligent heuristic fallback.")
            body_text = self.generate_fallback_draft_text(sender, subject, snippet, body=body or "", attachments=attachments)

        if not body_text:
            body_text = self.generate_fallback_draft_text(sender, subject, snippet, body=body or "", attachments=attachments)

        try:
            message = MIMEText(body_text, 'plain', 'utf-8')
            message['to'] = sender
            message['subject'] = clean_subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            draft_body = {
                'message': {
                    'threadId': thread_id,
                    'raw': raw
                }
            }
            draft_res = self.service.users().drafts().create(userId='me', body=draft_body).execute()
            print(f"[AI Agent] Successfully created draft reply for {sender} in Gmail Drafts (ID: {draft_res.get('id')}).")
            return {
                "id": draft_res.get('id'),
                "to": sender,
                "subject": clean_subject,
                "preview": body_text[:160] + "..." if len(body_text) > 160 else body_text,
                "body": body_text
            }
        except Exception as e:
            print(f"[Error] Failed to create draft in Gmail: {e}")
            return None

    def generate_synopsis(self, sender, subject, snippet, body=None, attachments=None):
        """Generates an executive, structured synopsis for an email and its attachments."""
        text_content = body if body else snippet
        att_section = ""
        if attachments:
            att_summaries = []
            for a in attachments:
                att_summaries.append(f"- Attached '{a.get('filename')}' ({a.get('file_type')}, {a.get('size_human')}): {a.get('summary', '')}")
                if a.get('key_points'):
                    att_summaries.append("  Key Points: " + " | ".join(a.get('key_points')[:3]))
                if a.get('text_content'):
                    att_summaries.append(f"  Content Preview: {a.get('text_content')[:1800]}")
            att_section = "\n\nATTACHED DOCUMENTS & FILES:\n" + "\n".join(att_summaries)

        try:
            client = self.get_openai_client()
            prompt = f"""You are an elite executive email assistant. Analyze this email and any attached documents/files to generate an accurate, razor-sharp synopsis.
Sender: {sender}
Subject: {subject}
Content: {text_content[:2500]}{att_section}

Respond in strictly valid JSON format with this exact schema (no markdown formatting, no backticks):
{{
  "tldr": "1 or 2 concise, informative sentences summarizing the core message and highlighting any attached documents.",
  "key_points": [
    "Key highlight or takeaway 1",
    "Key highlight or takeaway 2"
  ],
  "action_item": "Specific action required by the reader, or 'No action needed (Informational)'",
  "urgency": "Urgent" | "Normal" | "Low",
  "category": "Work" | "Finance" | "Promotions" | "Personal" | "Support"
}}
"""
            resp = client.chat.completions.create(
                model=getattr(self, 'model_name', 'gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=400,
                timeout=6.0
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            import json as json_lib
            parsed = json_lib.loads(raw)
            return {
                "tldr": parsed.get("tldr", f"{subject} from {sender}"),
                "key_points": parsed.get("key_points", [snippet[:120]]),
                "action_item": parsed.get("action_item", "No action needed (Informational)"),
                "urgency": parsed.get("urgency", "Normal"),
                "category": parsed.get("category", "Work"),
                "attachments": [
                    {
                        "filename": a.get("filename"),
                        "file_type": a.get("file_type"),
                        "size_human": a.get("size_human"),
                        "summary": a.get("summary"),
                        "key_points": a.get("key_points", [])
                    }
                    for a in (attachments or [])
                ]
            }
        except Exception as e:
            # High-precision heuristic fallback incorporating extracted document contents
            t_low = f"{subject} {snippet}".lower()
            if attachments:
                for a in attachments:
                    t_low += f" {a.get('filename', '')} {a.get('summary', '')} {' '.join(a.get('key_points', []))}".lower()

            urgency = "Normal"
            if any(k in t_low for k in ["urgent", "asap", "deadline", "action required", "immediate", "due today", "critical"]):
                urgency = "Urgent"
            elif any(k in t_low for k in ["newsletter", "digest", "promo", "discount", "sale"]):
                urgency = "Low"

            action = "No action needed (Informational)"
            if any(k in t_low for k in ["licence", "license", "application", "renewal", "sarathi", "rto", "form 2"]):
                action = "Review application details and submit/upload required documents to Licensing Authority"
            elif any(k in t_low for k in ["invoice", "payment", "bill", "due date", "balance due", "remit"]):
                action = "Review invoice and process payment by due date"
            elif any(k in t_low for k in ["agreement", "contract", "terms of service", "nda", "sign"]):
                action = "Review agreement terms and provide signature or approval"
            elif any(k in t_low for k in ["statement of account", "pension slip", "salary slip"]):
                action = "Review account statement / slip figures"
            elif any(k in t_low for k in ["review", "attached", "feedback", "inspect"]):
                if attachments:
                    action = f"Review attached file '{attachments[0].get('filename')}'"
                else:
                    action = "Review requested by sender"
            elif any(k in t_low for k in ["reply", "respond", "confirm", "let me know"]):
                action = "Response required from you"

            category = "Work"
            if any(k in t_low for k in ["licence", "license", "dl renewal", "family", "friend", "personal", "aadhaar", "passport"]):
                category = "Personal"
            elif any(k in t_low for k in ["invoice", "receipt", "bank", "billing", "pension", "salary", "$", "₹", "rs."]):
                category = "Finance"
            elif any(k in t_low for k in ["deal", "discount", "offer", "promo", "sale"]):
                category = "Promotions"
            elif any(k in t_low for k in ["ticket", "support", "helpdesk"]):
                category = "Support"

            # Construct informative TL;DR
            clean_snip = snippet.strip() if snippet else ""
            sentences = [s.strip() for s in clean_snip.split('.') if len(s.strip()) > 8]
            
            if attachments and (not clean_snip or len(clean_snip) < 20):
                first_a = attachments[0]
                tldr = f"Received '{first_a.get('filename')}' ({first_a.get('file_type', 'Document')}) from {sender}. {first_a.get('summary', '')}"
            elif sentences:
                tldr = ". ".join(sentences[:2]) + "."
                if attachments:
                    tldr += f" [Attached: {', '.join(a.get('filename', '') for a in attachments)}]"
            else:
                clean_subj = subject if subject and subject != "No Subject" else "Incoming email"
                tldr = f"{clean_subj} from {sender}"
                if attachments:
                    tldr += f" [Attached: {', '.join(a.get('filename', '') for a in attachments)}]"

            # Construct comprehensive Key Points
            points = []
            if sentences:
                points.extend(sentences[:2])
            
            if attachments:
                for a in attachments:
                    fn = a.get('filename', 'File')
                    sm = a.get('summary')
                    if sm:
                        points.append(f"📎 {fn}: {sm}")
                    kps = a.get('key_points', [])
                    for kp in kps[:2]:
                        points.append(f"  • {kp}")

            if not points:
                points.append(clean_snip[:120] if clean_snip else "Document received without additional text body.")

            return {
                "tldr": tldr,
                "key_points": points,
                "action_item": action,
                "urgency": urgency,
                "category": category,
                "attachments": [
                    {
                        "filename": a.get("filename"),
                        "file_type": a.get("file_type"),
                        "size_human": a.get("size_human"),
                        "summary": a.get("summary"),
                        "key_points": a.get("key_points", [])
                    }
                    for a in (attachments or [])
                ]
            }

    def get_folder_labels(self):
        """Retrieves user's accessible labels / folders."""
        try:
            resp = self.service.users().labels().list(userId='me').execute()
            labels = resp.get('labels', [])
            return [l['name'] for l in labels if l.get('name')]
        except Exception as e:
            print(f"[AI Agent] Error listing labels: {e}")
            return ["INBOX", "STARRED", "SENT", "Work", "Finance", "Promotions", "Personal"]

    def read_folder_emails(self, folder_query="in:inbox", max_results=20):
        """Reads all emails from a specific folder or query, parses attachments, and generates a synopsis for each."""
        try:
            res = self.service.users().messages().list(userId='me', q=folder_query, maxResults=max_results).execute()
            messages = res.get('messages', [])
            emails = []
            for m in messages:
                meta = self.service.users().messages().get(
                    userId='me', id=m['id'], format='full'
                ).execute()
                headers = meta.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h.get('name', '').lower() == 'subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h.get('name', '').lower() == 'from'), 'Unknown')
                date_val = next((h['value'] for h in headers if h.get('name', '').lower() == 'date'), '')
                snippet = meta.get('snippet', '')
                thread_id = meta.get('threadId', m['id'])

                full_body, attachments = self.extract_email_body_and_attachments(m['id'], meta.get('payload', {}))
                synopsis = self.generate_synopsis(sender, subject, snippet, body=full_body, attachments=attachments)
                emails.append({
                    "id": m['id'],
                    "thread_id": thread_id,
                    "sender": sender,
                    "subject": subject,
                    "snippet": snippet,
                    "date": date_val,
                    "synopsis": synopsis,
                    "attachments": attachments
                })
            return emails
        except Exception as e:
            print(f"[AI Agent] Error reading folder emails: {e}")
            return []

    def purge_blocked_senders_history(self, max_per_sender=100):
        """Finds and trashes ALL previous emails (read, unread, inbox, or archive) from blocked senders.
        
        Args:
            max_per_sender (int): Maximum messages to retrieve and trash per blocked sender.
            
        Returns:
            dict: Summary containing total_purged, per_sender counts, and details list.
        """
        total_purged = 0
        details = []
        per_sender = {}

        if not self.delete_senders:
            print("[AI Agent] No blocked senders configured for historical purge.")
            return {"total_purged": 0, "per_sender": {}, "details": []}

        print(f"[AI Agent] Starting historical purge for blocked senders: {self.delete_senders}")

        for sender_target in self.delete_senders:
            clean_target = sender_target.strip()
            if not clean_target:
                continue

            query = f"from:{clean_target} -in:trash"
            try:
                list_resp = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=max_per_sender
                ).execute()
                msgs = list_resp.get('messages', [])
                count = 0

                for m in msgs:
                    m_id = m['id']
                    try:
                        # Fetch subject and sender headers for reporting
                        meta = self.service.users().messages().get(
                            userId='me',
                            id=m_id,
                            format='metadata',
                            metadataHeaders=['Subject', 'From', 'Date']
                        ).execute()
                        headers = meta.get('payload', {}).get('headers', [])
                        subj = next((h['value'] for h in headers if h.get('name', '').lower() == 'subject'), 'No Subject')
                        from_hdr = next((h['value'] for h in headers if h.get('name', '').lower() == 'from'), clean_target)

                        # Trash message
                        self.service.users().messages().trash(userId='me', id=m_id).execute()
                        count += 1
                        details.append({
                            "id": m_id,
                            "sender": from_hdr,
                            "subject": subj,
                            "category": "Trash",
                            "action": f"Moved to Trash (Purged historical mail from blocked sender '{clean_target}')",
                            "draft": None,
                            "is_historical_purge": True
                        })
                        print(f"[AI Agent] Purged previous mail '{subj}' from blocked sender '{from_hdr}'.")
                    except Exception as trash_err:
                        print(f"[AI Agent] Could not trash message {m_id}: {trash_err}")

                per_sender[clean_target] = count
                total_purged += count
            except Exception as e:
                print(f"[AI Agent] Error querying previous emails for '{clean_target}': {e}")
                per_sender[clean_target] = 0

        print(f"[AI Agent] Completed historical purge: {total_purged} previous emails trashed from blocked senders.")
        return {
            "total_purged": total_purged,
            "per_sender": per_sender,
            "details": details
        }

    def process_unread_emails(self, auto_delete=False, max_results=10, grace_period_minutes=60, purge_history=True):
        """Scans unread emails, categorizes them, drafts replies, handles delete blacklists,
        and purges all previous emails from blocked senders.
        
        Legitimate newly arrived emails stay intact for grace_period_minutes (default 1 hour).
        
        Args:
            auto_delete (bool): If True, immediately moves blacklisted emails to trash without confirmation.
            max_results (int): Maximum unread emails to inspect.
            grace_period_minutes (int): Minutes to leave new legitimate emails intact on top of inbox (default 60).
            purge_history (bool): If True and auto_delete is True, purges all historical mails from blocked senders.
            
        Returns:
            list: List of dictionaries detailing actions taken for each processed email.
        """
        processed_summary = []

        # 0. Purge all previous/historical emails from blocked senders
        if auto_delete and purge_history and self.delete_senders:
            historical_purge = self.purge_blocked_senders_history()
            if historical_purge.get("details"):
                processed_summary.extend(historical_purge["details"])

        results = self.service.users().messages().list(userId='me', q='is:unread', maxResults=max_results).execute()
        messages = results.get('messages', [])

        if not messages:
            print("[AI Agent] No new unread messages.")
            return processed_summary

        for msg_summary in messages:
            msg = self.service.users().messages().get(userId='me', id=msg_summary['id'], format='full').execute()
            headers = msg.get('payload', {}).get('headers', [])
            sender = next((h['value'] for h in headers if h.get('name', '').lower() == 'from'), 'Unknown')
            subject = next((h['value'] for h in headers if h.get('name', '').lower() == 'subject'), 'No Subject')
            snippet = msg.get('snippet', '')
            thread_id = msg.get('threadId')
            msg_id = msg['id']

            full_body, attachments = self.extract_email_body_and_attachments(msg_id, msg.get('payload', {}))
            print(f"\nProcessing email from: {sender} | Subject: {subject} | Attachments: {len(attachments)}")
            action_status = "Categorized"
            draft_info = None

            # 1. Approval-based / Blacklist Deletion (Checked FIRST so blocked senders are never kept intact!)
            is_blacklisted = any(target in sender.lower() for target in self.delete_senders)
            if is_blacklisted:
                should_delete = False
                if auto_delete:
                    should_delete = True
                elif sys.stdin and sys.stdin.isatty():
                    # Running interactively in terminal
                    confirm = input(f"Sender '{sender}' is flagged for deletion. Delete email '{subject}'? (y/n): ")
                    if confirm.lower() == 'y':
                        should_delete = True
                else:
                    # Non-interactive (e.g., Streamlit GUI with auto_delete=False)
                    print(f"[AI Agent] Sender '{sender}' is flagged for deletion. Skipping deletion (auto-delete not enabled).")
                    action_status = "Flagged for Deletion (Pending manual approval)"

                if should_delete:
                    self.service.users().messages().trash(userId='me', id=msg_id).execute()
                    print(f"Moved to Trash: {subject}")
                    processed_summary.append({
                        "id": msg_id,
                        "sender": sender,
                        "subject": subject,
                        "snippet": snippet,
                        "category": "Trash",
                        "action": "Moved to Trash (Blocked Sender)",
                        "draft": None,
                        "attachments": attachments
                    })
                    continue

            # 2. 1-Hour Grace Period Check for Legitimate Emails: Keep newly arrived intact at top of inbox
            internal_date_ms = int(msg.get('internalDate', 0))
            if internal_date_ms > 0:
                import time
                age_seconds = (time.time() * 1000 - internal_date_ms) / 1000
                if age_seconds < (grace_period_minutes * 60):
                    mins_ago = max(0, int(age_seconds // 60))
                    print(f"[AI Agent] Email '{subject}' from '{sender}' arrived {mins_ago}m ago (< {grace_period_minutes}m). Keeping intact on top of inbox.")
                    processed_summary.append({
                        "id": msg_id,
                        "sender": sender,
                        "subject": subject,
                        "snippet": snippet,
                        "category": "Inbox (Top)",
                        "action": f"Kept Intact on Top of Inbox (Arrived {mins_ago}m ago, 1h grace)",
                        "draft": None,
                        "is_intact": True,
                        "attachments": attachments
                    })
                    continue  # Leave completely intact, unread, and untouched on top of inbox!

            # 3. Automated Draft Generation for Designated Senders
            is_designated = any(des in sender.lower() for des in self.designated_senders)
            if is_designated:
                draft_info = self.draft_reply(msg_id, thread_id, sender, subject, snippet, body=full_body, attachments=attachments)
                if draft_info:
                    action_status = "Drafted Reply & Categorized"

            # 4. Categorization & Moving to Label + Sender-named Folder
            category = self.classify_email(sender, subject, snippet, body=full_body, attachments=attachments)
            label_id = self.get_or_create_label(category)
            sender_info = self.parse_sender_info(sender)
            sender_label_id = self.get_or_create_label(sender_info['label_name'])
            add_labels = [lbl for lbl in [label_id, sender_label_id] if lbl]
            self.service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'addLabelIds': add_labels, 'removeLabelIds': ['UNREAD']}
            ).execute()
            print(f"[AI Agent] Categorized as '{category}', sorted into '{sender_info['label_name']}', and marked read.")

            processed_summary.append({
                "id": msg_id,
                "sender": sender,
                "sender_name": sender_info['name'],
                "subject": subject,
                "snippet": snippet,
                "category": category,
                "sender_folder": sender_info['label_name'],
                "action": f"{action_status} & Sorted into {sender_info['label_name']}",
                "draft": draft_info,
                "attachments": attachments
            })

        return processed_summary

    def parse_sender_info(self, from_header, folder_prefix=None):
        """
        Extracts clean sender display name, clean email address, domain root slug,
        and target folder label from From header.
        Ensures all emails from the same sender/organization (e.g. IndusInd)
        are routed into a single consolidated folder (e.g. 'indusind').
        """
        if folder_prefix is None:
            folder_prefix = getattr(self, "sender_folder_prefix", "")

        import email.utils
        name, addr = email.utils.parseaddr(from_header or "")
        name = name.strip().strip("'\"")
        addr = addr.strip().lower()

        if not addr and "@" in (from_header or ""):
            em_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_header)
            if em_match:
                addr = em_match.group(0).lower()

        user_part = addr.split("@")[0] if "@" in addr else ""
        domain_part = addr.split("@")[1] if "@" in addr else ""

        # 1. Personal / Public Webmail (e.g. Gmail, Yahoo, Outlook)
        if domain_part in PUBLIC_WEBMAIL_DOMAINS:
            if name and name.lower() != addr and not re.match(r'^(no[-_]?reply|notification|support|info)', name, re.I):
                clean_name = re.sub(r'[/\\\[\]^:]', ' ', name).strip()
                clean_name = re.sub(r'\s+', ' ', clean_name)[:40]
                folder_slug = clean_name
            else:
                folder_slug = user_part or "personal"
            label_full = f"{folder_prefix}/{folder_slug}" if folder_prefix else folder_slug
            return {
                "raw": from_header,
                "name": name or user_part,
                "email": addr,
                "domain": domain_part,
                "folder_slug": folder_slug,
                "label_name": label_full
            }

        # 2. Extract domain root SLD for corporate / organization senders
        domain_root = ""
        if domain_part:
            rem = domain_part
            for multi in MULTI_PART_TLDS:
                if rem.endswith(multi):
                    rem = rem[:-len(multi)]
                    break
            else:
                if "." in rem:
                    rem = rem.rsplit(".", 1)[0]
            parts = rem.split(".")
            domain_root = parts[-1].lower() if parts else domain_part

        # 3. Check for Delivery Relay where brand is in display name
        brand_from_name = ""
        if name:
            tokens = re.findall(r'[a-zA-Z0-9]+', name)
            meaningful = [t.lower() for t in tokens if t.lower() not in NAME_STOPWORDS]
            if meaningful:
                brand_from_name = meaningful[0]

        if domain_part in DELIVERY_RELAY_DOMAINS and brand_from_name:
            folder_slug = brand_from_name
        elif domain_root:
            folder_slug = domain_root
        elif brand_from_name:
            folder_slug = brand_from_name
        else:
            folder_slug = user_part or "unknown"

        # Apply alias mappings if configured
        mappings = getattr(self, "sender_folder_mappings", {}) or {}
        if addr in mappings:
            folder_slug = mappings[addr]
        elif domain_part in mappings:
            folder_slug = mappings[domain_part]
        elif user_part in mappings:
            folder_slug = mappings[user_part]
        elif folder_slug in mappings:
            folder_slug = mappings[folder_slug]

        folder_slug = folder_slug.lower().strip()
        folder_slug = re.sub(r'[/\\\[\]^:]', '', folder_slug)[:40] or "unknown"
        label_full = f"{folder_prefix}/{folder_slug}" if folder_prefix else folder_slug

        return {
            "raw": from_header,
            "name": name or folder_slug,
            "email": addr,
            "domain": domain_part,
            "folder_slug": folder_slug,
            "label_name": label_full
        }

    def sort_emails_by_sender(self, folder_query=None, max_results=150, create_labels=True, fetch_all=True, folder_prefix=None, target_sender=None):
        """
        Sorts emails into sender-named folders (e.g. all mails from IndusInd into 'indusind', and similar):
        1. Paginates emails matching folder_query up to max_results.
        2. Pre-caches existing labels to minimize API overhead.
        3. Parses clean sender entity folder slugs (e.g., 'indusind').
        4. Consolidates all emails from each sender entity into that sender's single folder.
        5. Applies labels in batches using batchModify.
        6. Aggregates sender volume and stats.
        """
        if folder_prefix is None:
            folder_prefix = getattr(self, "sender_folder_prefix", "")

        if target_sender:
            clean_target = target_sender.strip().lower()
            if not folder_query or folder_query in ("-in:trash -in:spam", "in:inbox"):
                folder_query = f"from:{clean_target} -in:trash -in:spam"
            elif f"from:{clean_target}" not in folder_query.lower():
                folder_query = f"from:{clean_target} {folder_query}"
        elif folder_query is None:
            folder_query = "-in:trash -in:spam"

        if not self.service:
            remark = "I cannot access your Gmail mailbox right now because authentication is required."
            return {
                "remark": remark,
                "total_emails": 0,
                "total_senders": 0,
                "sender_groups": [],
                "details": []
            }

        try:
            # 1. Fetch message list with pagination
            all_messages = []
            page_token = None
            page_size = min(max_results, 100)

            while len(all_messages) < max_results:
                req = self.service.users().messages().list(
                    userId='me', q=folder_query, maxResults=page_size, pageToken=page_token
                )
                res = req.execute()
                msgs = res.get('messages', [])
                all_messages.extend(msgs)
                page_token = res.get('nextPageToken')
                if not fetch_all or not page_token:
                    break

            all_messages = all_messages[:max_results]
            if not all_messages:
                remark = f"I checked your mailbox ({folder_query}) and found 0 emails to sort."
                return {
                    "remark": remark,
                    "total_emails": 0,
                    "total_senders": 0,
                    "sender_groups": [],
                    "details": []
                }

            # 2. Pre-fetch existing labels
            existing_labels = {}
            try:
                lbl_res = self.service.users().labels().list(userId='me').execute()
                for l in lbl_res.get('labels', []):
                    existing_labels[l.get('name', '').lower()] = l.get('id')
            except Exception as e:
                print(f"[AI Agent] Could not list existing labels: {e}")

            def get_or_create_cached_label(label_name):
                clean = label_name.strip()
                if clean.lower() in existing_labels:
                    return existing_labels[clean.lower()]
                try:
                    created = self.service.users().labels().create(
                        userId='me',
                        body={'name': clean, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
                    ).execute()
                    existing_labels[clean.lower()] = created['id']
                    return created['id']
                except Exception as ce:
                    print(f"[AI Agent] Note creating label '{clean}': {ce}")
                    return None

            if create_labels and folder_prefix:
                get_or_create_cached_label(folder_prefix)

            senders_map = {}
            email_details = []

            # 3. Fetch metadata for each message
            for m in all_messages:
                m_id = m['id']
                try:
                    meta = self.service.users().messages().get(
                        userId='me', id=m_id, format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date']
                    ).execute()
                except Exception as fetch_err:
                    print(f"[AI Agent] Could not fetch message {m_id}: {fetch_err}")
                    continue

                headers = meta.get('payload', {}).get('headers', [])
                from_hdr = next((h['value'] for h in headers if h.get('name', '').lower() == 'from'), 'Unknown')
                subject = next((h['value'] for h in headers if h.get('name', '').lower() == 'subject'), 'No Subject')
                date_val = next((h['value'] for h in headers if h.get('name', '').lower() == 'date'), '')
                snippet = meta.get('snippet', '')
                thread_id = meta.get('threadId', m_id)
                label_ids = meta.get('labelIds', [])
                is_unread = 'UNREAD' in label_ids

                sender_info = self.parse_sender_info(from_hdr, folder_prefix=folder_prefix)
                if target_sender:
                    target_clean = target_sender.strip().lower()
                    sender_email_low = sender_info['email'].lower()
                    sender_name_low = sender_info['name'].lower()
                    folder_slug_low = sender_info['folder_slug'].lower()
                    raw_from_low = from_hdr.lower()
                    if not (target_clean in sender_email_low or target_clean in sender_name_low or target_clean in folder_slug_low or target_clean in raw_from_low):
                        continue

                # Group by folder_slug so all emails from the same sender (e.g. IndusInd) belong to one group!
                sender_key = sender_info.get('folder_slug') or sender_info['label_name'].lower()

                email_item = {
                    "id": m_id,
                    "thread_id": thread_id,
                    "sender": from_hdr,
                    "sender_name": sender_info['name'],
                    "sender_email": sender_info['email'],
                    "folder_slug": sender_info['folder_slug'],
                    "subject": subject,
                    "date": date_val,
                    "snippet": snippet,
                    "category": f"Sender: {sender_info['name']}",
                    "action": f"Sorted into folder '{sender_info['label_name']}'",
                    "is_unread": is_unread,
                    "sender_label": sender_info['label_name']
                }
                email_details.append(email_item)

                if sender_key not in senders_map:
                    senders_map[sender_key] = {
                        "sender_key": sender_key,
                        "sender_name": sender_info['name'],
                        "folder_slug": sender_info['folder_slug'],
                        "sender_email": sender_info['email'],
                        "raw_from": from_hdr,
                        "label_name": sender_info['label_name'],
                        "count": 0,
                        "unread_count": 0,
                        "emails": [],
                        "pending_message_ids": []
                    }

                group = senders_map[sender_key]
                group["count"] += 1
                if is_unread:
                    group["unread_count"] += 1
                group["emails"].append(email_item)
                group["pending_message_ids"].append({"id": m_id, "label_ids": label_ids})

            # 4. Batch label modifications using batchModify
            if create_labels:
                for grp in senders_map.values():
                    lbl_id = get_or_create_cached_label(grp["label_name"])
                    if not lbl_id:
                        continue
                    ids_to_apply = [p["id"] for p in grp["pending_message_ids"] if lbl_id not in p["label_ids"]]
                    if ids_to_apply:
                        for b in range(0, len(ids_to_apply), 50):
                            batch_ids = ids_to_apply[b:b+50]
                            try:
                                self.service.users().messages().batchModify(
                                    userId='me',
                                    body={'ids': batch_ids, 'addLabelIds': [lbl_id]}
                                ).execute()
                            except Exception as mod_err:
                                print(f"[AI Agent] Could not batchModify for '{grp['label_name']}': {mod_err}")

            # 5. Build summary remark
            sender_groups = sorted(senders_map.values(), key=lambda g: g["count"], reverse=True)
            self.last_sender_groups = sender_groups

            if target_sender and sender_groups:
                primary = sender_groups[0]
                unread_desc = f" ({primary['unread_count']} unread)" if primary['unread_count'] else ""
                folder_desc = f"'{primary['label_name']}'"
                remark = (
                    f"📬 I've put all {len(email_details)} emails from '{target_sender}' into the folder **{folder_desc}**!\n\n"
                    f"Folder Details:\n"
                    f"• 📁 **{primary['label_name']}**: {primary['count']} email{'s' if primary['count'] != 1 else ''}{unread_desc}\n\n"
                    f"All past emails from '{target_sender}' have been organized, and all future incoming emails from this sender will also be automatically filed into this folder."
                )
            elif target_sender and not sender_groups:
                remark = f"I checked your mailbox for emails from '{target_sender}' but found 0 matching emails to put in a folder."
            else:
                top_bullets = "\n".join(
                    f"• 📁 **{g['label_name']}**: {g['count']} email{'s' if g['count'] != 1 else ''}" + (f" ({g['unread_count']} unread)" if g['unread_count'] else "")
                    for g in sender_groups[:8]
                )
                folder_scope_desc = f"under '{folder_prefix}/'" if folder_prefix else "directly"
                remark = (
                    f"📬 I've sorted all {len(email_details)} emails sender-wise into {len(sender_groups)} folders {folder_scope_desc} (e.g., all mails from IndusInd into folder 'indusind', and similar for other senders)!\n\n"
                    f"Sender Folders Created / Organized:\n{top_bullets}\n\n"
                    f"All future incoming emails from these senders will also be automatically organized into their respective folders."
                )

            return {
                "remark": remark,
                "total_emails": len(email_details),
                "total_senders": len(sender_groups),
                "sender_groups": sender_groups,
                "details": email_details
            }
        except Exception as e:
            err_msg = f"I had an issue sorting your emails sender-wise: {e}"
            print(f"[AI Agent] {err_msg}")
            return {
                "remark": err_msg,
                "total_emails": 0,
                "total_senders": 0,
                "sender_groups": [],
                "details": []
            }

    def _sync_creds_to_extension(self):
        """Syncs active OAuth credentials to extension/auth_config.json."""
        if not self.creds:
            return
        ext_cfg = os.path.join("extension", "auth_config.json")
        if os.path.exists(ext_cfg):
            try:
                with open(ext_cfg, "r", encoding="utf-8") as ef:
                    e_data = json.load(ef)
                c_dict = json.loads(self.creds.to_json())
                if c_dict.get("refresh_token"):
                    e_data["refresh_token"] = c_dict["refresh_token"]
                if c_dict.get("client_id"):
                    e_data["client_id"] = c_dict["client_id"]
                if c_dict.get("client_secret"):
                    e_data["client_secret"] = c_dict["client_secret"]
                with open(ext_cfg, "w", encoding="utf-8") as ef:
                    json.dump(e_data, ef, indent=2)
                print(f"[AI Agent] Successfully synced OAuth credentials to {ext_cfg}")
            except Exception as e:
                print(f"[AI Agent] Error syncing creds to extension: {e}")

    def _persist_delete_senders(self):
        """Persists delete_senders to config.json and extension/auth_config.json."""
        # 1. Update config.json
        cfg_path = "config.json"
        cfg = {}
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                pass
        cfg["delete_senders"] = self.delete_senders
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            print(f"[AI Agent] Successfully saved {len(self.delete_senders)} blocked sender(s) to {cfg_path}")
        except Exception as e:
            print(f"[AI Agent] Error saving {cfg_path}: {e}")

        # 2. Update extension/auth_config.json
        ext_cfg = os.path.join("extension", "auth_config.json")
        if os.path.exists(ext_cfg):
            try:
                with open(ext_cfg, "r", encoding="utf-8") as ef:
                    e_data = json.load(ef)
                e_data["delete_senders"] = self.delete_senders
                with open(ext_cfg, "w", encoding="utf-8") as ef:
                    json.dump(e_data, ef, indent=2)
            except Exception as e:
                print(f"[AI Agent] Error updating {ext_cfg}: {e}")

    def block_sender(self, sender_target, selected_email_id=None, purge_now=True):
        """
        Blocks a sender:
        1. Identifies the target email or domain (from prompt or selected email).
        2. Adds them to self.delete_senders and saves to config.json permanently.
        3. Immediately trashes all historical emails from this sender across the mailbox.
        4. Future incoming emails from this sender will be automatically trashed.
        """
        clean_target = (sender_target or "").strip().lower()

        # If user said 'this sender' or target is empty, resolve from selected_email_id or latest email
        if clean_target in ["this", "the sender", "this sender", ""] and self.service:
            target_id = selected_email_id
            if not target_id:
                try:
                    res = self.service.users().messages().list(userId='me', q='in:inbox', maxResults=1).execute()
                    msgs = res.get('messages', [])
                    if msgs:
                        target_id = msgs[0]['id']
                except Exception:
                    pass

            if target_id:
                try:
                    meta = self.service.users().messages().get(userId='me', id=target_id, format='metadata', metadataHeaders=['From']).execute()
                    headers = meta.get('payload', {}).get('headers', [])
                    from_val = next((h['value'] for h in headers if h.get('name', '').lower() == 'from'), '')
                    import email.utils
                    _, addr = email.utils.parseaddr(from_val)
                    if addr:
                        clean_target = addr.lower()
                    else:
                        clean_target = from_val.lower()
                except Exception as e:
                    print(f"[AI Agent] Could not resolve sender from email {target_id}: {e}")

        # Extract email if passed with display name, e.g. "Spam Company <spam@deals.com>"
        import email.utils
        _, parsed_addr = email.utils.parseaddr(clean_target)
        if parsed_addr and "@" in parsed_addr:
            clean_target = parsed_addr.lower()

        clean_target = clean_target.strip("<>'\"")
        if not clean_target or clean_target in ["this", "sender"]:
            return {
                "remark": "Please specify the email address or sender you would like to block (e.g. 'block spam@promos.com').",
                "blocked_sender": None,
                "purged_count": 0,
                "details": []
            }

        already_blocked = clean_target in self.delete_senders
        if not already_blocked:
            self.delete_senders.append(clean_target)
            self._persist_delete_senders()

        # Purge past emails from this blocked sender
        purged_count = 0
        details = []
        if purge_now and self.service:
            query = f"from:{clean_target} -in:trash"
            try:
                list_resp = self.service.users().messages().list(userId='me', q=query, maxResults=100).execute()
                msgs = list_resp.get('messages', [])
                for m in msgs:
                    m_id = m['id']
                    try:
                        meta = self.service.users().messages().get(userId='me', id=m_id, format='metadata', metadataHeaders=['Subject', 'From']).execute()
                        headers = meta.get('payload', {}).get('headers', [])
                        subj = next((h['value'] for h in headers if h.get('name', '').lower() == 'subject'), 'No Subject')
                        from_hdr = next((h['value'] for h in headers if h.get('name', '').lower() == 'from'), clean_target)
                        self.service.users().messages().trash(userId='me', id=m_id).execute()
                        purged_count += 1
                        details.append({
                            "id": m_id,
                            "sender": from_hdr,
                            "subject": subj,
                            "category": "Trash",
                            "action": f"Moved to Trash (Blocked sender '{clean_target}')"
                        })
                    except Exception as trash_err:
                        print(f"[AI Agent] Error trashing message {m_id}: {trash_err}")
            except Exception as e:
                print(f"[AI Agent] Error querying previous emails for '{clean_target}': {e}")

        # Try to create a native Gmail Filter if permitted (best effort)
        try:
            filter_body = {
                'criteria': {'from': clean_target},
                'action': {'removeLabelIds': ['INBOX'], 'addLabelIds': ['TRASH']}
            }
            self.service.users().settings().filters().create(userId='me', body=filter_body).execute()
            print(f"[AI Agent] Created native Gmail filter to trash future mail from '{clean_target}'.")
        except Exception:
            pass

        status_prefix = f"🚫 **Blocked sender '{clean_target}'!**" if not already_blocked else f"⚠️ Sender '{clean_target}' is already in your blocked list."
        remark = (
            f"{status_prefix}\n\n"
            f"• Added to permanent blacklist rules (saved to `config.json`)\n"
            f"• Moved {purged_count} past email{'s' if purged_count != 1 else ''} from this sender to Trash\n"
            f"• All future emails from '{clean_target}' will be automatically blocked and trashed."
        )

        return {
            "remark": remark,
            "blocked_sender": clean_target,
            "purged_count": purged_count,
            "details": details
        }

    def unblock_sender(self, sender_target):
        """Unblocks a sender and removes them from the delete_senders blacklist."""
        clean_target = (sender_target or "").strip().lower()
        import email.utils
        _, parsed_addr = email.utils.parseaddr(clean_target)
        if parsed_addr:
            clean_target = parsed_addr.lower()

        clean_target = clean_target.strip("<>'\"")
        matching = [s for s in self.delete_senders if clean_target in s or s in clean_target]

        if not matching:
            return {
                "remark": f"Sender '{clean_target}' was not found in your blocked senders list.",
                "unblocked": None
            }

        for m in matching:
            self.delete_senders.remove(m)
        self._persist_delete_senders()

        unblocked_str = ", ".join(matching)
        remark = f"✅ Unblocked sender(s): '{unblocked_str}'. They have been removed from your blacklist and future emails will be accepted."
        return {
            "remark": remark,
            "unblocked": matching
        }

    def list_blocked_senders(self):
        """Lists all currently blocked / blacklisted senders."""
        if not self.delete_senders:
            return {
                "remark": "📋 You currently have 0 blocked senders. Your blacklist is clean!",
                "blocked_senders": []
            }
        
        list_str = "\n".join(f"• `{s}`" for s in self.delete_senders)
        remark = f"📋 You currently have {len(self.delete_senders)} blocked sender(s):\n\n{list_str}\n\nAll emails from these senders are automatically moved to Trash."
        return {
            "remark": remark,
            "blocked_senders": list(self.delete_senders)
        }

    def handle_user_prompt(self, user_prompt, auto_delete=False, max_results=10, grace_period_minutes=60, selected_email_id=None, selected_email_sender=None):
        """Processes a natural language command from the user, executes actions, and returns an avatar remark."""
        # 1. Engage Brain to analyze intent and extract entities
        context = {
            "blocked_senders": self.delete_senders,
            "selected_email_id": selected_email_id,
            "selected_email_sender": selected_email_sender
        }
        decision = self.brain.think(user_prompt, context=context)
        intent = decision.get("intent", "GENERAL_CONVERSATION")
        params = decision.get("parameters", {})
        print(f"[AI Agent Brain] Prompt: '{user_prompt}' -> Intent: {intent} | Parameters: {params}")

        # 2. Execute Intent: SORT_BY_SENDER
        if intent == "SORT_BY_SENDER":
            target_sender = params.get("target_sender")
            needs_target = params.get("needs_target_sender", False)

            # If prompt requests a particular sender without naming one
            if not target_sender and needs_target:
                selected_sender = context.get("selected_email_sender")
                if selected_sender:
                    target_sender = selected_sender
                else:
                    remark = (
                        "📁 I can certainly put all mails from a particular sender in a folder named after that sender!\n\n"
                        "**Which sender would you like me to sort?**\n"
                        "You can specify:\n"
                        "• An email address: e.g. *'put all mails from client@example.com in a folder named after the sender'*\n"
                        "• A company or brand: e.g. *'put all mails from IndusInd in a folder named after the sender'*\n"
                        "• A sender's display name: e.g. *'put all mails from \"John Doe\" in a folder named after the sender'*\n\n"
                        "💡 *Tip:* You can also go to the **👥 Sender-Wise Mails & Groups** tab, enter the sender in the **Target Particular Sender** field, and click **Put Mails in Folder**."
                    )
                    return remark, []

            if target_sender:
                folder = f"from:{target_sender} -in:trash -in:spam"
            else:
                folder = params.get("folder", "-in:trash -in:spam")
            create_lbls = params.get("create_labels", True)
            is_all = "all" in user_prompt.lower() or "entire" in user_prompt.lower() or params.get("fetch_all", False)
            max_r = 150 if is_all else params.get("max_results", 30)
            sort_res = self.sort_emails_by_sender(
                folder_query=folder,
                max_results=max_r,
                create_labels=create_lbls,
                fetch_all=is_all,
                target_sender=target_sender
            )
            return sort_res["remark"], sort_res.get("details", [])

        # 3. Execute Intent: BLOCK_SENDER
        if intent == "BLOCK_SENDER":
            target = params.get("target_sender", "")
            purge_now = params.get("purge_now", True)
            block_res = self.block_sender(target, selected_email_id=selected_email_id, purge_now=purge_now)
            return block_res["remark"], block_res.get("details", [])

        # 4. Execute Intent: UNBLOCK_SENDER
        if intent == "UNBLOCK_SENDER":
            target = params.get("target_sender", "")
            unblock_res = self.unblock_sender(target)
            return unblock_res["remark"], []

        # 5. Execute Intent: LIST_BLOCKED
        if intent == "LIST_BLOCKED":
            list_res = self.list_blocked_senders()
            return list_res["remark"], []

        # 6. Execute Intent: COUNT_UNREAD
        if intent == "COUNT_UNREAD":
            if not self.service:
                return "I cannot check your unread emails because Gmail authentication is needed.", []
            try:
                res = self.service.users().messages().list(userId='me', q='is:unread', maxResults=50).execute()
                msgs = res.get('messages', [])
                count = len(msgs)
                remark = f"I checked your inbox: you currently have {count}{'+' if count == 50 else ''} unread email{'s' if count != 1 else ''}. Would you like me to scan and organize them?"
                return remark, []
            except Exception as e:
                return f"I had a slight hiccup checking your unread emails: {e}", []

        # 7. Execute Intent: DRAFT_REPLY
        if intent == "DRAFT_REPLY":
            if not self.service:
                return "I cannot create drafts right now because Gmail authentication is needed.", []
            try:
                target_msg_id = selected_email_id
                if not target_msg_id:
                    res = self.service.users().messages().list(userId='me', q='in:inbox', maxResults=5).execute()
                    msgs = res.get('messages', [])
                    if not msgs:
                        return "I searched your inbox and found no emails to reply to.", []
                    target_msg_id = msgs[0]['id']

                meta = self.service.users().messages().get(userId='me', id=target_msg_id, format='full').execute()
                headers = meta.get('payload', {}).get('headers', [])
                sender = next((h['value'] for h in headers if h.get('name', '').lower() == 'from'), 'Unknown')
                subject = next((h['value'] for h in headers if h.get('name', '').lower() == 'subject'), 'No Subject')
                snippet = meta.get('snippet', '')
                thread_id = meta.get('threadId', target_msg_id)
                full_body, atts = self.extract_email_body_and_attachments(target_msg_id, meta.get('payload', {}))

                draft_info = self.draft_reply(target_msg_id, thread_id, sender, subject, snippet, body=full_body, attachments=atts)
                if draft_info:
                    preview = draft_info.get('preview', '')
                    remark = (
                        f"✉️ I've created a draft reply for you in Gmail Drafts to '{sender}' regarding '{subject}'!\n\n"
                        f"Draft Preview:\n\"{preview}\"\n\n"
                        f"You can review, edit, or send it directly in Gmail."
                    )
                    result_item = {
                        "id": target_msg_id,
                        "sender": sender,
                        "subject": subject,
                        "snippet": snippet,
                        "category": "Draft",
                        "action": f"Created Draft Reply (ID: {draft_info.get('id')})",
                        "draft": draft_info,
                        "attachments": atts
                    }
                    return remark, [result_item]
                else:
                    return f"I found the email '{subject}' from '{sender}', but had an issue creating the draft in Gmail.", []
            except Exception as e:
                return f"I had an issue preparing your draft reply: {e}", []

        # 8. Execute Intent: SUMMARIZE_ATTACHMENTS
        if intent == "SUMMARIZE_ATTACHMENTS":
            if not self.service:
                return "I cannot inspect attachments right now because Gmail authentication is needed.", []
            try:
                found_emails = []
                if selected_email_id:
                    try:
                        meta = self.service.users().messages().get(userId='me', id=selected_email_id, format='full').execute()
                        headers = meta.get('payload', {}).get('headers', [])
                        subj = next((h['value'] for h in headers if h.get('name', '').lower() == 'subject'), '')
                        from_hdr = next((h['value'] for h in headers if h.get('name', '').lower() == 'from'), 'Unknown')
                        date_hdr = next((h['value'] for h in headers if h.get('name', '').lower() == 'date'), '')
                        snippet = meta.get('snippet', '')
                        full_body, atts = self.extract_email_body_and_attachments(selected_email_id, meta.get('payload', {}))
                        if not subj.strip() and atts:
                            subj = f"(File: {atts[0].get('filename')})"
                        elif not subj.strip():
                            subj = "No Subject"
                        synopsis = self.generate_synopsis(from_hdr, subj, snippet, body=full_body, attachments=atts)
                        found_emails.append({
                            "id": selected_email_id,
                            "sender": from_hdr,
                            "subject": subj,
                            "date": date_hdr,
                            "snippet": snippet,
                            "attachments": atts,
                            "synopsis": synopsis
                        })
                    except Exception as e:
                        print(f"[AI Agent] Error retrieving selected email {selected_email_id}: {e}")

                if not found_emails:
                    query = 'has:attachment'
                    res = self.service.users().messages().list(userId='me', q=query, maxResults=12).execute()
                    msgs = res.get('messages', [])
                    for m in msgs:
                        meta = self.service.users().messages().get(userId='me', id=m['id'], format='full').execute()
                        headers = meta.get('payload', {}).get('headers', [])
                        subj = next((h['value'] for h in headers if h.get('name', '').lower() == 'subject'), '')
                        from_hdr = next((h['value'] for h in headers if h.get('name', '').lower() == 'from'), 'Unknown')
                        date_hdr = next((h['value'] for h in headers if h.get('name', '').lower() == 'date'), '')
                        snippet = meta.get('snippet', '')
                        full_body, atts = self.extract_email_body_and_attachments(m['id'], meta.get('payload', {}))
                        if atts:
                            if not subj.strip():
                                subj = f"(File: {atts[0].get('filename')})"
                            synopsis = self.generate_synopsis(from_hdr, subj, snippet, body=full_body, attachments=atts)
                            found_emails.append({
                                "id": m['id'],
                                "sender": from_hdr,
                                "subject": subj,
                                "date": date_hdr,
                                "snippet": snippet,
                                "attachments": atts,
                                "synopsis": synopsis
                            })
                            if len(found_emails) >= 2:
                                break

                if found_emails:
                    primary = found_emails[0]
                    p_syn = primary["synopsis"]
                    att_list = primary["attachments"]
                    att_desc = ", ".join(f"'{a.get('filename')}' ({a.get('file_type', 'File')}, {a.get('size_human', '')})" for a in att_list)
                    kp_str = ""
                    if p_syn.get("key_points"):
                        kp_str = "Key Highlights:\n" + "\n".join(f"• {kp}" for kp in p_syn["key_points"][:3])

                    remark_lines = [
                        "📎 Here is the summary of your email with attachment:",
                        f"📧 From: {primary['sender']}",
                        f"📋 Subject: {primary['subject']}",
                        f"📝 Summary: {p_syn.get('tldr', 'Email processed.')}",
                        f"📎 Attached File(s): {att_desc}",
                        f"⚡ Action Item: {p_syn.get('action_item', 'Review document')} ({p_syn.get('urgency', 'Normal')} priority)"
                    ]
                    if kp_str:
                        remark_lines.append(kp_str)
                    remark = "\n\n".join(remark_lines)
                    results_formatted = [
                        {
                            "id": e["id"],
                            "sender": e["sender"],
                            "subject": e["subject"],
                            "snippet": e["snippet"],
                            "category": e["synopsis"].get("category", "Work"),
                            "action": e["synopsis"].get("action_item", "Summarized"),
                            "synopsis": e["synopsis"],
                            "attachments": e["attachments"]
                        }
                        for e in found_emails
                    ]
                    return remark, results_formatted
                else:
                    return "I searched your mailbox for emails with attachments, but no accessible files were found.", []
            except Exception as e:
                return f"I had an issue summarizing emails with attachments: {e}", []

        # 9. Execute Intent: FOLDER_SYNOPSIS
        if intent == "FOLDER_SYNOPSIS":
            folder = params.get("folder", "in:inbox")
            if not self.service:
                return "I cannot read folder emails right now because Gmail authentication is needed.", []
            try:
                emails = self.read_folder_emails(folder_query=folder, max_results=max_results)
                total = len(emails)
                if total == 0:
                    remark = f"I looked through '{folder}' and found 0 emails to summarize. Your folder is empty or up to date!"
                else:
                    action_count = sum(1 for e in emails if e.get("synopsis", {}).get("urgency") == "Urgent" or "no action" not in e.get("synopsis", {}).get("action_item", "").lower())
                    info_count = total - action_count
                    remark = f"I've read and analyzed all {total} emails in this folder! {action_count} require your action, and {info_count} are informational."
                results_formatted = [
                    {
                        "id": e["id"],
                        "sender": e["sender"],
                        "subject": e["subject"],
                        "snippet": e["snippet"],
                        "category": e.get("synopsis", {}).get("category", "Work"),
                        "action": e.get("synopsis", {}).get("action_item", "Summarized"),
                        "synopsis": e.get("synopsis")
                    }
                    for e in emails
                ]
                return remark, results_formatted
            except Exception as e:
                return f"I had an issue reading emails from the folder: {e}", []

        # 10. Execute Intent: PURGE_SPAM
        if intent == "PURGE_SPAM":
            if not self.service:
                return "I cannot purge spam right now because Gmail authentication is needed.", []
            try:
                purge_res = self.purge_blocked_senders_history()
                count = purge_res["total_purged"]
                senders_str = ", ".join(self.delete_senders) if self.delete_senders else "None configured"
                if count > 0:
                    remark = f"I searched your entire mailbox and deleted {count} previous email{'s' if count != 1 else ''} from blocked senders ({senders_str}). All past spam has been moved to Trash!"
                else:
                    remark = f"I checked your entire mailbox for previous emails from blocked senders ({senders_str}), and found 0. Your inbox is clean of past spam!"
                return remark, purge_res["details"]
            except Exception as e:
                return f"I had an issue purging emails from blocked senders: {e}", []

        # 11. Execute Intent: SCAN_INBOX
        if intent == "SCAN_INBOX":
            if not self.service:
                return "I cannot scan your inbox right now because Gmail authentication is needed.", []
            results = self.process_unread_emails(
                auto_delete=auto_delete,
                max_results=max_results,
                grace_period_minutes=grace_period_minutes,
                purge_history=True
            )
            if not results:
                remark = "I scanned your inbox and found 0 unread emails. Everything is sparkling clean and up to date!"
            else:
                historical_purged = [r for r in results if r.get('is_historical_purge')]
                active_results = [r for r in results if not r.get('is_historical_purge')]
                intact_count = sum(1 for r in active_results if r.get('is_intact'))
                triaged = [r for r in active_results if not r.get('is_intact')]
                drafts = sum(1 for r in triaged if r.get('draft'))
                trashed = sum(1 for r in triaged if r.get('category') == 'Trash')
                categorized = len(triaged) - trashed

                parts = []
                if historical_purged:
                    parts.append(f"Deleted {len(historical_purged)} previous email{'s' if len(historical_purged) > 1 else ''} from blocked senders across your mailbox.")
                if intact_count > 0:
                    parts.append(f"Kept {intact_count} newly arrived email{'s' if intact_count > 1 else ''} intact on top of your inbox for the 1-hour window.")
                if len(triaged) > 0:
                    parts.append(f"Triaged {len(triaged)} older email{'s' if len(triaged) > 1 else ''}: {categorized} sorted into labels, {drafts} draft prepared, {trashed} spam trashed.")
                elif intact_count > 0 and not historical_purged:
                    parts.append("No older emails required triaging.")
                parts.append("What would you like me to do next?")
                remark = " ".join(parts)
            return remark, results

        # 12. Execute Intent: READ_FILE
        if intent == "READ_FILE":
            cand = params.get("filepath", "")
            if cand and os.path.isfile(cand):
                try:
                    res = self.file_reader.read_file(cand)
                    remark = f"I've read and analyzed '{res['filename']}' ({res['file_type']}, {res['size_human']})! {res['summary']}"
                    return remark, [res]
                except Exception as e:
                    return f"I found the file '{cand}', but had an issue reading it: {e}", []

        # 13. Default: GENERAL_CONVERSATION
        try:
            client = self.get_openai_client()
            sys_msg = f"""You are a 3D animated AI Gmail Assistant. Your job is to help the user manage their email inbox, sort emails sender-wise, block senders, create draft replies, and inspect attached documents.
Current rules:
- Auto-draft senders: {', '.join(self.designated_senders) if self.designated_senders else 'None configured'}
- Blacklisted senders: {', '.join(self.delete_senders) if self.delete_senders else 'None configured'}

Capabilities:
- Sort emails sender-wise into labels (command: 'Sort my mails sender wise')
- Block senders and purge their past emails (command: 'Block sender <email>')
- Unblock senders (command: 'Unblock <email>')
- List blocked senders (command: 'Who is blocked')
- Draft contextual replies (command: 'Make a draft reply')
- Inspect and summarize email attachments (command: 'Summarize mail with attachment')
- Scan, organize, and categorize unread messages (command: 'Scan now')
- Generate folder synopses (command: 'Summarize folder')

Answer the user directly and concisely in a friendly, enthusiastic, professional avatar persona.
"""
            resp = client.chat.completions.create(
                model=getattr(self, 'model_name', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
                temperature=0.7,
                timeout=8.0
            )
            remark = resp.choices[0].message.content.strip()
            return remark, []
        except Exception:
            blocked_str = ", ".join(self.delete_senders) if self.delete_senders else "None"
            return (
                "👋 I'm your AI Gmail Assistant with Intelligent Brain!\n\n"
                "Here are key things you can ask me to do:\n"
                "• 👥 **'Sort my mails sender wise'** - sorts all your emails into sender labels/folders\n"
                "• 🚫 **'Block sender spam@promos.com'** - permanently blocks the sender & deletes all their past emails\n"
                "• 📋 **'Who is blocked'** - lists all currently blocked senders\n"
                "• ✉️ **'Make a draft reply'** - creates a contextual draft reply in Gmail Drafts\n"
                "• 📎 **'Summarize mail with attachment'** - inspects and summarizes attachments\n"
                "• 🚀 **'Scan now'** - triages unread emails into category labels\n\n"
                f"Currently blocked senders: `{blocked_str}`"
            ), []


if __name__ == "__main__":
    agent = GmailAIAgent(
        designated_senders=["boss@example.com", "client@example.com"],
        delete_senders=["newsletter@spam.com", "promos@deals.com"]
    )
    agent.process_unread_emails()
