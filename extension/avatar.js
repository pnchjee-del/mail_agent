// 3D Cute Animal Avatar Engine & Standalone In-Extension Triage Assistant
// 100% Native: Connects directly to Gmail API & OpenAI without any background server!
// Features adorable, expressive Dog 🐶, Bunny 🐰, and Bear 🐻 avatars with animated ears, lips, tongue, and eyes!

(function () {
    const remarkEl = document.getElementById('balloon-text') || document.getElementById('remark-text');
    const speakingBadge = document.getElementById('speaking-badge');
    const speechBalloon = document.getElementById('speech-balloon') || document.getElementById('message-box');
    const balloonTitleEl = document.getElementById('balloon-title');
    const charBtn = document.getElementById('char-btn');
    const voiceBtn = document.getElementById('voice-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const closeSettingsBtn = document.getElementById('close-settings-btn');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const inputForm = document.getElementById('input-form');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const container = document.getElementById('canvas-mount');
    const agentStatus = document.getElementById('agent-status');

    let voiceEnabled = false;
    let isSpeaking = false;
    let speechTimer = null;
    let currentCharacter = 'dog'; // 'dog' | 'bunny' | 'bear'

    // Web Speech Synthesis
    voiceBtn.addEventListener('click', () => {
        voiceEnabled = !voiceEnabled;
        voiceBtn.innerText = voiceEnabled ? "🔊 Voice: ON" : "🔇 Voice: OFF";
        if (voiceEnabled && window.speechSynthesis) {
            speakAloud(remarkEl.innerText);
        } else if (!voiceEnabled && window.speechSynthesis) {
            window.speechSynthesis.cancel();
        }
    });

    function speakAloud(text) {
        if (!('speechSynthesis' in window)) return;
        window.speechSynthesis.cancel();
        const clean = text.replace(/[^a-zA-Z0-9\s.,?!'-]/g, '');
        const utter = new SpeechSynthesisUtterance(clean);
        utter.rate = 1.05;
        utter.pitch = currentCharacter === 'bunny' ? 1.25 : (currentCharacter === 'bear' ? 0.95 : 1.1);
        window.speechSynthesis.speak(utter);
    }

    function setAvatarRemark(text, animateSpeech = true) {
        remarkEl.innerText = text;

        if (animateSpeech) {
            isSpeaking = true;
            speakingBadge.style.display = 'inline-flex';
            speechBalloon.classList.add('speaking');

            if (voiceEnabled) {
                speakAloud(text);
            }

            if (speechTimer) clearTimeout(speechTimer);
            const durationMs = Math.min(10000, Math.max(3500, text.length * 60));
            speechTimer = setTimeout(() => {
                isSpeaking = false;
                speakingBadge.style.display = 'none';
                speechBalloon.classList.remove('speaking');
            }, durationMs);
        }
    }

    // Settings Modal
    settingsBtn.addEventListener('click', async () => {
        const cfg = await GmailEngine.getConfig();
        const aiProvider = cfg.ai_provider || (cfg.use_omniroute !== false ? 'omniroute' : 'openai');
        const providerSel = document.getElementById('cfg-ai-provider');
        if (providerSel) providerSel.value = aiProvider;

        const omniUrl = document.getElementById('cfg-omniroute-url');
        if (omniUrl) omniUrl.value = cfg.omniroute_base_url || "http://localhost:20128/v1";

        const omniModel = document.getElementById('cfg-omniroute-model');
        if (omniModel) omniModel.value = cfg.omniroute_model || "auto";

        const omniKey = document.getElementById('cfg-omniroute-key');
        if (omniKey) omniKey.value = cfg.omniroute_api_key || "";

        const statusEl = document.getElementById('omniroute-test-status');
        if (statusEl) {
            statusEl.style.display = 'none';
            statusEl.innerText = '';
        }

        document.getElementById('cfg-openai-key').value = cfg.openai_api_key || "";
        document.getElementById('cfg-designated').value = (cfg.designated_senders || []).join('\n');
        document.getElementById('cfg-blacklisted').value = (cfg.delete_senders || []).join('\n');
        document.getElementById('cfg-grace-period').value = cfg.grace_period_minutes !== undefined ? cfg.grace_period_minutes : 60;
        document.getElementById('cfg-auto-delete').checked = cfg.auto_delete !== false;
        const cfgChar = document.getElementById('cfg-character');
        if (cfgChar) cfgChar.value = cfg.avatar_character || currentCharacter;
        settingsModal.classList.add('active');
    });

    closeSettingsBtn.addEventListener('click', () => {
        settingsModal.classList.remove('active');
    });

    // Test OmniRoute Connection Button
    const testOmniBtn = document.getElementById('test-omniroute-btn');
    if (testOmniBtn) {
        testOmniBtn.addEventListener('click', async () => {
            const statusEl = document.getElementById('omniroute-test-status');
            if (statusEl) {
                statusEl.style.display = 'block';
                statusEl.style.color = '#38bdf8';
                statusEl.innerText = 'Connecting to OmniRoute gateway...';
            }

            // Temporarily stage user inputs for the test
            const inputUrl = document.getElementById('cfg-omniroute-url')?.value.trim() || 'http://localhost:20128/v1';
            const inputModel = document.getElementById('cfg-omniroute-model')?.value.trim() || 'auto';
            const inputKey = document.getElementById('cfg-omniroute-key')?.value.trim() || 'omniroute';

            await GmailEngine.saveConfig({
                omniroute_base_url: inputUrl,
                omniroute_model: inputModel,
                omniroute_api_key: inputKey,
                ai_provider: 'omniroute',
                use_omniroute: true
            });

            const result = await GmailEngine.testOmniRouteConnection();
            if (statusEl) {
                if (result.ok) {
                    statusEl.style.color = '#4ade80';
                    statusEl.innerHTML = `✅ <strong>Connected!</strong> Model: <code>${result.model}</code><br>Reply: "${result.reply}"`;
                } else {
                    statusEl.style.color = '#f87171';
                    statusEl.innerHTML = `❌ <strong>Not connected:</strong> ${result.message}`;
                }
            }
        });
    }

    saveSettingsBtn.addEventListener('click', async () => {
        const key = document.getElementById('cfg-openai-key').value.trim();
        const designated = document.getElementById('cfg-designated').value.split('\n').map(s => s.trim()).filter(Boolean);
        const blacklisted = document.getElementById('cfg-blacklisted').value.split('\n').map(s => s.trim()).filter(Boolean);
        const autoDel = document.getElementById('cfg-auto-delete').checked;
        const grace = parseInt(document.getElementById('cfg-grace-period').value, 10) || 60;
        const charChoice = document.getElementById('cfg-character') ? document.getElementById('cfg-character').value : currentCharacter;

        const aiProvider = document.getElementById('cfg-ai-provider')?.value || 'omniroute';
        const omniUrl = document.getElementById('cfg-omniroute-url')?.value.trim() || 'http://localhost:20128/v1';
        const omniModel = document.getElementById('cfg-omniroute-model')?.value.trim() || 'auto';
        const omniKey = document.getElementById('cfg-omniroute-key')?.value.trim() || 'omniroute';

        await GmailEngine.saveConfig({
            ai_provider: aiProvider,
            use_omniroute: aiProvider === 'omniroute',
            omniroute_base_url: omniUrl,
            omniroute_model: omniModel,
            omniroute_api_key: omniKey,
            openai_api_key: key,
            designated_senders: designated,
            delete_senders: blacklisted,
            auto_delete: autoDel,
            grace_period_minutes: grace,
            avatar_character: charChoice
        });

        if (charChoice !== currentCharacter) {
            setCharacter(charChoice, false);
        }

        settingsModal.classList.remove('active');
        const providerName = aiProvider === 'omniroute' ? 'OmniRoute Gateway' : 'OpenAI';
        setAvatarRemark(`⚙️ Settings saved! AI Engine set to ${providerName} (Model: ${aiProvider === 'omniroute' ? omniModel : 'gpt-4o-mini'}).`);
    });

    // Three.js 3D Cute Avatar Setup
    const initW = container.clientWidth || 380;
    const initH = container.clientHeight || 280;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, initW / initH, 0.1, 100);
    camera.position.set(0, 1.40, 1.65);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(initW, initH);
    container.appendChild(renderer.domElement);

    function handleResize() {
        if (!container) return;
        const w = container.clientWidth || 380;
        const h = container.clientHeight || 280;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
    }
    window.addEventListener('resize', handleResize);
    setTimeout(handleResize, 150);
    setTimeout(handleResize, 500);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, 1.36, 0);
    controls.minDistance = 1.1;
    controls.maxDistance = 2.6;
    controls.maxPolarAngle = Math.PI / 2 + 0.1;
    controls.update();

    // Soft Studio Lighting for Cute Fluffy Look
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

    // Root Group for Avatar Models
    const avatarRoot = new THREE.Group();
    scene.add(avatarRoot);

    // Dynamic Animation Handles
    let animatedParts = {
        headGroup: null,
        bodyGroup: null,
        leftEye: null,
        rightEye: null,
        leftEar: null,
        rightEar: null,
        lowerLip: null,
        cavity: null,
        tongue: null,
        charType: 'dog'
    };

    // Helper: Create Sparkly Anime/Puppy Eyes
    function createCuteEye(x, irisColor = 0x3e1f07, lidColor = 0xdf984b) {
        const eyeGroup = new THREE.Group();

        // White Sclera
        const whiteGeo = new THREE.SphereGeometry(0.066, 24, 24);
        const whiteMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.15 });
        const white = new THREE.Mesh(whiteGeo, whiteMat);
        white.scale.set(1.0, 0.92, 0.55);
        eyeGroup.add(white);

        // Rich Colorful Iris
        const irisGeo = new THREE.SphereGeometry(0.046, 24, 24);
        const irisMat = new THREE.MeshStandardMaterial({ color: irisColor, roughness: 0.25 });
        const iris = new THREE.Mesh(irisGeo, irisMat);
        iris.position.set(0, 0, 0.024);
        iris.scale.set(1.0, 1.0, 0.35);
        eyeGroup.add(iris);

        // Black Pupil
        const pupilGeo = new THREE.SphereGeometry(0.026, 24, 24);
        const pupilMat = new THREE.MeshStandardMaterial({ color: 0x09090b });
        const pupil = new THREE.Mesh(pupilGeo, pupilMat);
        pupil.position.set(0, 0, 0.038);
        pupil.scale.set(1.0, 1.0, 0.25);
        eyeGroup.add(pupil);

        // Big Twinkle Catchlight (Major shine)
        const shine1Geo = new THREE.SphereGeometry(0.013, 16, 16);
        const shineMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
        const shine1 = new THREE.Mesh(shine1Geo, shineMat);
        shine1.position.set(0.014, 0.016, 0.052);
        eyeGroup.add(shine1);

        // Small Secondary Twinkle (Cute sparkle)
        const shine2Geo = new THREE.SphereGeometry(0.007, 12, 12);
        const shine2 = new THREE.Mesh(shine2Geo, shineMat);
        shine2.position.set(-0.012, -0.012, 0.052);
        eyeGroup.add(shine2);

        // Blinking Eyelid
        const lidGeo = new THREE.SphereGeometry(0.072, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.5);
        const lidMat = new THREE.MeshStandardMaterial({ color: lidColor, roughness: 0.65 });
        const upperLid = new THREE.Mesh(lidGeo, lidMat);
        upperLid.rotation.x = Math.PI;
        upperLid.scale.set(1.06, 0.01, 1.06);
        eyeGroup.add(upperLid);

        eyeGroup.position.set(x, 1.42, 0.30);
        eyeGroup.userData = { upperLid: upperLid, iris: iris };
        return eyeGroup;
    }

    // Helper: Create Rosy Blush Cheek
    function createRosyCheek(x, y, z, color = 0xf472b6) {
        const cheekGeo = new THREE.SphereGeometry(0.055, 16, 16);
        const cheekMat = new THREE.MeshBasicMaterial({ color: color, transparent: true, opacity: 0.58 });
        const cheek = new THREE.Mesh(cheekGeo, cheekMat);
        cheek.scale.set(1.0, 0.65, 0.3);
        cheek.position.set(x, y, z);
        return cheek;
    }

    // BUILD CUTE 3D ANIMAL AVATARS (Dog 🐶, Bunny 🐰, Bear 🐻)
    function buildCuteAvatar(type = 'dog') {
        // Clear previous meshes
        while (avatarRoot.children.length > 0) {
            avatarRoot.remove(avatarRoot.children[0]);
        }

        const headGroup = new THREE.Group();
        const bodyGroup = new THREE.Group();
        avatarRoot.add(bodyGroup);
        avatarRoot.add(headGroup);

        let leftEar, rightEar, leftEye, rightEye, lowerLip, cavity, tongue;

        if (type === 'dog') {
            // ==================== 🐶 CUTE PUPPY DOG ====================
            const furColor = 0xdf984b;      // Warm Golden Shiba tan
            const creamColor = 0xfff7ed;    // Soft Ivory / Cream muzzle
            const earTipColor = 0xba6a22;   // Caramel darker tips
            const irisColor = 0x3e1f07;     // Warm chocolate eyes

            // 1. Head Base (Chubby Cute Puppy Head)
            const headGeo = new THREE.SphereGeometry(0.38, 32, 32);
            headGeo.scale(1.08, 0.98, 0.96);
            const furMat = new THREE.MeshStandardMaterial({ color: furColor, roughness: 0.68, metalness: 0.02 });
            const headMesh = new THREE.Mesh(headGeo, furMat);
            headMesh.position.set(0, 1.40, 0);
            headGroup.add(headMesh);

            // 2. Cute Cream Snout / Muzzle
            const snoutGeo = new THREE.SphereGeometry(0.18, 24, 24);
            snoutGeo.scale(1.18, 0.88, 1.05);
            const snoutMat = new THREE.MeshStandardMaterial({ color: creamColor, roughness: 0.7 });
            const snout = new THREE.Mesh(snoutGeo, snoutMat);
            snout.position.set(0, 1.30, 0.25);
            headGroup.add(snout);

            // 3. Shiny Puppy Nose
            const noseGeo = new THREE.SphereGeometry(0.048, 16, 16);
            noseGeo.scale(1.2, 0.85, 0.9);
            const noseMat = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.15, metalness: 0.1 });
            const nose = new THREE.Mesh(noseGeo, noseMat);
            nose.position.set(0, 1.34, 0.435);
            headGroup.add(nose);

            const noseShine = new THREE.Mesh(new THREE.SphereGeometry(0.009, 8, 8), new THREE.MeshBasicMaterial({ color: 0xffffff }));
            noseShine.position.set(0.012, 1.355, 0.45);
            headGroup.add(noseShine);

            // 4. Floppy Puppy Ears (Bounce & droop beside cheeks)
            function createDogEar(isLeft) {
                const earPivot = new THREE.Group();
                earPivot.position.set(isLeft ? -0.34 : 0.34, 1.52, 0.02);

                const earGeo = new THREE.CylinderGeometry(0.065, 0.13, 0.38, 24);
                earGeo.scale(0.65, 1.0, 1.0);
                const earMat = new THREE.MeshStandardMaterial({ color: isLeft ? furColor : earTipColor, roughness: 0.7 });
                const earMesh = new THREE.Mesh(earGeo, earMat);
                earMesh.position.set(0, -0.16, 0);
                earMesh.rotation.z = isLeft ? -0.34 : 0.34;
                earPivot.add(earMesh);

                return earPivot;
            }
            leftEar = createDogEar(true);
            rightEar = createDogEar(false);
            headGroup.add(leftEar);
            headGroup.add(rightEar);

            // 5. Sparkly Eyes
            leftEye = createCuteEye(-0.14, irisColor, furColor);
            rightEye = createCuteEye(0.14, irisColor, furColor);
            headGroup.add(leftEye);
            headGroup.add(rightEye);

            // 6. Rosy Cheeks
            headGroup.add(createRosyCheek(-0.24, 1.31, 0.28, 0xf472b6));
            headGroup.add(createRosyCheek(0.24, 1.31, 0.28, 0xf472b6));

            // 7. Mouth, Smiling Lips & Bobbing Tongue
            const mouthGroup = new THREE.Group();
            mouthGroup.position.set(0, 1.23, 0.33);

            // Upper smile lips (cute 'w' shape)
            const lipMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.5 });
            const lipL = new THREE.Mesh(new THREE.TorusGeometry(0.042, 0.011, 12, 20, Math.PI), lipMat);
            lipL.rotation.x = Math.PI;
            lipL.position.set(-0.038, 0.015, 0);
            mouthGroup.add(lipL);

            const lipR = new THREE.Mesh(new THREE.TorusGeometry(0.042, 0.011, 12, 20, Math.PI), lipMat);
            lipR.rotation.x = Math.PI;
            lipR.position.set(0.038, 0.015, 0);
            mouthGroup.add(lipR);

            // Lower lip
            const lowerLipGeo = new THREE.TorusGeometry(0.052, 0.015, 12, 24, Math.PI);
            lowerLip = new THREE.Mesh(lowerLipGeo, new THREE.MeshStandardMaterial({ color: 0xd9777f, roughness: 0.5 }));
            lowerLip.position.set(0, -0.012, 0);
            mouthGroup.add(lowerLip);

            // Mouth Cavity
            cavity = new THREE.Mesh(new THREE.SphereGeometry(0.046, 16, 16), new THREE.MeshBasicMaterial({ color: 0x3f0713 }));
            cavity.scale.set(1.1, 0.35, 0.2);
            cavity.position.set(0, -0.005, -0.01);
            mouthGroup.add(cavity);

            // Cute Pink Tongue (Peeks out and bobs!)
            tongue = new THREE.Mesh(new THREE.SphereGeometry(0.036, 16, 16), new THREE.MeshStandardMaterial({ color: 0xf43f5e, roughness: 0.4 }));
            tongue.scale.set(1.0, 0.32, 1.25);
            tongue.position.set(0, -0.012, 0.02);
            mouthGroup.add(tongue);

            headGroup.add(mouthGroup);

            // 8. Body, Neck, Red Collar & Golden Bell
            const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.20, 0.18, 24), furMat);
            neck.position.set(0, 1.16, 0);
            bodyGroup.add(neck);

            const body = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.44, 0.55, 24), furMat);
            body.position.set(0, 0.83, 0);
            bodyGroup.add(body);

            // Cream belly patch
            const belly = new THREE.Mesh(new THREE.SphereGeometry(0.28, 24, 24), snoutMat);
            belly.scale.set(0.75, 1.1, 0.3);
            belly.position.set(0, 0.82, 0.18);
            bodyGroup.add(belly);

            // Red Puppy Collar
            const collar = new THREE.Mesh(
                new THREE.TorusGeometry(0.18, 0.026, 16, 32),
                new THREE.MeshStandardMaterial({ color: 0xef4444, roughness: 0.35 })
            );
            collar.rotation.x = Math.PI / 2;
            collar.position.set(0, 1.08, 0);
            bodyGroup.add(collar);

            // Golden Bell
            const bell = new THREE.Mesh(
                new THREE.SphereGeometry(0.042, 16, 16),
                new THREE.MeshStandardMaterial({ color: 0xfbbf24, metalness: 0.8, roughness: 0.2 })
            );
            bell.position.set(0, 1.04, 0.21);
            bodyGroup.add(bell);

        } else if (type === 'bunny') {
            // ==================== 🐰 FLUFFY BUNNY ====================
            const furColor = 0xf8fafc;      // Snow White
            const innerEarColor = 0xfbcfe8; // Pastel Blush Pink
            const irisColor = 0x1e3a8a;     // Deep Sapphire Blue
            const noseColor = 0xf472b6;     // Soft Pink

            // 1. Head Base
            const headGeo = new THREE.SphereGeometry(0.36, 32, 32);
            headGeo.scale(1.05, 0.98, 0.95);
            const furMat = new THREE.MeshStandardMaterial({ color: furColor, roughness: 0.72 });
            const headMesh = new THREE.Mesh(headGeo, furMat);
            headMesh.position.set(0, 1.38, 0);
            headGroup.add(headMesh);

            // 2. White Fluffy Snout
            const snoutGeo = new THREE.SphereGeometry(0.15, 24, 24);
            snoutGeo.scale(1.15, 0.8, 0.95);
            const snout = new THREE.Mesh(snoutGeo, furMat);
            snout.position.set(0, 1.28, 0.26);
            headGroup.add(snout);

            // 3. Pink Heart Nose
            const nose = new THREE.Mesh(
                new THREE.ConeGeometry(0.035, 0.04, 16),
                new THREE.MeshStandardMaterial({ color: noseColor, roughness: 0.3 })
            );
            nose.rotation.x = Math.PI;
            nose.position.set(0, 1.34, 0.39);
            headGroup.add(nose);

            // 4. Tall Fluffy Bunny Ears (Twitch & tilt!)
            function createBunnyEar(isLeft) {
                const earPivot = new THREE.Group();
                earPivot.position.set(isLeft ? -0.16 : 0.16, 1.66, -0.02);

                const earGeo = new THREE.CylinderGeometry(0.055, 0.088, 0.52, 24);
                earGeo.scale(0.8, 1.0, 0.38);
                const outer = new THREE.Mesh(earGeo, furMat);
                outer.position.set(0, 0.24, 0);
                earPivot.add(outer);

                // Inner pink ear pad
                const innerGeo = new THREE.CylinderGeometry(0.038, 0.065, 0.44, 20);
                innerGeo.scale(0.75, 1.0, 0.2);
                const inner = new THREE.Mesh(innerGeo, new THREE.MeshStandardMaterial({ color: innerEarColor, roughness: 0.6 }));
                inner.position.set(0, 0.24, 0.015);
                earPivot.add(inner);

                earPivot.rotation.z = isLeft ? -0.16 : 0.16;
                earPivot.rotation.x = -0.08;
                return earPivot;
            }
            leftEar = createBunnyEar(true);
            rightEar = createBunnyEar(false);
            headGroup.add(leftEar);
            headGroup.add(rightEar);

            // 5. Sparkly Eyes
            leftEye = createCuteEye(-0.13, irisColor, furColor);
            rightEye = createCuteEye(0.13, irisColor, furColor);
            headGroup.add(leftEye);
            headGroup.add(rightEye);

            // 6. Rosy Cheeks
            headGroup.add(createRosyCheek(-0.23, 1.29, 0.27, 0xf472b6));
            headGroup.add(createRosyCheek(0.23, 1.29, 0.27, 0xf472b6));

            // 7. Whiskers
            function createWhiskers(isLeft) {
                const wGroup = new THREE.Group();
                const wMat = new THREE.MeshBasicMaterial({ color: 0x94a3b8 });
                for (let i = -1; i <= 1; i++) {
                    const wMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.002, 0.002, 0.16), wMat);
                    wMesh.rotation.z = Math.PI / 2 + (i * 0.15);
                    wMesh.position.set(isLeft ? -0.07 : 0.07, i * 0.018, 0);
                    wGroup.add(wMesh);
                }
                wGroup.position.set(isLeft ? -0.14 : 0.14, 1.29, 0.32);
                return wGroup;
            }
            headGroup.add(createWhiskers(true));
            headGroup.add(createWhiskers(false));

            // 8. Cute Buckteeth & Mouth
            const mouthGroup = new THREE.Group();
            mouthGroup.position.set(0, 1.22, 0.32);

            // Two White Buckteeth!
            const toothMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.2 });
            const toothL = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.03, 0.012), toothMat);
            toothL.position.set(-0.014, 0.01, 0.01);
            mouthGroup.add(toothL);

            const toothR = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.03, 0.012), toothMat);
            toothR.position.set(0.014, 0.01, 0.01);
            mouthGroup.add(toothR);

            lowerLip = new THREE.Mesh(new THREE.TorusGeometry(0.045, 0.012, 12, 24, Math.PI), new THREE.MeshStandardMaterial({ color: 0xf472b6 }));
            lowerLip.position.set(0, -0.015, 0);
            mouthGroup.add(lowerLip);

            cavity = new THREE.Mesh(new THREE.SphereGeometry(0.04, 16, 16), new THREE.MeshBasicMaterial({ color: 0x4a044e }));
            cavity.scale.set(1.0, 0.35, 0.2);
            cavity.position.set(0, -0.005, -0.01);
            mouthGroup.add(cavity);

            tongue = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 16), new THREE.MeshStandardMaterial({ color: 0xf43f5e }));
            tongue.scale.set(1.0, 0.3, 1.1);
            tongue.position.set(0, -0.012, 0.015);
            mouthGroup.add(tongue);

            headGroup.add(mouthGroup);

            // 9. White Body & Mint Bow Tie
            const body = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.42, 0.52, 24), furMat);
            body.position.set(0, 0.83, 0);
            bodyGroup.add(body);

            // Mint/Cyan Bow Tie
            const bowMat = new THREE.MeshStandardMaterial({ color: 0x06b6d4, roughness: 0.35 });
            const bowL = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.12, 16), bowMat);
            bowL.rotation.z = Math.PI / 2;
            bowL.position.set(-0.065, 1.07, 0.20);
            bodyGroup.add(bowL);

            const bowR = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.12, 16), bowMat);
            bowR.rotation.z = -Math.PI / 2;
            bowR.position.set(0.065, 1.07, 0.20);
            bodyGroup.add(bowR);

            const knot = new THREE.Mesh(new THREE.SphereGeometry(0.032, 16, 16), new THREE.MeshStandardMaterial({ color: 0x0891b2 }));
            knot.position.set(0, 1.07, 0.22);
            bodyGroup.add(knot);

        } else if (type === 'bear') {
            // ==================== 🐻 TEDDY BEAR ====================
            const furColor = 0x854d0e;      // Warm Honey Caramel Teddy Brown
            const biscuitColor = 0xfde68a;  // Biscuit Yellow / Cream
            const irisColor = 0x1c1917;     // Deep Onyx Button eyes

            // 1. Head Base
            const headGeo = new THREE.SphereGeometry(0.38, 32, 32);
            headGeo.scale(1.08, 0.98, 0.96);
            const furMat = new THREE.MeshStandardMaterial({ color: furColor, roughness: 0.8 });
            const headMesh = new THREE.Mesh(headGeo, furMat);
            headMesh.position.set(0, 1.40, 0);
            headGroup.add(headMesh);

            // 2. Round Teddy Ears (Half-cup on top of head)
            function createBearEar(isLeft) {
                const earPivot = new THREE.Group();
                earPivot.position.set(isLeft ? -0.28 : 0.28, 1.68, 0.0);

                const outerGeo = new THREE.SphereGeometry(0.13, 24, 24);
                outerGeo.scale(1.0, 1.0, 0.45);
                const outer = new THREE.Mesh(outerGeo, furMat);
                earPivot.add(outer);

                const innerGeo = new THREE.SphereGeometry(0.085, 20, 20);
                innerGeo.scale(1.0, 1.0, 0.35);
                const inner = new THREE.Mesh(innerGeo, new THREE.MeshStandardMaterial({ color: biscuitColor, roughness: 0.7 }));
                inner.position.set(0, 0, 0.025);
                earPivot.add(inner);

                earPivot.rotation.z = isLeft ? 0.3 : -0.3;
                return earPivot;
            }
            leftEar = createBearEar(true);
            rightEar = createBearEar(false);
            headGroup.add(leftEar);
            headGroup.add(rightEar);

            // 3. Oval Biscuit Snout
            const snoutGeo = new THREE.SphereGeometry(0.18, 24, 24);
            snoutGeo.scale(1.15, 0.88, 1.0);
            const snoutMat = new THREE.MeshStandardMaterial({ color: biscuitColor, roughness: 0.7 });
            const snout = new THREE.Mesh(snoutGeo, snoutMat);
            snout.position.set(0, 1.30, 0.26);
            headGroup.add(snout);

            // 4. Round Charcoal Teddy Button Nose
            const nose = new THREE.Mesh(
                new THREE.SphereGeometry(0.048, 16, 16),
                new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.25 })
            );
            nose.scale.set(1.2, 0.85, 0.9);
            nose.position.set(0, 1.34, 0.43);
            headGroup.add(nose);

            // 5. Sparkly Button Eyes
            leftEye = createCuteEye(-0.14, irisColor, furColor);
            rightEye = createCuteEye(0.14, irisColor, furColor);
            headGroup.add(leftEye);
            headGroup.add(rightEye);

            // 6. Peach Blush Cheeks
            headGroup.add(createRosyCheek(-0.25, 1.31, 0.28, 0xfb923c));
            headGroup.add(createRosyCheek(0.25, 1.31, 0.28, 0xfb923c));

            // 7. Mouth & Lips
            const mouthGroup = new THREE.Group();
            mouthGroup.position.set(0, 1.23, 0.33);

            lowerLip = new THREE.Mesh(new THREE.TorusGeometry(0.052, 0.014, 12, 24, Math.PI), new THREE.MeshStandardMaterial({ color: 0x9a3412 }));
            lowerLip.position.set(0, -0.012, 0);
            mouthGroup.add(lowerLip);

            cavity = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 16), new THREE.MeshBasicMaterial({ color: 0x300c04 }));
            cavity.scale.set(1.1, 0.35, 0.2);
            cavity.position.set(0, -0.005, -0.01);
            mouthGroup.add(cavity);

            tongue = new THREE.Mesh(new THREE.SphereGeometry(0.035, 16, 16), new THREE.MeshStandardMaterial({ color: 0xf43f5e }));
            tongue.scale.set(1.0, 0.32, 1.2);
            tongue.position.set(0, -0.012, 0.018);
            mouthGroup.add(tongue);

            headGroup.add(mouthGroup);

            // 8. Teddy Body & Royal Blue Bow Tie
            const body = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.44, 0.55, 24), furMat);
            body.position.set(0, 0.83, 0);
            bodyGroup.add(body);

            // Biscuit tummy patch
            const belly = new THREE.Mesh(new THREE.SphereGeometry(0.26, 24, 24), snoutMat);
            belly.scale.set(0.75, 1.05, 0.3);
            belly.position.set(0, 0.83, 0.18);
            bodyGroup.add(belly);

            // Royal Blue Bow Tie with Red Knot
            const bowMat = new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.4 });
            const bowL = new THREE.Mesh(new THREE.ConeGeometry(0.075, 0.13, 16), bowMat);
            bowL.rotation.z = Math.PI / 2;
            bowL.position.set(-0.07, 1.07, 0.21);
            bodyGroup.add(bowL);

            const bowR = new THREE.Mesh(new THREE.ConeGeometry(0.075, 0.13, 16), bowMat);
            bowR.rotation.z = -Math.PI / 2;
            bowR.position.set(0.07, 1.07, 0.21);
            bodyGroup.add(bowR);

            const knot = new THREE.Mesh(new THREE.SphereGeometry(0.035, 16, 16), new THREE.MeshStandardMaterial({ color: 0xef4444 }));
            knot.position.set(0, 1.07, 0.23);
            bodyGroup.add(knot);
        }

        // Save animated part references
        animatedParts = {
            headGroup: headGroup,
            bodyGroup: bodyGroup,
            leftEye: leftEye,
            rightEye: rightEye,
            leftEar: leftEar,
            rightEar: rightEar,
            lowerLip: lowerLip,
            cavity: cavity,
            tongue: tongue,
            charType: type
        };
    }

    // Function to Switch Character with Sound & Speech
    function setCharacter(type, announce = true) {
        if (!['dog', 'bunny', 'bear'].includes(type)) type = 'dog';
        currentCharacter = type;
        buildCuteAvatar(type);

        // Update Top Bar Button
        if (charBtn) {
            if (type === 'dog') charBtn.innerText = '🐶 Dog';
            else if (type === 'bunny') charBtn.innerText = '🐰 Bunny';
            else if (type === 'bear') charBtn.innerText = '🐻 Bear';
        }

        // Update Speech Balloon Title
        if (balloonTitleEl) {
            if (type === 'dog') balloonTitleEl.innerText = '🐶 Cute Dog Assistant';
            else if (type === 'bunny') balloonTitleEl.innerText = '🐰 Fluffy Bunny Assistant';
            else if (type === 'bear') balloonTitleEl.innerText = '🐻 Teddy Bear Assistant';
        }

        // Update Settings Dropdown if open
        const cfgChar = document.getElementById('cfg-character');
        if (cfgChar) cfgChar.value = type;

        // Save to Extension Config
        GmailEngine.saveConfig({ avatar_character: type });

        if (announce) {
            let greeting = "Woof! I'm your cute puppy assistant, ready to fetch your emails!";
            if (type === 'bunny') greeting = "Hop hop! Fluffy bunny assistant at your service to sort your inbox!";
            else if (type === 'bear') greeting = "Hello friend! Teddy bear assistant ready to guard your inbox!";
            setAvatarRemark(greeting, true);
        }
    }

    // Character Switch Button in Top Bar
    if (charBtn) {
        charBtn.addEventListener('click', () => {
            const cycle = { 'dog': 'bunny', 'bunny': 'bear', 'bear': 'dog' };
            const nextChar = cycle[currentCharacter] || 'dog';
            setCharacter(nextChar, true);
        });
    }

    // Mouse Look Tracking
    let targetLookX = 0, targetLookY = 0;
    container.addEventListener('mousemove', (e) => {
        const rect = container.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
        targetLookX = x * 0.18;
        targetLookY = y * 0.12;
    });
    container.addEventListener('mouseleave', () => {
        targetLookX = 0;
        targetLookY = 0;
    });

    // Animation Render Loop
    let lastBlinkTime = 0;
    const clock = new THREE.Clock();

    function animate() {
        requestAnimationFrame(animate);
        const time = clock.getElapsedTime();
        controls.update();

        const p = animatedParts;
        if (!p || !p.headGroup) {
            renderer.render(scene, camera);
            return;
        }

        // 1. Natural Blinking Animation
        if (time - lastBlinkTime > 3.6) {
            const blinkProgress = (time - lastBlinkTime - 3.6) / 0.16;
            if (blinkProgress <= 1.0) {
                const blinkScale = Math.sin(blinkProgress * Math.PI) * 1.05;
                if (p.leftEye?.userData?.upperLid) p.leftEye.userData.upperLid.scale.y = Math.max(0.01, blinkScale);
                if (p.rightEye?.userData?.upperLid) p.rightEye.userData.upperLid.scale.y = Math.max(0.01, blinkScale);
            } else {
                if (p.leftEye?.userData?.upperLid) p.leftEye.userData.upperLid.scale.y = 0.01;
                if (p.rightEye?.userData?.upperLid) p.rightEye.userData.upperLid.scale.y = 0.01;
                lastBlinkTime = time;
            }
        }

        // 2. Gentle Idle Breathing
        p.headGroup.position.y = Math.sin(time * 2.0) * 0.014;
        if (p.bodyGroup) p.bodyGroup.position.y = Math.sin(time * 2.0) * 0.007;

        // 3. Speech & Ear Animation
        if (isSpeaking) {
            const mouthMv = Math.abs(Math.sin(time * 14)) * 0.042;
            if (p.lowerLip) p.lowerLip.position.y = -0.012 - mouthMv;
            if (p.cavity) p.cavity.scale.y = 0.35 + mouthMv * 24;
            if (p.tongue) p.tongue.position.y = -0.012 + mouthMv * 0.65;

            // Expressive Ear Bouncing per character
            if (p.charType === 'dog' && p.leftEar && p.rightEar) {
                // Floppy dog ears bounce rhythmically
                const earBounce = Math.abs(Math.sin(time * 10)) * 0.12;
                p.leftEar.rotation.z = -earBounce;
                p.rightEar.rotation.z = earBounce;
            } else if (p.charType === 'bunny' && p.leftEar && p.rightEar) {
                // Bunny ears twitch back and forth cutely
                p.leftEar.rotation.x = -0.08 + Math.sin(time * 13) * 0.10;
                p.rightEar.rotation.x = -0.08 + Math.cos(time * 13) * 0.10;
            } else if (p.charType === 'bear' && p.leftEar && p.rightEar) {
                // Round teddy ears wiggle
                p.leftEar.rotation.z = Math.sin(time * 9) * 0.08;
                p.rightEar.rotation.z = -Math.sin(time * 9) * 0.08;
            }

            // Head Nodding & Turning while speaking
            const headSpeakNod = Math.sin(time * 6) * 0.024;
            const headSpeakTurn = Math.sin(time * 2.5) * 0.032;
            p.headGroup.rotation.y = THREE.MathUtils.lerp(p.headGroup.rotation.y, targetLookX + headSpeakTurn, 0.08);
            p.headGroup.rotation.x = THREE.MathUtils.lerp(p.headGroup.rotation.x, -targetLookY + headSpeakNod, 0.08);

        } else {
            // Idle state: close mouth, reset ears gently
            if (p.lowerLip) p.lowerLip.position.y = -0.012;
            if (p.cavity) p.cavity.scale.y = 0.35;
            if (p.tongue) p.tongue.position.y = -0.012;

            if (p.charType === 'dog' && p.leftEar && p.rightEar) {
                p.leftEar.rotation.z = THREE.MathUtils.lerp(p.leftEar.rotation.z, 0, 0.05);
                p.rightEar.rotation.z = THREE.MathUtils.lerp(p.rightEar.rotation.z, 0, 0.05);
            } else if (p.charType === 'bunny' && p.leftEar && p.rightEar) {
                // Occasional subtle bunny ear twitch
                const twitch = Math.sin(time * 1.5) > 0.95 ? Math.sin(time * 20) * 0.06 : 0;
                p.leftEar.rotation.x = -0.08 + twitch;
                p.rightEar.rotation.x = -0.08 - twitch;
            } else if (p.charType === 'bear' && p.leftEar && p.rightEar) {
                p.leftEar.rotation.z = THREE.MathUtils.lerp(p.leftEar.rotation.z, 0, 0.05);
                p.rightEar.rotation.z = THREE.MathUtils.lerp(p.rightEar.rotation.z, 0, 0.05);
            }

            p.headGroup.rotation.y = THREE.MathUtils.lerp(p.headGroup.rotation.y, targetLookX, 0.06);
            p.headGroup.rotation.x = THREE.MathUtils.lerp(p.headGroup.rotation.x, -targetLookY, 0.06);
        }

        renderer.render(scene, camera);
    }
    animate();

    // Direct Gmail & AI Interaction
    async function updateStatus() {
        try {
            const count = await GmailEngine.getUnreadCount();
            agentStatus.innerText = `Active • ${count} unread`;
        } catch (e) {
            agentStatus.innerText = "Active • Ready";
        }
    }

    async function executePrompt(promptText) {
        if (!promptText) return;
        userInput.value = "";
        sendBtn.disabled = true;
        setAvatarRemark("I'm on it! Checking your mailbox...", true);

        // Forward to Gmail parent frame (content script has access to selected/open emails in DOM)
        if (window.parent && window.parent !== window) {
            window.parent.postMessage({
                type: "RESOLVE_PROMPT_WITH_DOM",
                promptText: promptText
            }, "*");
            setTimeout(() => {
                sendBtn.disabled = false;
                updateStatus();
            }, 3000);
            return;
        }

        try {
            const result = await GmailEngine.handleUserPrompt(promptText);
            sendBtn.disabled = false;
            setAvatarRemark(result.remark || "Done!", true);
            updateStatus();
        } catch (err) {
            sendBtn.disabled = false;
            const msg = (err && err.message) ? err.message : String(err);
            if (msg.includes('Extension context invalidated')) {
                setAvatarRemark('🔄 The extension was reloaded or updated. Please refresh this Gmail tab (F5) to reconnect!', true);
            } else {
                setAvatarRemark(`I encountered an issue: ${msg}`, true);
            }
        }
    }

    // Listen for remarks from content script (e.g. folder synopsis completed)
    window.addEventListener('message', (e) => {
        if (!e.data) return;
        if (e.data.type === "AVATAR_SET_REMARK" && e.data.remark) {
            setAvatarRemark(e.data.remark, true);
        }
    });

    inputForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (text) executePrompt(text);
    });

    document.querySelectorAll('.chip-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            executePrompt(btn.getAttribute('data-prompt'));
        });
    });

    // Startup: Load Character & Greet User
    setTimeout(async () => {
        try {
            const cfg = await GmailEngine.getConfig();
            const savedChar = cfg.avatar_character || 'dog';
            setCharacter(savedChar, false);
            await updateStatus();

            let initialGreeting = "Woof! I'm your cute puppy assistant. What would you like me to do with your inbox today?";
            if (savedChar === 'bunny') initialGreeting = "Hop hop! I'm your bunny assistant. Ready to scan or clean your inbox!";
            else if (savedChar === 'bear') initialGreeting = "Hello! I'm your teddy bear assistant. How can I help with your mail today?";

            setAvatarRemark(initialGreeting, true);
        } catch (e) {
            setCharacter('dog', false);
            setAvatarRemark("Woof! I'm ready to help you manage your inbox. Click 'Scan Inbox' or ask me anything!", true);
        }
        setInterval(updateStatus, 15000);
    }, 350);

})();
