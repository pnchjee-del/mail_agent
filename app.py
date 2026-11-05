import os
import json
import time
import subprocess
import streamlit as st
import streamlit.components.v1 as components
from gmail_agent import GmailAIAgent
from file_reader import FileReader, human_size

st.set_page_config(layout="wide", page_title="AI Gmail Avatar Agent", page_icon="🤖")

CONFIG_FILE = "config.json"
LOG_FILE = "agent_activity.log"
PID_FILE = "daemon.pid"

def load_config():
    default_cfg = {
        "poll_interval_seconds": 300,
        "max_scan": 10,
        "auto_delete": False,
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

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def is_daemon_running():
    if not os.path.exists(PID_FILE):
        return False, None
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            pid = f.read().strip()
        if not pid:
            return False, None
        out = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /NH', shell=True).decode()
        if pid in out and "python" in out.lower():
            return True, pid
    except Exception:
        pass
    return False, None

cfg = load_config()

# Initialize Session State
if "avatar_remark" not in st.session_state:
    st.session_state["avatar_remark"] = (
        "Hello! I'm your AI Gmail Assistant. What would you like me to do with your inbox today?"
    )
if "last_results" not in st.session_state:
    st.session_state["last_results"] = []
if "is_speaking" not in st.session_state:
    st.session_state["is_speaking"] = True

# Sidebar Controls
st.sidebar.title("⚙️ Agent Controls")

env_key = os.environ.get("OPENAI_API_KEY", "")
api_key = st.sidebar.text_input(
    "OpenAI API Key",
    value=env_key,
    type="password",
    help="Enter your OpenAI API key or set OPENAI_API_KEY in your environment."
)

env_gemini_key = os.environ.get("GEMINI_API_KEY", "")
gemini_key = st.sidebar.text_input(
    "Gemini API Key (Optional)",
    value=env_gemini_key,
    type="password",
    help="Enter Google Gemini API key or set GEMINI_API_KEY in your environment."
)

st.sidebar.markdown("---")
st.sidebar.subheader("Continuous Operation")

daemon_active, active_pid = is_daemon_running()
if daemon_active:
    st.sidebar.success(f"🟢 Background Daemon: Active (PID: {active_pid})")
else:
    st.sidebar.info("⚪ Background Daemon: Stopped")

auto_pilot = st.sidebar.checkbox(
    "🔄 Browser Auto-Pilot",
    value=False,
    help="Continuously scans inbox at specified intervals while this browser tab remains open."
)

poll_minutes = st.sidebar.slider(
    "Scan Interval (Minutes)",
    min_value=1,
    max_value=30,
    value=max(1, cfg.get("poll_interval_seconds", 300) // 60),
    help="How frequently the agent checks for new unread emails."
)

st.sidebar.markdown("---")
st.sidebar.subheader("Triage Rules")

designated_text = "\n".join(cfg.get("designated_senders", ["client@example.com", "boss@company.com"]))
designated_input = st.sidebar.text_area(
    "Designated Senders (Auto-Draft)",
    designated_text,
    help="Emails from these senders get auto-drafted contextual replies."
)
designated_senders = [s.strip() for s in designated_input.splitlines() if s.strip()]

delete_text = "\n".join(cfg.get("delete_senders", ["spam@promos.com", "newsletter@ads.com"]))
delete_input = st.sidebar.text_area(
    "Blacklisted Senders (Delete / Trash)",
    delete_text,
    help="Emails matching these addresses/domains will be moved to trash."
)
delete_senders = [s.strip() for s in delete_input.splitlines() if s.strip()]

auto_delete = st.sidebar.checkbox(
    "Auto-trash Blacklisted Emails",
    value=cfg.get("auto_delete", False),
    help="If checked, matching blacklisted emails are trashed immediately."
)

max_scan = st.sidebar.slider("Max unread emails per scan", min_value=1, max_value=25, value=cfg.get("max_scan", 10))

grace_period = st.sidebar.number_input(
    "Keep new emails intact on top (Minutes)",
    min_value=0,
    max_value=720,
    value=cfg.get("grace_period_minutes", 60),
    help="New emails arriving within this window remain untouched, unread, and intact on top of your inbox."
)

char_options = ["🐶 Cute Puppy Dog", "🐰 Fluffy Bunny", "🐻 Teddy Bear"]
char_map = {"🐶 Cute Puppy Dog": "dog", "🐰 Fluffy Bunny": "bunny", "🐻 Teddy Bear": "bear"}
rev_char_map = {"dog": "🐶 Cute Puppy Dog", "bunny": "🐰 Fluffy Bunny", "bear": "🐻 Teddy Bear"}

current_char = cfg.get("avatar_character", "dog")
default_idx = 0
if current_char in ["dog", "bunny", "bear"]:
    default_idx = char_options.index(rev_char_map.get(current_char, "🐶 Cute Puppy Dog"))

selected_char_label = st.sidebar.selectbox(
    "Cute Avatar Character",
    options=char_options,
    index=default_idx,
    help="Choose your cute assistant companion!"
)
selected_char = char_map[selected_char_label]

# Save rules to config.json
updated_cfg = {
    "poll_interval_seconds": poll_minutes * 60,
    "max_scan": max_scan,
    "auto_delete": auto_delete,
    "grace_period_minutes": grace_period,
    "avatar_character": selected_char,
    "designated_senders": designated_senders,
    "delete_senders": delete_senders
}
if updated_cfg != cfg:
    save_config(updated_cfg)

# 3D Avatar HTML Generator with Ears, Lips, Eyes, and Talking Animation
def render_avatar_html(remark_text: str, char_type: str = "dog") -> str:
    escaped_remark = json.dumps(remark_text)
    escaped_char = json.dumps(char_type)
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: transparent;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            user-select: none;
        }}
        #avatar-container {{
            position: relative;
            width: 100%;
            height: 530px;
            background: radial-gradient(circle at 50% 25%, #1e1b4b 0%, #0f172a 100%);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 12px 36px rgba(0,0,0,0.5);
            border: 1px solid rgba(56, 189, 248, 0.25);
        }}
        #top-bar {{
            position: absolute;
            top: 14px;
            left: 16px;
            right: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 20;
            pointer-events: none;
        }}
        .status-pill {{
            pointer-events: auto;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(15, 23, 42, 0.85);
            padding: 6px 14px;
            border-radius: 20px;
            border: 1px solid rgba(147, 197, 253, 0.25);
            backdrop-filter: blur(8px);
            color: #93c5fd;
            font-size: 12.5px;
            font-weight: 500;
        }}
        .pulse-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #22c55e;
            box-shadow: 0 0 10px #22c55e;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); opacity: 0.8; }}
            50% {{ transform: scale(1.25); opacity: 1; }}
            100% {{ transform: scale(0.95); opacity: 0.8; }}
        }}
        .voice-btn {{
            pointer-events: auto;
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(147, 197, 253, 0.25);
            color: #93c5fd;
            padding: 6px 12px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 12px;
            backdrop-filter: blur(8px);
            transition: all 0.2s ease;
        }}
        .voice-btn:hover {{
            background: rgba(30, 41, 59, 0.95);
            color: #ffffff;
            border-color: #38bdf8;
        }}
        #canvas-mount {{
            width: 100%;
            height: 100%;
            cursor: grab;
        }}
        #canvas-mount:active {{
            cursor: grabbing;
        }}
        /* Speech Text Balloon with Tail Pointing to Mouth */
        #speech-balloon {{
            position: absolute;
            bottom: 14px;
            left: 14px;
            right: 14px;
            background: rgba(15, 23, 42, 0.95);
            border: 2px solid rgba(56, 189, 248, 0.55);
            border-radius: 18px;
            padding: 12px 18px;
            backdrop-filter: blur(14px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.6);
            z-index: 20;
            transition: all 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            transform-origin: top center;
        }}

        /* Triangular Speech Balloon Tail pointing UP to the avatar's lips */
        #speech-balloon::before {{
            content: '';
            position: absolute;
            top: -12px;
            left: 50%;
            transform: translateX(-50%);
            width: 0;
            height: 0;
            border-left: 11px solid transparent;
            border-right: 11px solid transparent;
            border-bottom: 12px solid rgba(56, 189, 248, 0.65);
        }}

        #speech-balloon::after {{
            content: '';
            position: absolute;
            top: -9px;
            left: 50%;
            transform: translateX(-50%);
            width: 0;
            height: 0;
            border-left: 9px solid transparent;
            border-right: 9px solid transparent;
            border-bottom: 10px solid #0f172a;
        }}

        /* Active Speaking Glow & Bounce Effect */
        #speech-balloon.speaking {{
            border-color: #38bdf8;
            box-shadow: 0 0 26px rgba(56, 189, 248, 0.55);
            animation: balloon-pop 0.35s ease;
        }}

        @keyframes balloon-pop {{
            0% {{ transform: scale(0.94); }}
            50% {{ transform: scale(1.02); }}
            100% {{ transform: scale(1.0); }}
        }}

        .balloon-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 5px;
        }}

        .balloon-title {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #38bdf8;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .sound-wave-bars {{
            display: inline-flex;
            align-items: center;
            gap: 2.5px;
            height: 12px;
        }}

        .sound-wave-bars span {{
            width: 2.5px;
            height: 100%;
            background: #38bdf8;
            border-radius: 2px;
            animation: wave-bar 0.7s infinite ease-in-out alternate;
        }}

        .sound-wave-bars span:nth-child(1) {{ animation-delay: 0.0s; }}
        .sound-wave-bars span:nth-child(2) {{ animation-delay: 0.25s; }}
        .sound-wave-bars span:nth-child(3) {{ animation-delay: 0.15s; }}
        .sound-wave-bars span:nth-child(4) {{ animation-delay: 0.35s; }}

        @keyframes wave-bar {{
            0% {{ height: 3px; }}
            100% {{ height: 12px; }}
        }}

        .speaking-badge {{
            display: none;
            font-size: 10px;
            font-weight: 600;
            color: #c084fc;
            background: rgba(192, 132, 252, 0.18);
            padding: 2px 7px;
            border-radius: 8px;
            align-items: center;
            gap: 5px;
        }}

        #balloon-text {{
            color: #f8fafc;
            font-size: 14px;
            line-height: 1.45;
            font-weight: 450;
            max-height: 80px;
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <div id="avatar-container">
        <div id="top-bar">
            <div class="status-pill">
                <div class="pulse-dot"></div>
                <span id="agent-status">AI Avatar Active</span>
            </div>
            <button id="voice-toggle" class="voice-btn">🔊 Voice: OFF</button>
        </div>

        <div id="canvas-mount"></div>

        <!-- Animated Speech Text Balloon with Pointer Tail -->
        <div id="speech-balloon">
            <div class="balloon-header">
                <span class="balloon-title">
                    <span>💬 AI Avatar</span>
                </span>
                <span id="speaking-badge" class="speaking-badge">
                    <span class="sound-wave-bars active">
                        <span></span><span></span><span></span><span></span>
                    </span>
                    <span>Speaking...</span>
                </span>
            </div>
            <div id="balloon-text"></div>
        </div>
    </div>

    <script type="module">
        import * as THREE from 'https://esm.sh/three@0.160.0';
        import {{ OrbitControls }} from 'https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js';

        const initialRemark = {escaped_remark};
        let voiceEnabled = false;

        const remarkEl = document.getElementById('balloon-text') || document.getElementById('remark-text');
        const speakingBadge = document.getElementById('speaking-badge');
        const speechBalloon = document.getElementById('speech-balloon') || document.getElementById('message-box');
        const voiceBtn = document.getElementById('voice-toggle');
        const container = document.getElementById('canvas-mount');

        remarkEl.innerText = initialRemark;

        // Web Speech Setup
        voiceBtn.addEventListener('click', () => {{
            voiceEnabled = !voiceEnabled;
            voiceBtn.innerText = voiceEnabled ? "🔊 Voice: ON" : "🔇 Voice: OFF";
            if (voiceEnabled && window.speechSynthesis) {{
                speakRemark(initialRemark);
            }} else if (!voiceEnabled && window.speechSynthesis) {{
                window.speechSynthesis.cancel();
            }}
        }});

        function speakRemark(text) {{
            if (!('speechSynthesis' in window)) return;
            window.speechSynthesis.cancel();
            const cleanText = text.replace(/[^a-zA-Z0-9\\s.,?!'-]/g, '');
            const utter = new SpeechSynthesisUtterance(cleanText);
            utter.rate = 1.05;
            utter.pitch = 1.0;
            window.speechSynthesis.speak(utter);
        }}

        // Three.js Scene Setup
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(40, container.clientWidth / container.clientHeight, 0.1, 100);
        camera.position.set(0, 1.44, 1.6);

        const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        container.appendChild(renderer.domElement);

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.target.set(0, 1.38, 0);
        controls.minDistance = 1.1;
        controls.maxDistance = 2.8;
        controls.maxPolarAngle = Math.PI / 2 + 0.1;
        controls.update();

        // Soft Studio Lighting
        const amb = new THREE.AmbientLight(0xffffff, 1.45);
        scene.add(amb);

        const keyLight = new THREE.DirectionalLight(0xffeedd, 2.2);
        keyLight.position.set(2, 3, 2.5);
        scene.add(keyLight);

        const fillLight = new THREE.DirectionalLight(0xdbeafe, 1.5);
        fillLight.position.set(-2, 2, 1);
        scene.add(fillLight);

        const rimLight = new THREE.PointLight(0xfef08a, 2.0, 5);
        rimLight.position.set(0, 0.4, 1.1);
        scene.add(rimLight);

        // Character Selection
        const charType = {escaped_char};

        const headGroup = new THREE.Group();
        const bodyGroup = new THREE.Group();
        scene.add(bodyGroup);
        scene.add(headGroup);

        function createCuteEye(x, irisColor, lidColor) {{
            const eyeGroup = new THREE.Group();
            const white = new THREE.Mesh(
                new THREE.SphereGeometry(0.066, 24, 24),
                new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.15 }})
            );
            white.scale.set(1.0, 0.92, 0.55);
            eyeGroup.add(white);

            const iris = new THREE.Mesh(
                new THREE.SphereGeometry(0.046, 24, 24),
                new THREE.MeshStandardMaterial({{ color: irisColor, roughness: 0.25 }})
            );
            iris.position.set(0, 0, 0.024);
            iris.scale.set(1.0, 1.0, 0.35);
            eyeGroup.add(iris);

            const pupil = new THREE.Mesh(
                new THREE.SphereGeometry(0.026, 24, 24),
                new THREE.MeshStandardMaterial({{ color: 0x09090b }})
            );
            pupil.position.set(0, 0, 0.038);
            pupil.scale.set(1.0, 1.0, 0.25);
            eyeGroup.add(pupil);

            // Double Catchlight Sparkles
            const s1 = new THREE.Mesh(new THREE.SphereGeometry(0.013, 16, 16), new THREE.MeshBasicMaterial({{ color: 0xffffff }}));
            s1.position.set(0.014, 0.016, 0.052);
            eyeGroup.add(s1);

            const s2 = new THREE.Mesh(new THREE.SphereGeometry(0.007, 12, 12), new THREE.MeshBasicMaterial({{ color: 0xffffff }}));
            s2.position.set(-0.012, -0.012, 0.052);
            eyeGroup.add(s2);

            const upperLid = new THREE.Mesh(
                new THREE.SphereGeometry(0.072, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.5),
                new THREE.MeshStandardMaterial({{ color: lidColor, roughness: 0.65 }})
            );
            upperLid.rotation.x = Math.PI;
            upperLid.scale.set(1.06, 0.01, 1.06);
            eyeGroup.add(upperLid);

            eyeGroup.position.set(x, 1.42, 0.30);
            eyeGroup.userData = {{ upperLid: upperLid, iris: iris }};
            return eyeGroup;
        }}

        function createRosyCheek(x, y, z, color = 0xf472b6) {{
            const cheek = new THREE.Mesh(
                new THREE.SphereGeometry(0.055, 16, 16),
                new THREE.MeshBasicMaterial({{ color: color, transparent: true, opacity: 0.58 }})
            );
            cheek.scale.set(1.0, 0.65, 0.3);
            cheek.position.set(x, y, z);
            return cheek;
        }}

        let leftEar, rightEar, leftEye, rightEye, lowerLip, cavity, tongue;

        if (charType === 'bunny') {{
            // 🐰 Fluffy Bunny
            const furColor = 0xf8fafc;
            const furMat = new THREE.MeshStandardMaterial({{ color: furColor, roughness: 0.72 }});
            const headMesh = new THREE.Mesh(new THREE.SphereGeometry(0.36, 32, 32), furMat);
            headMesh.scale.set(1.05, 0.98, 0.95);
            headMesh.position.set(0, 1.38, 0);
            headGroup.add(headMesh);

            const snout = new THREE.Mesh(new THREE.SphereGeometry(0.15, 24, 24), furMat);
            snout.scale.set(1.15, 0.8, 0.95);
            snout.position.set(0, 1.28, 0.26);
            headGroup.add(snout);

            const nose = new THREE.Mesh(new THREE.ConeGeometry(0.035, 0.04, 16), new THREE.MeshStandardMaterial({{ color: 0xf472b6, roughness: 0.3 }}));
            nose.rotation.x = Math.PI;
            nose.position.set(0, 1.34, 0.39);
            headGroup.add(nose);

            function createBunnyEar(isLeft) {{
                const pivot = new THREE.Group();
                pivot.position.set(isLeft ? -0.16 : 0.16, 1.66, -0.02);
                const outer = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.088, 0.52, 24), furMat);
                outer.scale.set(0.8, 1.0, 0.38);
                outer.position.set(0, 0.24, 0);
                pivot.add(outer);

                const inner = new THREE.Mesh(new THREE.CylinderGeometry(0.038, 0.065, 0.44, 20), new THREE.MeshStandardMaterial({{ color: 0xfbcfe8, roughness: 0.6 }}));
                inner.scale.set(0.75, 1.0, 0.2);
                inner.position.set(0, 0.24, 0.015);
                pivot.add(inner);

                pivot.rotation.z = isLeft ? -0.16 : 0.16;
                pivot.rotation.x = -0.08;
                return pivot;
            }}
            leftEar = createBunnyEar(true);
            rightEar = createBunnyEar(false);
            headGroup.add(leftEar);
            headGroup.add(rightEar);

            leftEye = createCuteEye(-0.13, 0x1e3a8a, furColor);
            rightEye = createCuteEye(0.13, 0x1e3a8a, furColor);
            headGroup.add(leftEye);
            headGroup.add(rightEye);

            headGroup.add(createRosyCheek(-0.23, 1.29, 0.27, 0xf472b6));
            headGroup.add(createRosyCheek(0.23, 1.29, 0.27, 0xf472b6));

            const mouthGroup = new THREE.Group();
            mouthGroup.position.set(0, 1.22, 0.32);

            const toothMat = new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.2 }});
            const tL = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.03, 0.012), toothMat);
            tL.position.set(-0.014, 0.01, 0.01);
            mouthGroup.add(tL);
            const tR = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.03, 0.012), toothMat);
            tR.position.set(0.014, 0.01, 0.01);
            mouthGroup.add(tR);

            lowerLip = new THREE.Mesh(new THREE.TorusGeometry(0.045, 0.012, 12, 24, Math.PI), new THREE.MeshStandardMaterial({{ color: 0xf472b6 }}));
            lowerLip.position.set(0, -0.015, 0);
            mouthGroup.add(lowerLip);

            cavity = new THREE.Mesh(new THREE.SphereGeometry(0.04, 16, 16), new THREE.MeshBasicMaterial({{ color: 0x4a044e }}));
            cavity.scale.set(1.0, 0.35, 0.2);
            cavity.position.set(0, -0.005, -0.01);
            mouthGroup.add(cavity);

            tongue = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 16), new THREE.MeshStandardMaterial({{ color: 0xf43f5e }}));
            tongue.scale.set(1.0, 0.3, 1.1);
            tongue.position.set(0, -0.012, 0.015);
            mouthGroup.add(tongue);
            headGroup.add(mouthGroup);

            const body = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.42, 0.52, 24), furMat);
            body.position.set(0, 0.83, 0);
            bodyGroup.add(body);

            const bowMat = new THREE.MeshStandardMaterial({{ color: 0x06b6d4, roughness: 0.35 }});
            const bowL = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.12, 16), bowMat);
            bowL.rotation.z = Math.PI / 2;
            bowL.position.set(-0.065, 1.07, 0.20);
            bodyGroup.add(bowL);
            const bowR = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.12, 16), bowMat);
            bowR.rotation.z = -Math.PI / 2;
            bowR.position.set(0.065, 1.07, 0.20);
            bodyGroup.add(bowR);
            const knot = new THREE.Mesh(new THREE.SphereGeometry(0.032, 16, 16), new THREE.MeshStandardMaterial({{ color: 0x0891b2 }}));
            knot.position.set(0, 1.07, 0.22);
            bodyGroup.add(knot);

        }} else if (charType === 'bear') {{
            // 🐻 Teddy Bear
            const furColor = 0x854d0e;
            const furMat = new THREE.MeshStandardMaterial({{ color: furColor, roughness: 0.8 }});
            const headMesh = new THREE.Mesh(new THREE.SphereGeometry(0.38, 32, 32), furMat);
            headMesh.scale.set(1.08, 0.98, 0.96);
            headMesh.position.set(0, 1.40, 0);
            headGroup.add(headMesh);

            function createBearEar(isLeft) {{
                const pivot = new THREE.Group();
                pivot.position.set(isLeft ? -0.28 : 0.28, 1.68, 0.0);
                const outer = new THREE.Mesh(new THREE.SphereGeometry(0.13, 24, 24), furMat);
                outer.scale.set(1.0, 1.0, 0.45);
                pivot.add(outer);

                const inner = new THREE.Mesh(new THREE.SphereGeometry(0.085, 20, 20), new THREE.MeshStandardMaterial({{ color: 0xfde68a, roughness: 0.7 }}));
                inner.scale.set(1.0, 1.0, 0.35);
                inner.position.set(0, 0, 0.025);
                pivot.add(inner);
                pivot.rotation.z = isLeft ? 0.3 : -0.3;
                return pivot;
            }}
            leftEar = createBearEar(true);
            rightEar = createBearEar(false);
            headGroup.add(leftEar);
            headGroup.add(rightEar);

            const snout = new THREE.Mesh(new THREE.SphereGeometry(0.18, 24, 24), new THREE.MeshStandardMaterial({{ color: 0xfde68a, roughness: 0.7 }}));
            snout.scale.set(1.15, 0.88, 1.0);
            snout.position.set(0, 1.30, 0.26);
            headGroup.add(snout);

            const nose = new THREE.Mesh(new THREE.SphereGeometry(0.048, 16, 16), new THREE.MeshStandardMaterial({{ color: 0x1f2937, roughness: 0.25 }}));
            nose.scale.set(1.2, 0.85, 0.9);
            nose.position.set(0, 1.34, 0.43);
            headGroup.add(nose);

            leftEye = createCuteEye(-0.14, 0x1c1917, furColor);
            rightEye = createCuteEye(0.14, 0x1c1917, furColor);
            headGroup.add(leftEye);
            headGroup.add(rightEye);

            headGroup.add(createRosyCheek(-0.25, 1.31, 0.28, 0xfb923c));
            headGroup.add(createRosyCheek(0.25, 1.31, 0.28, 0xfb923c));

            const mouthGroup = new THREE.Group();
            mouthGroup.position.set(0, 1.23, 0.33);

            lowerLip = new THREE.Mesh(new THREE.TorusGeometry(0.052, 0.014, 12, 24, Math.PI), new THREE.MeshStandardMaterial({{ color: 0x9a3412 }}));
            lowerLip.position.set(0, -0.012, 0);
            mouthGroup.add(lowerLip);

            cavity = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 16), new THREE.MeshBasicMaterial({{ color: 0x300c04 }}));
            cavity.scale.set(1.1, 0.35, 0.2);
            cavity.position.set(0, -0.005, -0.01);
            mouthGroup.add(cavity);

            tongue = new THREE.Mesh(new THREE.SphereGeometry(0.035, 16, 16), new THREE.MeshStandardMaterial({{ color: 0xf43f5e }}));
            tongue.scale.set(1.0, 0.32, 1.2);
            tongue.position.set(0, -0.012, 0.018);
            mouthGroup.add(tongue);
            headGroup.add(mouthGroup);

            const body = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.44, 0.55, 24), furMat);
            body.position.set(0, 0.83, 0);
            bodyGroup.add(body);

            const bowMat = new THREE.MeshStandardMaterial({{ color: 0x2563eb, roughness: 0.4 }});
            const bowL = new THREE.Mesh(new THREE.ConeGeometry(0.075, 0.13, 16), bowMat);
            bowL.rotation.z = Math.PI / 2;
            bowL.position.set(-0.07, 1.07, 0.21);
            bodyGroup.add(bowL);
            const bowR = new THREE.Mesh(new THREE.ConeGeometry(0.075, 0.13, 16), bowMat);
            bowR.rotation.z = -Math.PI / 2;
            bowR.position.set(0.07, 1.07, 0.21);
            bodyGroup.add(bowR);
            const knot = new THREE.Mesh(new THREE.SphereGeometry(0.035, 16, 16), new THREE.MeshStandardMaterial({{ color: 0xef4444 }}));
            knot.position.set(0, 1.07, 0.23);
            bodyGroup.add(knot);

        }} else {{
            // 🐶 Cute Puppy Dog (Default)
            const furColor = 0xdf984b;
            const furMat = new THREE.MeshStandardMaterial({{ color: furColor, roughness: 0.68, metalness: 0.02 }});
            const headMesh = new THREE.Mesh(new THREE.SphereGeometry(0.38, 32, 32), furMat);
            headMesh.scale.set(1.08, 0.98, 0.96);
            headMesh.position.set(0, 1.40, 0);
            headGroup.add(headMesh);

            const snoutMat = new THREE.MeshStandardMaterial({{ color: 0xfff7ed, roughness: 0.7 }});
            const snout = new THREE.Mesh(new THREE.SphereGeometry(0.18, 24, 24), snoutMat);
            snout.scale.set(1.18, 0.88, 1.05);
            snout.position.set(0, 1.30, 0.25);
            headGroup.add(snout);

            const nose = new THREE.Mesh(
                new THREE.SphereGeometry(0.048, 16, 16),
                new THREE.MeshStandardMaterial({{ color: 0x18181b, roughness: 0.15, metalness: 0.1 }})
            );
            nose.scale.set(1.2, 0.85, 0.9);
            nose.position.set(0, 1.34, 0.435);
            headGroup.add(nose);

            function createDogEar(isLeft) {{
                const pivot = new THREE.Group();
                pivot.position.set(isLeft ? -0.34 : 0.34, 1.52, 0.02);
                const earGeo = new THREE.CylinderGeometry(0.065, 0.13, 0.38, 24);
                earGeo.scale(0.65, 1.0, 1.0);
                const earMesh = new THREE.Mesh(earGeo, new THREE.MeshStandardMaterial({{ color: isLeft ? 0xdf984b : 0xba6a22, roughness: 0.7 }}));
                earMesh.position.set(0, -0.16, 0);
                earMesh.rotation.z = isLeft ? -0.34 : 0.34;
                pivot.add(earMesh);
                return pivot;
            }}
            leftEar = createDogEar(true);
            rightEar = createDogEar(false);
            headGroup.add(leftEar);
            headGroup.add(rightEar);

            leftEye = createCuteEye(-0.14, 0x3e1f07, furColor);
            rightEye = createCuteEye(0.14, 0x3e1f07, furColor);
            headGroup.add(leftEye);
            headGroup.add(rightEye);

            headGroup.add(createRosyCheek(-0.24, 1.31, 0.28, 0xf472b6));
            headGroup.add(createRosyCheek(0.24, 1.31, 0.28, 0xf472b6));

            const mouthGroup = new THREE.Group();
            mouthGroup.position.set(0, 1.23, 0.33);

            const lipMat = new THREE.MeshStandardMaterial({{ color: 0x475569, roughness: 0.5 }});
            const lipL = new THREE.Mesh(new THREE.TorusGeometry(0.042, 0.011, 12, 20, Math.PI), lipMat);
            lipL.rotation.x = Math.PI;
            lipL.position.set(-0.038, 0.015, 0);
            mouthGroup.add(lipL);
            const lipR = new THREE.Mesh(new THREE.TorusGeometry(0.042, 0.011, 12, 20, Math.PI), lipMat);
            lipR.rotation.x = Math.PI;
            lipR.position.set(0.038, 0.015, 0);
            mouthGroup.add(lipR);

            lowerLip = new THREE.Mesh(new THREE.TorusGeometry(0.052, 0.015, 12, 24, Math.PI), new THREE.MeshStandardMaterial({{ color: 0xd9777f, roughness: 0.5 }}));
            lowerLip.position.set(0, -0.012, 0);
            mouthGroup.add(lowerLip);

            cavity = new THREE.Mesh(new THREE.SphereGeometry(0.046, 16, 16), new THREE.MeshBasicMaterial({{ color: 0x3f0713 }}));
            cavity.scale.set(1.1, 0.35, 0.2);
            cavity.position.set(0, -0.005, -0.01);
            mouthGroup.add(cavity);

            tongue = new THREE.Mesh(new THREE.SphereGeometry(0.036, 16, 16), new THREE.MeshStandardMaterial({{ color: 0xf43f5e, roughness: 0.4 }}));
            tongue.scale.set(1.0, 0.32, 1.25);
            tongue.position.set(0, -0.012, 0.02);
            mouthGroup.add(tongue);
            headGroup.add(mouthGroup);

            const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.20, 0.18, 24), furMat);
            neck.position.set(0, 1.16, 0);
            bodyGroup.add(neck);

            const body = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.44, 0.55, 24), furMat);
            body.position.set(0, 0.83, 0);
            bodyGroup.add(body);

            const collar = new THREE.Mesh(
                new THREE.TorusGeometry(0.18, 0.026, 16, 32),
                new THREE.MeshStandardMaterial({{ color: 0xef4444, roughness: 0.35 }})
            );
            collar.rotation.x = Math.PI / 2;
            collar.position.set(0, 1.08, 0);
            bodyGroup.add(collar);

            const bell = new THREE.Mesh(
                new THREE.SphereGeometry(0.042, 16, 16),
                new THREE.MeshStandardMaterial({{ color: 0xfbbf24, metalness: 0.8, roughness: 0.2 }})
            );
            bell.position.set(0, 1.04, 0.21);
            bodyGroup.add(bell);
        }}

        // Mouse look-around interaction
        let targetLookX = 0;
        let targetLookY = 0;
        container.addEventListener('mousemove', (e) => {{
            const rect = container.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
            targetLookX = x * 0.18;
            targetLookY = y * 0.12;
        }});
        container.addEventListener('mouseleave', () => {{
            targetLookX = 0;
            targetLookY = 0;
        }});

        // Resize Observer
        window.addEventListener('resize', () => {{
            if (!container) return;
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }});

        // Speech & Animation State
        let isSpeaking = true;
        const durationSec = Math.min(10, Math.max(3.5, initialRemark.length * 0.055));

        speakingBadge.style.display = 'inline-flex';
        speechBalloon.classList.add('speaking');

        setTimeout(() => {{
            isSpeaking = false;
            speakingBadge.style.display = 'none';
            speechBalloon.classList.remove('speaking');
        }}, durationSec * 1000);

        let lastBlinkTime = 0;
        const clock = new THREE.Clock();

        function animate() {{
            requestAnimationFrame(animate);
            const time = clock.getElapsedTime();
            controls.update();

            // Natural Blinking
            if (time - lastBlinkTime > 3.6) {{
                const blinkProgress = (time - lastBlinkTime - 3.6) / 0.16;
                if (blinkProgress <= 1.0) {{
                    const blinkScale = Math.sin(blinkProgress * Math.PI) * 1.05;
                    if (leftEye?.userData?.upperLid) leftEye.userData.upperLid.scale.y = Math.max(0.01, blinkScale);
                    if (rightEye?.userData?.upperLid) rightEye.userData.upperLid.scale.y = Math.max(0.01, blinkScale);
                }} else {{
                    if (leftEye?.userData?.upperLid) leftEye.userData.upperLid.scale.y = 0.01;
                    if (rightEye?.userData?.upperLid) rightEye.userData.upperLid.scale.y = 0.01;
                    lastBlinkTime = time;
                }}
            }}

            // Idle Breathing
            headGroup.position.y = Math.sin(time * 2.0) * 0.014;
            bodyGroup.position.y = Math.sin(time * 2.0) * 0.007;

            // Lip Movement / Speech & Ear Animation
            if (isSpeaking) {{
                const mouthMv = Math.abs(Math.sin(time * 14)) * 0.042;
                if (lowerLip) lowerLip.position.y = -0.012 - mouthMv;
                if (cavity) cavity.scale.y = 0.35 + mouthMv * 24;
                if (tongue) tongue.position.y = -0.012 + mouthMv * 0.65;

                if (charType === 'dog' && leftEar && rightEar) {{
                    const earBounce = Math.abs(Math.sin(time * 10)) * 0.12;
                    leftEar.rotation.z = -earBounce;
                    rightEar.rotation.z = earBounce;
                }} else if (charType === 'bunny' && leftEar && rightEar) {{
                    leftEar.rotation.x = -0.08 + Math.sin(time * 13) * 0.10;
                    rightEar.rotation.x = -0.08 + Math.cos(time * 13) * 0.10;
                }} else if (charType === 'bear' && leftEar && rightEar) {{
                    leftEar.rotation.z = Math.sin(time * 9) * 0.08;
                    rightEar.rotation.z = -Math.sin(time * 9) * 0.08;
                }}

                const headSpeakNod = Math.sin(time * 6) * 0.024;
                const headSpeakTurn = Math.sin(time * 2.5) * 0.032;
                headGroup.rotation.y = THREE.MathUtils.lerp(headGroup.rotation.y, targetLookX + headSpeakTurn, 0.08);
                headGroup.rotation.x = THREE.MathUtils.lerp(headGroup.rotation.x, -targetLookY + headSpeakNod, 0.08);
            }} else {{
                if (lowerLip) lowerLip.position.y = -0.012;
                if (cavity) cavity.scale.y = 0.35;
                if (tongue) tongue.position.y = -0.012;

                if (charType === 'dog' && leftEar && rightEar) {{
                    leftEar.rotation.z = THREE.MathUtils.lerp(leftEar.rotation.z, 0, 0.05);
                    rightEar.rotation.z = THREE.MathUtils.lerp(rightEar.rotation.z, 0, 0.05);
                }} else if (charType === 'bunny' && leftEar && rightEar) {{
                    const twitch = Math.sin(time * 1.5) > 0.95 ? Math.sin(time * 20) * 0.06 : 0;
                    leftEar.rotation.x = -0.08 + twitch;
                    rightEar.rotation.x = -0.08 - twitch;
                }} else if (charType === 'bear' && leftEar && rightEar) {{
                    leftEar.rotation.z = THREE.MathUtils.lerp(leftEar.rotation.z, 0, 0.05);
                    rightEar.rotation.z = THREE.MathUtils.lerp(rightEar.rotation.z, 0, 0.05);
                }}

                headGroup.rotation.y = THREE.MathUtils.lerp(headGroup.rotation.y, targetLookX, 0.06);
                headGroup.rotation.x = THREE.MathUtils.lerp(headGroup.rotation.x, -targetLookY, 0.06);
            }}

            renderer.render(scene, camera);
        }}
        animate();
    </script>
</body>
</html>
"""

# Header
st.title("🤖 AI Gmail Avatar Assistant")
st.caption("Interactive 3D Avatar with facial expressions, real-time message box remarks, and automated email triage")

col1, col2 = st.columns([1.1, 1], gap="large")

with col1:
    st.subheader(f"👤 {selected_char_label} Assistant")
    components.html(render_avatar_html(st.session_state["avatar_remark"], char_type=selected_char), height=540)

    # Avatar Command / Input Box
    st.markdown("#### 💬 Tell Your Avatar What To Do")

    # Quick Action Buttons
    q_sort, q_block, q1, q2, q3, q4, q5, q6, q7 = st.columns(9)
    quick_action = None
    with q_sort:
        if st.button("👥 Sort Sender-Wise", use_container_width=True):
            quick_action = "I need to sort my mails sender wise"
    with q_block:
        if st.button("🚫 Block Sender", use_container_width=True):
            quick_action = "Who is blocked"
    with q1:
        if st.button("✉️ Draft Reply", use_container_width=True):
            quick_action = "Make a draft reply to the latest email"
    with q2:
        if st.button("📎 Attachment", use_container_width=True):
            quick_action = "Summarize mail with attachment"
    with q3:
        if st.button("📑 Folder", use_container_width=True):
            quick_action = "Summarize all emails in this folder and prepare synopses"
    with q4:
        if st.button("🚀 Scan", use_container_width=True):
            quick_action = "Scan my inbox and categorize all unread emails"
    with q5:
        if st.button("📊 Unread", use_container_width=True):
            quick_action = "How many unread emails do I have?"
    with q6:
        if st.button("🧹 Spam", use_container_width=True):
            quick_action = "Delete all previous mails from blocked senders"
    with q7:
        if st.button("❓ Help", use_container_width=True):
            quick_action = "What can you do?"

    # Chat Input Box
    user_input = st.chat_input("Ask or command your avatar (e.g., 'Sort my mails sender wise', 'Block sender spam@promos.com', 'Scan now')...")

    active_prompt = quick_action or user_input

    if active_prompt:
        if not os.path.exists("token.json") and not os.path.exists("credentials.json"):
            st.error("⚠️ Google OAuth credentials or token not found.")
        else:
            with st.spinner("Avatar is processing your request..."):
                try:
                    agent = GmailAIAgent(
                        designated_senders=designated_senders,
                        delete_senders=delete_senders,
                        api_key=api_key or None,
                        gemini_api_key=gemini_key or None
                    )
                    remark, results = agent.handle_user_prompt(
                        active_prompt,
                        auto_delete=auto_delete,
                        max_results=max_scan,
                        grace_period_minutes=grace_period
                    )
                    st.session_state["avatar_remark"] = remark
                    if results:
                        st.session_state["last_results"] = results
                    if getattr(agent, "last_sender_groups", None):
                        st.session_state["sender_groups"] = agent.last_sender_groups
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error communicating with agent: {e}")

with col2:
    tab_files, tab_sender, tab_folder, tab_triage, tab_daemon = st.tabs([
        "📂 Multi-Format File Reader",
        "👥 Sender-Wise Mails & Groups",
        "📁 Folder Mails & Mouseover Synopsis",
        "📬 Unread Triage Results",
        "🖥️ Background Service & Logs"
    ])

    with tab_files:
        st.subheader("📂 Multi-Format Document, Image & Binary Reader")
        st.caption("Read, inspect, and analyze all files: .txt, .docx, .xlsx, .pdf, .png, .gif, and arbitrary binary files (.bin, .dat, .zip, etc.).")

        file_mode = st.radio("Choose Input Method:", ["📤 Upload File", "📁 Local File Path"], horizontal=True)

        loaded_result = None
        file_bytes_data = None
        file_name_display = ""

        # Initialize file reader with active OpenAI/Gemini client if available
        active_client = None
        if gemini_key:
            try:
                from openai import OpenAI
                active_client = OpenAI(
                    api_key=gemini_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
                )
            except Exception:
                pass
        elif api_key:
            try:
                from openai import OpenAI
                active_client = OpenAI(api_key=api_key)
            except Exception:
                pass
        reader = FileReader(openai_client=active_client)

        if file_mode == "📤 Upload File":
            uploaded_file = st.file_uploader(
                "Drop or browse ANY file (.txt, .docx, .xlsx, .pdf, .png, .gif, .bin, .dat, .zip, etc.):",
                type=None,
                help="Accepts all document, spreadsheet, PDF, image, animation, archive, and binary formats."
            )
            if uploaded_file is not None:
                file_bytes_data = uploaded_file.read()
                file_name_display = uploaded_file.name
                with st.spinner(f"AI Agent reading and analyzing '{file_name_display}'..."):
                    loaded_result = reader.read_bytes(file_bytes_data, filename=file_name_display)
        else:
            p_col1, p_col2 = st.columns([3, 1])
            with p_col1:
                path_input = st.text_input("Enter local file path on this computer:", placeholder="e.g. D:\\mail_agent\\invoice.pdf")
            with p_col2:
                st.write("")
                st.write("")
                load_path_btn = st.button("🔍 Read File", use_container_width=True)

            if load_path_btn and path_input:
                if not os.path.exists(path_input):
                    st.error(f"❌ File does not exist: `{path_input}`")
                elif not os.path.isfile(path_input):
                    st.error(f"❌ Specified path is a folder, not a file: `{path_input}`")
                else:
                    with open(path_input, "rb") as pf:
                        file_bytes_data = pf.read()
                    file_name_display = os.path.basename(path_input)
                    with st.spinner(f"AI Agent reading '{file_name_display}'..."):
                        loaded_result = reader.read_bytes(file_bytes_data, filename=file_name_display)

        if loaded_result:
            st.session_state["current_analyzed_file"] = loaded_result

            fn = loaded_result.get("filename", "File")
            ftype = loaded_result.get("file_type", "Binary")
            fsize = loaded_result.get("size_human", "0 B")
            summary = loaded_result.get("summary", "")
            meta = loaded_result.get("metadata", {})

            # Metric Columns
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("File Name", fn[:20] + ("..." if len(fn) > 20 else ""))
            mc2.metric("Detected Format", ftype)
            mc3.metric("Size", fsize)
            entropy_val = meta.get("entropy", "N/A")
            mc4.metric("Entropy", f"{entropy_val} / 8.0" if entropy_val != "N/A" else "N/A")

            st.success(f"🤖 **Avatar Summary:** {summary}")
            if loaded_result.get("key_points"):
                st.markdown("##### 📌 Key Highlights & Sections")
                for kp in loaded_result["key_points"]:
                    st.markdown(f"- {kp}")

            # Sub-tabs for content inspection
            st_content, st_tables, st_visual, st_binary, st_chat = st.tabs([
                "📄 Extracted Text & Content",
                "📊 Spreadsheets & Tables",
                "🖼️ Visual Preview & AI Vision",
                "🔬 Binary Hex & Strings",
                "💬 Ask Avatar About This File"
            ])

            with st_content:
                st.markdown("#### Extracted Text Content")
                text_c = loaded_result.get("text_content", "")
                if text_c:
                    if len(text_c) > 50000:
                        st.info(f"Displaying first 50,000 characters (total: {len(text_c):,} characters).")
                    st.text_area("Full Content", value=text_c[:50000], height=320)
                else:
                    st.info("No raw text content extracted. Check the Binary or Visual tab for inspection.")

            with st_tables:
                st.markdown("#### Tabular Data / Spreadsheets")
                tables = loaded_result.get("tables", [])
                if tables:
                    for t in tables:
                        tname = t.get("name", "Table")
                        st.markdown(f"##### 📋 {tname}")
                        st.markdown(t.get("markdown", ""))
                else:
                    st.info("No tables or spreadsheets detected in this file.")

            with st_visual:
                st.markdown("#### Visual Preview & AI Vision Analysis")
                ext_l = loaded_result.get("extension", "").lower()
                if ext_l in ["png", "jpg", "jpeg", "webp", "bmp", "gif"] and file_bytes_data:
                    st.image(file_bytes_data, caption=f"{fn} ({meta.get('dimensions', '')})", use_container_width=True)
                    if ext_l == "gif":
                        st.info(f"🎞️ Animated GIF: {meta.get('frame_count', 1)} frames | Estimated Duration: {meta.get('estimated_duration', 'Static')}")
                    if active_client:
                        st.markdown("##### 👁️ OpenAI Vision OCR & Visual Analysis:")
                        st.write(loaded_result.get("text_content", ""))
                    else:
                        st.info("💡 Add your OpenAI API Key in the left sidebar to enable automatic AI Vision OCR & image description.")
                else:
                    st.info("This is not an image or GIF file.")

            with st_binary:
                st.markdown("#### Binary Inspection, Hashes & Hex Dump")
                bc1, bc2 = st.columns(2)
                with bc1:
                    st.code(f"MD5:    {meta.get('md5', 'N/A')}\nSHA256: {meta.get('sha256', 'N/A')}", language="text")
                with bc2:
                    st.code(f"MIME Type: {loaded_result.get('mime_type')}\nEntropy:   {meta.get('entropy')} ({meta.get('entropy_type', '')})", language="text")

                st.markdown("##### 💾 Canonical Hex Dump (First 256 bytes):")
                hexdump = meta.get("hexdump") or ""
                if hexdump:
                    st.code(hexdump, language="text")
                else:
                    st.info("No hex dump available.")

                sample_strings = meta.get("sample_strings", [])
                if sample_strings:
                    st.markdown("##### 🔤 Embedded Printable ASCII Strings:")
                    st.code("\n".join(sample_strings[:30]), language="text")

            with st_chat:
                st.markdown("#### 💬 Ask the Avatar About This File")
                q_text = st.text_input("Ask any question regarding the contents of this file:", placeholder="e.g. What is the total expense in this spreadsheet?")
                if st.button("Ask Avatar"):
                    if not q_text.strip():
                        st.warning("Please enter a question.")
                    else:
                        with st.spinner("Avatar analyzing file to answer..."):
                            try:
                                if not active_client:
                                    client = GmailAIAgent(api_key=api_key).get_openai_client()
                                else:
                                    client = active_client
                                file_ctx = loaded_result.get("text_content", "")[:6000]
                                f_prompt = f"""You are a helpful AI assistant analyzing a file for the user.
File Name: {fn}
File Type: {ftype}
Summary: {summary}
Content Excerpt:
{file_ctx}

User Question: {q_text}

Provide an accurate, concise, helpful answer:
"""
                                a_resp = client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    messages=[{"role": "user", "content": f_prompt}],
                                    max_tokens=250,
                                    temperature=0.2
                                )
                                answer_text = a_resp.choices[0].message.content.strip()
                                st.session_state["avatar_remark"] = answer_text
                                st.markdown(f"**🤖 Avatar Answer:**\n\n{answer_text}")
                            except Exception as e:
                                st.error(f"Error getting answer: {e}")

    with tab_sender:
        st.subheader("👥 Sort Mails Sender-Wise & Block Senders")
        st.caption("Organize your mailbox sender-wise. The agent automatically groups your messages by sender into clean folders (e.g., all mails from IndusInd in folder 'indusind', and similar)!")

        # Target a Particular Sender
        st.markdown("##### 📁 Put All Mails From a Particular Sender in a Folder")
        st.caption("Specify a particular sender (email, domain, or brand). The agent will gather all emails from that sender and put them into a dedicated folder named after the sender.")
        p_col1, p_col2 = st.columns([3, 1.2])
        with p_col1:
            particular_sender_input = st.text_input(
                "Target Particular Sender",
                placeholder="e.g. indusind, client@example.com, or Amazon",
                key="particular_sender_target"
            )
        with p_col2:
            st.write("")
            st.write("")
            put_particular_btn = st.button("📁 Put Mails in Folder", use_container_width=True)

        if put_particular_btn:
            if not particular_sender_input.strip():
                st.warning("⚠️ Please enter a sender email, domain, or company name.")
            elif not os.path.exists("token.json") and not os.path.exists("credentials.json"):
                st.error("⚠️ Google OAuth credentials or token not found.")
            else:
                with st.spinner(f"Putting all mails from '{particular_sender_input.strip()}' in a dedicated folder..."):
                    try:
                        agent = GmailAIAgent(
                            designated_senders=designated_senders,
                            delete_senders=delete_senders,
                            api_key=api_key or None,
                            gemini_api_key=gemini_key or None
                        )
                        sort_res = agent.sort_emails_by_sender(
                            target_sender=particular_sender_input.strip(),
                            max_results=max_sender_emails,
                            create_labels=apply_labels_chk
                        )
                        st.session_state["sender_groups"] = sort_res.get("sender_groups", [])
                        st.session_state["last_results"] = sort_res.get("details", [])
                        st.session_state["avatar_remark"] = sort_res.get("remark", "Sorted into folder!")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Error sorting emails for sender '{particular_sender_input.strip()}': {err}")

        st.markdown("---")
        st.markdown("##### 👥 Bulk Sender-Wise Organization")
        s_col1, s_col2, s_col3 = st.columns([1.5, 1, 1.2])
        with s_col1:
            sender_folder_query = st.selectbox(
                "Mailbox Scope",
                options=["INBOX", "STARRED", "SENT", "Work", "Finance", "Promotions", "Personal", "Support", "Custom Query"],
                index=0,
                key="sort_scope"
            )
        with s_col2:
            max_sender_emails = st.number_input("Max Emails to Sort", min_value=5, max_value=100, value=30, key="sort_max")
        with s_col3:
            st.write("")
            st.write("")
            sort_now_btn = st.button("👥 Sort Emails Sender-Wise", use_container_width=True)

        apply_labels_chk = st.checkbox("🏷️ Create & Apply Gmail Sender Labels (e.g., 'indusind')", value=True, help="Creates Gmail labels so your emails are sorted sender-wise in Gmail.")

        custom_sender_q = None
        if sender_folder_query == "Custom Query":
            custom_sender_q = st.text_input("Custom Query", value="in:inbox", placeholder="e.g. from:github.com or in:inbox", key="custom_sender_q")

        if sort_now_btn:
            if not os.path.exists("token.json") and not os.path.exists("credentials.json"):
                st.error("⚠️ Google OAuth credentials or token not found.")
            else:
                with st.spinner("Agent Brain analyzing emails and organizing sender-wise..."):
                    try:
                        agent = GmailAIAgent(
                            designated_senders=designated_senders,
                            delete_senders=delete_senders,
                            api_key=api_key or None,
                            gemini_api_key=gemini_key or None
                        )
                        q_str = custom_sender_q if sender_folder_query == "Custom Query" else (
                            "in:inbox" if sender_folder_query == "INBOX" else (
                                "is:starred" if sender_folder_query == "STARRED" else (
                                    "in:sent" if sender_folder_query == "SENT" else f'label:"{sender_folder_query}"'
                                )
                            )
                        )
                        sort_res = agent.sort_emails_by_sender(folder_query=q_str, max_results=max_sender_emails, create_labels=apply_labels_chk)
                        st.session_state["sender_groups"] = sort_res.get("sender_groups", [])
                        st.session_state["last_results"] = sort_res.get("details", [])
                        st.session_state["avatar_remark"] = sort_res.get("remark", "Sorted sender-wise!")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Error sorting emails sender-wise: {err}")

        # Block a Sender directly
        st.markdown("---")
        st.markdown("#### 🚫 Block Sender & Trash Emails")
        b_c1, b_c2 = st.columns([3, 1])
        with b_c1:
            block_input = st.text_input("Enter email address or domain to block:", placeholder="e.g. spammer@promos.com or @newsletter.com", key="manual_block_input")
        with b_c2:
            st.write("")
            st.write("")
            block_btn = st.button("🚫 Block Sender", use_container_width=True)

        if block_btn and block_input.strip():
            with st.spinner(f"Agent blocking sender '{block_input}'..."):
                try:
                    agent = GmailAIAgent(
                        designated_senders=designated_senders,
                        delete_senders=delete_senders,
                        api_key=api_key or None,
                        gemini_api_key=gemini_key or None
                    )
                    block_res = agent.block_sender(block_input.strip(), purge_now=True)
                    st.session_state["avatar_remark"] = block_res["remark"]
                    st.success(block_res["remark"])
                    time.sleep(1)
                    st.rerun()
                except Exception as b_err:
                    st.error(f"Error blocking sender: {b_err}")

        # Display Sender Groups
        sender_groups = st.session_state.get("sender_groups", [])
        if sender_groups:
            st.markdown("---")
            st.markdown("#### 📊 Sender Breakdown & Organized Emails")
            sg_c1, sg_c2, sg_c3 = st.columns(3)
            total_mails = sum(g["count"] for g in sender_groups)
            sg_c1.metric("Unique Senders", len(sender_groups))
            sg_c2.metric("Total Emails Sorted", total_mails)
            top_s = sender_groups[0]["sender_name"] if sender_groups else "None"
            sg_c3.metric("Top Sender", f"{top_s} ({sender_groups[0]['count']})" if sender_groups else "None")

            for g_idx, grp in enumerate(sender_groups, start=1):
                s_name = grp["sender_name"]
                s_email = grp["sender_email"]
                count = grp["count"]
                unread = grp["unread_count"]
                lbl = grp["label_name"]

                expander_label = f"#{g_idx}: {s_name} ({s_email or 'No Email'}) — {count} email{'s' if count != 1 else ''}" + (f" • 🔴 {unread} unread" if unread else "")
                with st.expander(expander_label, expanded=(g_idx <= 2)):
                    h_col1, h_col2 = st.columns([3, 1])
                    with h_col1:
                        st.markdown(f"**Gmail Label:** `{lbl}` | **From Header:** `{grp.get('raw_from', '')}`")
                    with h_col2:
                        if st.button(f"🚫 Block {s_name[:12]}", key=f"blk_btn_{g_idx}"):
                            agent = GmailAIAgent(designated_senders=designated_senders, delete_senders=delete_senders, api_key=api_key)
                            b_target = s_email or s_name
                            b_res = agent.block_sender(b_target, purge_now=True)
                            st.session_state["avatar_remark"] = b_res["remark"]
                            st.rerun()

                    for em in grp.get("emails", []):
                        unread_badge = "🔴 Unread | " if em.get("is_unread") else ""
                        st.markdown(f"• **{unread_badge}{em['subject']}** — *{em.get('date', '')}*")
                        if em.get("snippet"):
                            st.caption(em["snippet"])
                        if em.get("attachments"):
                            att_badges = " ".join([f"`📎 {a.get('filename')}`" for a in em["attachments"]])
                            st.markdown(f"  └─ Attachments: {att_badges}")
        else:
            st.info("💡 Click **👥 Sort Emails Sender-Wise** above or tell your avatar **'Sort my mails sender wise'** to automatically group and organize your emails by sender!")

        # Display Currently Blocked Senders List
        cfg_delete = cfg.get("delete_senders", [])
        st.markdown("---")
        st.markdown("#### 📋 Currently Blocked Senders (Auto-Trashed)")
        if cfg_delete:
            for b_idx, bs in enumerate(cfg_delete):
                b_row1, b_row2 = st.columns([4, 1])
                with b_row1:
                    st.markdown(f"• 🚫 **`{bs}`** — *All incoming & past emails moved to Trash*")
                with b_row2:
                    if st.button(f"Unblock", key=f"unblk_{b_idx}_{bs}"):
                        agent = GmailAIAgent(designated_senders=designated_senders, delete_senders=delete_senders, api_key=api_key)
                        un_res = agent.unblock_sender(bs)
                        st.session_state["avatar_remark"] = un_res["remark"]
                        st.rerun()
        else:
            st.caption("No senders currently blocked. Use the block input above or tell your avatar 'Block sender <email>'.")

    with tab_folder:
        st.subheader("📁 Read Folder Mails & View Synopses")
        st.caption("Read all emails in any Gmail folder. Move your mouse over any email card to view its AI synopsis in a floating text box!")

        f_col1, f_col2, f_col3 = st.columns([1.5, 1, 1.2])
        with f_col1:
            folder_choice = st.selectbox(
                "Select Folder / Label",
                options=["INBOX", "Work", "Finance", "Promotions", "Personal", "Support", "STARRED", "SENT", "Custom Query"],
                index=0
            )
        with f_col2:
            max_folder_emails = st.number_input("Max Mails", min_value=1, max_value=50, value=15)
        with f_col3:
            st.write("")
            st.write("")
            load_folder_btn = st.button("📖 Read All Folder Mails", use_container_width=True)

        custom_q = None
        if folder_choice == "Custom Query":
            custom_q = st.text_input("Gmail Query", value="in:inbox", placeholder="e.g., from:boss or label:work")

        if load_folder_btn:
            if not os.path.exists("token.json") and not os.path.exists("credentials.json"):
                st.error("⚠️ Google OAuth credentials or token not found.")
            else:
                with st.spinner("Reading all emails from folder and synthesizing synopses..."):
                    try:
                        agent = GmailAIAgent(
                            designated_senders=designated_senders,
                            delete_senders=delete_senders,
                            api_key=api_key
                        )
                        q_str = custom_q if folder_choice == "Custom Query" else (
                            "in:inbox" if folder_choice == "INBOX" else (
                                "is:starred" if folder_choice == "STARRED" else (
                                    "in:sent" if folder_choice == "SENT" else f'label:"{folder_choice}"'
                                )
                            )
                        )
                        folder_mails = agent.read_folder_emails(folder_query=q_str, max_results=max_folder_emails)
                        st.session_state["folder_emails"] = folder_mails
                        action_cnt = sum(1 for e in folder_mails if e.get("synopsis", {}).get("urgency") == "Urgent" or "no action" not in e.get("synopsis", {}).get("action_item", "").lower())
                        info_cnt = len(folder_mails) - action_cnt
                        remark = f"I've read and analyzed all {len(folder_mails)} emails in '{folder_choice}'! {action_cnt} need your attention, and {info_cnt} are informational. Hover your mouse over any email card to view its synopsis!"
                        st.session_state["avatar_remark"] = remark
                        st.rerun()
                    except Exception as err:
                        st.error(f"Error reading folder emails: {err}")

        # Display Folder Mails with Mouseover Hover Synopses
        folder_mails = st.session_state.get("folder_emails", [])
        if not folder_mails:
            st.info("💡 Select a folder above and click **📖 Read All Folder Mails** to read all emails and generate mouseover synopses.")
        else:
            fm1, fm2, fm3 = st.columns(3)
            fm1.metric("Emails Read", len(folder_mails))
            urgent_count = sum(1 for m in folder_mails if m.get("synopsis", {}).get("urgency") == "Urgent")
            fm2.metric("Urgent / Actions", urgent_count)
            fm3.metric("Informational", len(folder_mails) - urgent_count)

            st.markdown("---")
            st.markdown("#### 📧 Email List (Hover mouse over any card for synopsis):")

            # Injected CSS for Mouseover Synopsis Hover Card in Dashboard
            tooltip_css = """
            <style>
            .mail-card {
                position: relative;
                background: #1e293b;
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 10px;
                padding: 12px 14px;
                margin-bottom: 10px;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .mail-card:hover {
                background: #243248;
                border-color: #38bdf8;
                box-shadow: 0 6px 18px rgba(56, 189, 248, 0.25);
            }
            .mail-card-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 4px;
            }
            .mail-card-title {
                font-weight: 700;
                font-size: 14px;
                color: #ffffff;
            }
            .mail-card-from {
                font-size: 12px;
                color: #94a3b8;
            }
            .mail-card-snippet {
                font-size: 12px;
                color: #cbd5e1;
                margin-top: 4px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .mail-hover-synopsis {
                display: none;
                position: absolute;
                top: calc(100% + 8px);
                left: 10px;
                width: 380px;
                max-width: 90vw;
                background: rgba(15, 23, 42, 0.98);
                backdrop-filter: blur(14px);
                border: 1px solid #38bdf8;
                border-radius: 12px;
                padding: 14px;
                box-shadow: 0 16px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(56, 189, 248, 0.3);
                z-index: 99999;
                color: #f8fafc;
                pointer-events: none;
            }
            .mail-card:hover .mail-hover-synopsis {
                display: block;
                animation: popIn 0.2s ease-out forwards;
            }
            @keyframes popIn {
                from { opacity: 0; transform: translateY(-6px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .syn-badge-pill {
                display: inline-block;
                padding: 2px 7px;
                font-size: 10.5px;
                font-weight: 700;
                border-radius: 8px;
                text-transform: uppercase;
                margin-right: 6px;
            }
            .syn-badge-work { background: rgba(59, 130, 246, 0.25); color: #93c5fd; }
            .syn-badge-fin { background: rgba(16, 185, 129, 0.25); color: #6ee7b7; }
            .syn-badge-urg { background: rgba(239, 68, 68, 0.25); color: #fca5a5; }
            .syn-tldr {
                background: rgba(30, 41, 59, 0.9);
                border-left: 3px solid #38bdf8;
                padding: 8px 10px;
                font-size: 12px;
                line-height: 1.4;
                border-radius: 4px;
                margin: 8px 0;
            }
            .syn-bullets {
                padding-left: 16px;
                font-size: 11.5px;
                color: #cbd5e1;
                margin: 6px 0;
            }
            .syn-action {
                background: rgba(245, 158, 11, 0.15);
                border: 1px solid rgba(245, 158, 11, 0.35);
                color: #fde68a;
                padding: 6px 8px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }
            </style>
            """
            st.markdown(tooltip_css, unsafe_allow_html=True)

            for idx, item in enumerate(folder_mails, start=1):
                syn = item.get("synopsis", {})
                urgency = syn.get("urgency", "Normal")
                cat = syn.get("category", "Work")
                tldr = syn.get("tldr", item["snippet"])
                points_html = "".join([f"<li>{p}</li>" for p in syn.get("key_points", [item["snippet"][:100]])])
                action = syn.get("action_item", "No action needed (Informational)")

                urg_class = "syn-badge-urg" if urgency == "Urgent" else "syn-badge-work"
                cat_class = "syn-badge-fin" if cat == "Finance" else "syn-badge-work"

                attachments = item.get("attachments", [])
                att_pills = ""
                att_syn_list = ""
                if attachments:
                    att_pills = "<div style='margin-top: 5px;'>" + " ".join([f"<span class='syn-badge-pill syn-badge-fin'>📎 {a.get('filename')} ({a.get('file_type', 'File')})</span>" for a in attachments]) + "</div>"
                    att_syn_list = "<div style='margin-top: 6px; font-size: 11px; color: #38bdf8;'><b>📎 Attached Files:</b> " + ", ".join([f"{a.get('filename')} ({a.get('size_human', '')})" for a in attachments]) + "</div>"

                card_html = f"""
                <div class="mail-card">
                    <div class="mail-card-header">
                        <span class="mail-card-title">#{idx} {item['subject']}</span>
                        <span style="font-size: 11px; color: #94a3b8;">{item.get('date', '')}</span>
                    </div>
                    <div class="mail-card-from">From: {item['sender']}</div>
                    <div class="mail-card-snippet">{item['snippet']}</div>
                    {att_pills}

                    <!-- Floating Synopsis Popover on Mouseover -->
                    <div class="mail-hover-synopsis">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <div>
                                <span class="syn-badge-pill {cat_class}">🏷️ {cat}</span>
                                <span class="syn-badge-pill {urg_class}">⚡ {urgency}</span>
                            </div>
                            <span style="font-size: 10px; color: #38bdf8; font-weight: 600;">AI SYNOPSIS</span>
                        </div>
                        <div style="font-weight: 700; font-size: 13px; color: #fff; margin-bottom: 3px;">{item['subject']}</div>
                        <div style="font-size: 11px; color: #94a3b8; margin-bottom: 6px;">{item['sender']}</div>
                        <div class="syn-tldr">📝 {tldr}</div>
                        <div style="font-size: 10.5px; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Key Points:</div>
                        <ul class="syn-bullets">{points_html}</ul>
                        {att_syn_list}
                        <div class="syn-action" style="margin-top: 6px;">⚡ Action: {action}</div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)

    with tab_triage:
        st.subheader("📬 Processing Results")
        
        results = st.session_state.get("last_results", [])
        if not results:
            st.info("💡 Type a command like **'Scan my inbox'** or click **🚀 Scan Inbox** on the left to triage your emails.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Emails Scanned", len(results))
            m2.metric("Drafts Created", sum(1 for r in results if r.get("draft")))
            m3.metric("Moved to Trash", sum(1 for r in results if r.get("category") == "Trash"))
            m4.metric("Flagged / Pending", sum(1 for r in results if "Flagged" in r.get("action", "")))

            st.markdown("---")
            st.markdown("### 📋 Email Details")
            for i, item in enumerate(results, start=1):
                with st.expander(f"#{i}: {item['subject']} — {item['sender']}", expanded=(i == 1)):
                    ca, cb = st.columns(2)
                    with ca:
                        st.markdown(f"**Category:** `{item['category']}`")
                    with cb:
                        st.markdown(f"**Action Status:** `{item['action']}`")
                    st.markdown(f"**Snippet:** *{item['snippet']}*")

                    if item.get("attachments"):
                        st.markdown("##### 📎 Attached Files")
                        for a in item["attachments"]:
                            st.markdown(f"• **`{a.get('filename')}`** ({a.get('file_type')}, {a.get('size_human')}):\n  {a.get('summary', '')}")
                            if a.get('key_points'):
                                for kp in a['key_points']:
                                    st.markdown(f"    - {kp}")
                            if a.get('text_content'):
                                with st.expander(f"Preview content: {a.get('filename')}"):
                                    st.text(a.get('text_content')[:2000])

                    if item.get("draft"):
                        draft = item["draft"]
                        st.markdown("##### ✉️ Drafted Contextual Reply")
                        st.info(f"**To:** {draft['to']}\n\n**Subject:** {draft['subject']}\n\n**Preview:**\n\n{draft['preview']}")

    with tab_daemon:
        st.subheader("🖥️ 24/7 Background Daemon")
        b1, b2 = st.columns(2)
        with b1:
            if daemon_active:
                st.success(f"Status: **Running in Background** (PID: {active_pid})")
            else:
                st.warning("Status: **Stopped**")
        with b2:
            st.caption("Start with `start_background.bat` | Stop with `stop_background.bat`")

        st.markdown("---")
        st.markdown("#### 📜 Activity Log (`agent_activity.log`)")
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as lf:
                    lines = lf.readlines()
                st.code("".join(lines[-35:]) if lines else "No log entries yet.", language="text")
            except Exception as e:
                st.error(f"Could not read log: {e}")
        else:
            st.info("No activity log found yet. Runs from the daemon will record here.")

# Auto-Pilot Mode
if auto_pilot:
    st.sidebar.warning(f"⏳ Auto-Pilot active: Next scan in {poll_minutes}m...")
    time.sleep(poll_minutes * 60)
    st.rerun()
