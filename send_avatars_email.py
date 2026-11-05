"""
Sends the AI companion avatar pack to the user's Gmail mailbox (pnchjee@gmail.com).
Includes embedded inline images and full downloadable attachments (.png and .gif).
"""

import os
import glob
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def send_avatar_pack(recipient="pnchjee@gmail.com"):
    print(f"Preparing to send avatar pack to {recipient}...")

    if not os.path.exists("token.json"):
        raise FileNotFoundError("token.json not found. Authenticate first.")

    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    service = build("gmail", "v1", credentials=creds)

    msg_root = MIMEMultipart("related")
    msg_root["Subject"] = "🤖 Meet Your AI Gmail Companions: Your 3D Avatar Pack is Ready!"
    msg_root["From"] = f"AI Gmail Avatar Agent <me>"
    msg_root["To"] = recipient

    # Alternative part for plain text and HTML
    msg_alt = MIMEMultipart("alternative")
    msg_root.attach(msg_alt)

    plain_text = """Hello!

Your AI Gmail Avatar Assistant is now ACTIVE and standing by to help manage your inbox.

We have attached your 3 companion avatars:
1. 🐶 Cute Puppy Dog (Loyal, energetic triage buddy)
2. 🐰 Fluffy Bunny (Swift, cheerful email organizer)
3. 🐻 Teddy Bear (Warm, calm executive companion)

All avatar images and animated GIFs are attached below. Your agent can read, inspect, and analyze all of them!

- AI Gmail Assistant
"""
    msg_alt.attach(MIMEText(plain_text, "plain", "utf-8"))

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px; margin: 0; }}
  .container {{ max-width: 640px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid rgba(56, 189, 248, 0.3); padding: 28px; box-shadow: 0 16px 40px rgba(0,0,0,0.5); }}
  .header {{ text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 18px; margin-bottom: 24px; }}
  .header h1 {{ color: #38bdf8; font-size: 24px; margin: 0 0 8px 0; }}
  .status-badge {{ display: inline-block; background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #22c55e; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
  .intro {{ font-size: 14.5px; line-height: 1.6; color: #cbd5e1; margin-bottom: 24px; }}
  .avatar-grid {{ display: flex; flex-direction: column; gap: 18px; margin-bottom: 24px; }}
  .avatar-card {{ background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(147, 197, 253, 0.2); border-radius: 12px; padding: 16px; display: flex; align-items: center; gap: 16px; }}
  .avatar-card img {{ width: 110px; height: 110px; border-radius: 12px; object-fit: cover; border: 2px solid #38bdf8; }}
  .avatar-info h3 {{ margin: 0 0 6px 0; font-size: 17px; color: #f8fafc; }}
  .avatar-info p {{ margin: 0 0 6px 0; font-size: 13px; color: #94a3b8; line-height: 1.4; }}
  .tag {{ display: inline-block; background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; margin-right: 6px; }}
  .footer {{ text-align: center; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 18px; font-size: 12px; color: #64748b; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="status-badge">🟢 Agent Service Active</div>
    <h1>🤖 Your AI Gmail Companions Are Ready!</h1>
    <p style="color: #94a3b8; font-size: 13px; margin: 6px 0 0 0;">Autonomous Inbox Scanning & Multi-Format Document Reader</p>
  </div>

  <p class="intro">
    Hello! Your <b>AI Gmail Assistant</b> has been successfully activated. As requested, here is your companion avatar pack delivered directly to your mailbox!
  </p>

  <div class="avatar-grid">
    <div class="avatar-card">
      <img src="cid:avatar_dog" alt="Puppy Dog Avatar">
      <div class="avatar-info">
        <h3>🐶 Cute Puppy Dog</h3>
        <p>Loyal, energetic inbox watchdog. Specializes in auto-triaging unread emails, auto-drafting replies, and moving spam to trash.</p>
        <div>
          <span class="tag">Active 3D Avatar</span>
          <span class="tag">Animated GIF Attached</span>
        </div>
      </div>
    </div>

    <div class="avatar-card">
      <img src="cid:avatar_bunny" alt="Fluffy Bunny Avatar">
      <div class="avatar-info">
        <h3>🐰 Fluffy Bunny</h3>
        <p>Swift, cheerful email organizer. Masters folder synopses, reads all folder emails, and generates instant hover cards.</p>
        <div>
          <span class="tag">Active 3D Avatar</span>
          <span class="tag">Animated GIF Attached</span>
        </div>
      </div>
    </div>

    <div class="avatar-card">
      <img src="cid:avatar_bear" alt="Teddy Bear Avatar">
      <div class="avatar-info">
        <h3>🐻 Teddy Bear</h3>
        <p>Calm, executive document analyst. Reads and parses .txt, .docx, .xlsx, .pdf, .png, .gif, and binary files with ease.</p>
        <div>
          <span class="tag">Active 3D Avatar</span>
          <span class="tag">Animated GIF Attached</span>
        </div>
      </div>
    </div>
  </div>

  <div style="background: rgba(30, 41, 59, 0.9); border-left: 4px solid #38bdf8; padding: 12px 14px; border-radius: 8px; margin-bottom: 24px; font-size: 13px; line-height: 1.5; color: #e2e8f0;">
    💡 <b>Tip:</b> Your agent is now capable of reading all files (.txt, .docx, .xlsx, .pdf, .png, .gif, and binary files). Since these avatar files are now in your mailbox, your agent can inspect and summarize them anytime!
  </div>

  <div class="footer">
    AI Gmail Avatar Agent • Running on http://127.0.0.1:5000 • Autonomous Gmail Service
  </div>
</div>
</body>
</html>
"""
    msg_alt.attach(MIMEText(html_content, "html", "utf-8"))

    # Map CIDs to image files (embed high-res 3D portraits in email)
    cid_map = {
        "avatar_dog": "avatars/3d_puppy_dog_portrait.jpg" if os.path.exists("avatars/3d_puppy_dog_portrait.jpg") else "avatars/puppy_dog_animated.gif",
        "avatar_bunny": "avatars/3d_fluffy_bunny_portrait.jpg" if os.path.exists("avatars/3d_fluffy_bunny_portrait.jpg") else "avatars/fluffy_bunny_animated.gif",
        "avatar_bear": "avatars/3d_teddy_bear_portrait.jpg" if os.path.exists("avatars/3d_teddy_bear_portrait.jpg") else "avatars/teddy_bear_animated.gif"
    }

    # If subagent generated high-res avatars in avatars/, check for them
    for cid, default_path in cid_map.items():
        if os.path.exists(default_path):
            with open(default_path, "rb") as img_f:
                mime_img = MIMEImage(img_f.read())
                mime_img.add_header("Content-ID", f"<{cid}>")
                mime_img.add_header("Content-Disposition", "inline", filename=os.path.basename(default_path))
                msg_root.attach(mime_img)

    # Attach all files in avatars/ directory as downloadable attachments
    avatar_files = glob.glob("avatars/*.*")
    print(f"Attaching {len(avatar_files)} avatar file(s)...")
    for fpath in avatar_files:
        fn = os.path.basename(fpath)
        with open(fpath, "rb") as af:
            file_bytes = af.read()
        part = MIMEApplication(file_bytes, Name=fn)
        part["Content-Disposition"] = f'attachment; filename="{fn}"'
        msg_root.attach(part)
        print(f"  • Attached: {fn} ({len(file_bytes)} bytes)")

    # Send message via Gmail API
    raw = base64.urlsafe_b64encode(msg_root.as_bytes()).decode("utf-8")
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    msg_id = result.get("id")
    print(f"\n✅ Avatar pack successfully delivered to {recipient}! (Message ID: {msg_id})")
    return msg_id


if __name__ == "__main__":
    send_avatar_pack()
