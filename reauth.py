"""
Google OAuth Re-Authentication Tool for AI Gmail Agent.
Generates a fresh OAuth token and automatically syncs it to both
token.json and extension/auth_config.json.
"""
import os
import sys
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify'
]

CREDENTIALS_PATH = 'credentials.json'
TOKEN_PATH = 'token.json'
EXT_CONFIG_PATH = os.path.join('extension', 'auth_config.json')

def reauth():
    print("==================================================")
    print("🔐 AI Gmail Agent: Google OAuth Re-Authentication")
    print("==================================================")
    
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"❌ Error: '{CREDENTIALS_PATH}' not found in current directory.")
        return False

    print("Opening your browser for Google Sign-In...")
    print("Please select your Google Account and click 'Allow' / 'Continue'.\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0, prompt='consent')
    except Exception as e:
        print(f"❌ OAuth flow failed: {e}")
        return False

    # 1. Save to token.json
    try:
        with open(TOKEN_PATH, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())
        print(f"✅ Successfully updated '{TOKEN_PATH}'")
    except Exception as e:
        print(f"⚠️ Warning: Failed to write to {TOKEN_PATH}: {e}")

    # 2. Sync client_id, client_secret, refresh_token to extension/auth_config.json
    creds_dict = json.loads(creds.to_json())
    new_refresh_token = creds_dict.get('refresh_token')
    new_client_id = creds_dict.get('client_id')
    new_client_secret = creds_dict.get('client_secret')

    if os.path.exists(EXT_CONFIG_PATH):
        try:
            with open(EXT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                ext_cfg = json.load(f)
            if new_refresh_token:
                ext_cfg['refresh_token'] = new_refresh_token
            if new_client_id:
                ext_cfg['client_id'] = new_client_id
            if new_client_secret:
                ext_cfg['client_secret'] = new_client_secret

            with open(EXT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(ext_cfg, f, indent=2)
            print(f"✅ Successfully synced new refresh token to '{EXT_CONFIG_PATH}'")
        except Exception as e:
            print(f"⚠️ Warning: Failed to update {EXT_CONFIG_PATH}: {e}")

    print("\n==================================================")
    print("🎉 Authentication Successful!")
    print("Both your local Agent and Chrome Extension are now authenticated.")
    print("==================================================")
    print("\n💡 TIP to make your token permanent (never expire again after 7 days):")
    print("1. Go to Google Cloud Console: https://console.cloud.google.com/apis/credentials/consent")
    print("2. Under 'Publishing status', click the 'PUBLISH APP' button.")
    print("3. Confirm 'In production'. This removes Google's 7-day test token limit!")
    print("==================================================")
    return True

if __name__ == "__main__":
    success = reauth()
    if not success:
        sys.exit(1)
