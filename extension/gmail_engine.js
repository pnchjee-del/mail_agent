// Pure JavaScript Gmail & OpenAI AI Engine for Browser Extension
// Runs 100% locally in Chrome/Edge without any Python backend or batch files

const GmailEngine = (function () {
    let cachedConfig = null;
    let cachedAccessToken = null;
    let tokenExpiryTime = 0;
    const VALID_CATEGORIES = ['Work', 'Finance', 'Promotions', 'Personal', 'Support'];

    // Load initial config from auth_config.json merged with chrome.storage.local
    async function getConfig() {
        if (cachedConfig) return cachedConfig;

        // Read auth_config.json bundled with extension
        let fileConfig = {};
        try {
            const resp = await fetch(chrome.runtime.getURL('auth_config.json'));
            if (resp.ok) {
                fileConfig = await resp.json();
            }
        } catch (e) {
            console.warn("[GmailEngine] Could not read auth_config.json:", e);
        }

        // Try chrome.storage.local for user preferences (character, rules, etc.)
        const stored = await new Promise(resolve => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get(['gmail_agent_config'], result => {
                    resolve(result.gmail_agent_config || null);
                });
            } else {
                resolve(null);
            }
        });

        const defaults = {
            client_id: "",
            client_secret: "",
            refresh_token: "",
            ai_provider: "omniroute",
            use_omniroute: true,
            omniroute_base_url: "http://localhost:20128/v1",
            omniroute_api_key: "omniroute",
            omniroute_model: "auto",
            openai_api_key: "",
            openai_model: "gpt-4o-mini",
            designated_senders: ["client@example.com", "boss@company.com"],
            delete_senders: ["spam@promos.com", "newsletter@ads.com"],
            auto_delete: false,
            max_scan: 10,
            grace_period_minutes: 60,
            avatar_character: "dog",
            agent_enabled: true
        };

        // File credentials take precedence over stale stored tokens
        cachedConfig = {
            ...defaults,
            ...(stored || {}),
            ...fileConfig,
            avatar_character: stored?.avatar_character || fileConfig.avatar_character || defaults.avatar_character,
            designated_senders: stored?.designated_senders || fileConfig.designated_senders || defaults.designated_senders,
            delete_senders: stored?.delete_senders || fileConfig.delete_senders || defaults.delete_senders
        };

        return cachedConfig;
    }

    async function saveConfig(newConfig) {
        cachedConfig = { ...(cachedConfig || {}), ...newConfig };
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            await new Promise(resolve => {
                chrome.storage.local.set({ gmail_agent_config: cachedConfig }, resolve);
            });
        }
        return cachedConfig;
    }

    // Resolve AI Endpoint details (OmniRoute Gateway or direct OpenAI)
    function getAiEndpoint(cfg) {
        const useOmni = cfg.use_omniroute !== false && (cfg.ai_provider === 'omniroute' || !cfg.openai_api_key || cfg.use_omniroute);
        if (useOmni) {
            let base = (cfg.omniroute_base_url || 'http://localhost:20128/v1').trim().replace(/\/+$/, '');
            if (!base.endsWith('/v1')) {
                base += '/v1';
            }
            return {
                provider: 'omniroute',
                url: `${base}/chat/completions`,
                testUrl: `${base}/models`,
                apiKey: cfg.omniroute_api_key || 'omniroute',
                model: cfg.omniroute_model || 'auto'
            };
        }
        return {
            provider: 'openai',
            url: 'https://api.openai.com/v1/chat/completions',
            testUrl: 'https://api.openai.com/v1/models',
            apiKey: cfg.openai_api_key || '',
            model: cfg.openai_model || 'gpt-4o-mini'
        };
    }

    // Centralized AI Chat Completions caller with automatic failover
    async function callAiChatCompletion({ messages, max_tokens = 200, temperature = 0.2, model = null }) {
        const cfg = await getConfig();
        const primary = getAiEndpoint(cfg);
        const reqModel = model || primary.model;

        // 1. Try primary endpoint (OmniRoute by default)
        try {
            console.log(`[GmailEngine] Calling ${primary.provider.toUpperCase()} at ${primary.url} with model '${reqModel}'...`);
            const headers = { "Content-Type": "application/json" };
            if (primary.apiKey) {
                headers["Authorization"] = `Bearer ${primary.apiKey}`;
            }

            const resp = await fetch(primary.url, {
                method: "POST",
                headers,
                body: JSON.stringify({
                    model: reqModel,
                    messages,
                    max_tokens,
                    temperature
                })
            });

            if (resp.ok) {
                const data = await resp.json();
                const content = data.choices?.[0]?.message?.content;
                if (content) {
                    return { success: true, content, provider: primary.provider, model: reqModel };
                }
            } else {
                const errText = await resp.text();
                console.warn(`[GmailEngine] ${primary.provider} responded with error status ${resp.status}:`, errText);
            }
        } catch (err) {
            console.warn(`[GmailEngine] Failed to connect to ${primary.provider} (${primary.url}):`, err.message);
        }

        // 2. If OmniRoute failed and direct OpenAI key exists, fallback to OpenAI
        if (primary.provider === 'omniroute' && cfg.openai_api_key) {
            try {
                console.log("[GmailEngine] OmniRoute unavailable, attempting fallback to direct OpenAI API...");
                const resp = await fetch("https://api.openai.com/v1/chat/completions", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${cfg.openai_api_key}`
                    },
                    body: JSON.stringify({
                        model: cfg.openai_model || "gpt-4o-mini",
                        messages,
                        max_tokens,
                        temperature
                    })
                });
                if (resp.ok) {
                    const data = await resp.json();
                    const content = data.choices?.[0]?.message?.content;
                    if (content) {
                        return { success: true, content, provider: 'openai (fallback)', model: 'gpt-4o-mini' };
                    }
                }
            } catch (fbErr) {
                console.warn("[GmailEngine] OpenAI fallback also failed:", fbErr.message);
            }
        }

        return { success: false, content: null, provider: primary.provider };
    }

    // Function to test OmniRoute connection
    async function testOmniRouteConnection() {
        const cfg = await getConfig();
        const endpoint = getAiEndpoint({ ...cfg, ai_provider: 'omniroute', use_omniroute: true });
        try {
            const resp = await fetch(endpoint.url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${endpoint.apiKey}`
                },
                body: JSON.stringify({
                    model: endpoint.model,
                    messages: [{ role: "user", content: "Reply with the single word: OK" }],
                    max_tokens: 10
                })
            });

            if (resp.ok) {
                const data = await resp.json();
                const text = (data.choices?.[0]?.message?.content || "").trim();
                return {
                    ok: true,
                    url: endpoint.url,
                    model: endpoint.model,
                    reply: text,
                    message: `Connected successfully to OmniRoute (${endpoint.model})!`
                };
            } else {
                const errText = await resp.text();
                return {
                    ok: false,
                    url: endpoint.url,
                    status: resp.status,
                    error: errText,
                    message: `OmniRoute returned HTTP ${resp.status}: ${errText.slice(0, 100)}`
                };
            }
        } catch (e) {
            return {
                ok: false,
                url: endpoint.url,
                error: e.message,
                message: `Could not reach OmniRoute at ${endpoint.url}. Make sure OmniRoute is running (e.g. 'omniroute' on port 20128).`
            };
        }
    }

    // Refresh OAuth Access Token directly from Google
    async function getAccessToken() {
        const now = Date.now();
        if (cachedAccessToken && now < tokenExpiryTime - 60000) {
            return cachedAccessToken;
        }

        const cfg = await getConfig();
        if (!cfg.client_id || !cfg.refresh_token) {
            throw new Error("Missing Google OAuth client credentials or refresh token.");
        }

        const params = new URLSearchParams({
            client_id: cfg.client_id,
            client_secret: cfg.client_secret,
            refresh_token: cfg.refresh_token,
            grant_type: "refresh_token"
        });

        const resp = await fetch("https://oauth2.googleapis.com/token", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: params.toString()
        });

        if (!resp.ok) {
            const errBody = await resp.text();
            cachedAccessToken = null;
            if (errBody.includes("invalid_grant") || errBody.includes("expired or revoked")) {
                cachedConfig = null;
                if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                    chrome.storage.local.remove(['gmail_agent_config']);
                }
                throw new Error("Google OAuth token expired or revoked. Please run 'reauth.bat' in your mail_agent folder to sign in with Google again.");
            }
            throw new Error(`Failed to refresh Google token (${resp.status}): ${errBody}`);
        }

        const data = await resp.json();
        cachedAccessToken = data.access_token;
        const expiresInSec = data.expires_in || 3500;
        tokenExpiryTime = Date.now() + (expiresInSec * 1000);
        return cachedAccessToken;
    }

    // Fetch unread count
    async function getUnreadCount() {
        const token = await getAccessToken();
        const resp = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults=50", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!resp.ok) throw new Error(`Gmail API error: ${resp.status}`);
        const data = await resp.json();
        return (data.messages || []).length;
    }

    // AI Classification (OmniRoute or OpenAI)
    async function classifyEmail(sender, subject, snippet) {
        try {
            const prompt = `Classify this email into exactly one category: 'Work', 'Finance', 'Promotions', 'Personal', or 'Support'.
Sender: ${sender}
Subject: ${subject}
Snippet: ${snippet}

Respond with ONLY the single category name.`;

            const aiRes = await callAiChatCompletion({
                messages: [{ role: "user", content: prompt }],
                temperature: 0.0,
                max_tokens: 15
            });

            if (aiRes.success && aiRes.content) {
                const raw = aiRes.content.trim().replace(/['"]/g, '');
                for (const cat of VALID_CATEGORIES) {
                    if (raw.toLowerCase().includes(cat.toLowerCase())) {
                        return cat;
                    }
                }
            }
            return heuristicClassify(sender, subject, snippet);
        } catch (e) {
            console.warn("[GmailEngine] AI classify error, using heuristic:", e);
            return heuristicClassify(sender, subject, snippet);
        }
    }

    function heuristicClassify(sender, subject, snippet) {
        const text = `${sender} ${subject} ${snippet}`.toLowerCase();
        if (/invoice|payment|bank|receipt|billing|\$|wire|statement|tax|pension|salary|due\s+date/.test(text)) return "Finance";
        if (/discount|% off|sale|promo|deals|coupon|shop|newsletter|unsubscribe|special offer/.test(text)) return "Promotions";
        if (/ticket|support|issue|helpdesk|bug|case|service request|troubleshoot/.test(text)) return "Support";
        if (/project|client|team|task|report|meeting|proposal|contract|deadline|deliverable|agenda/.test(text)) return "Work";
        return "Personal";
    }

    function generateFallbackReplyBody(sender, subject, snippet) {
        const senderName = (sender.split('<')[0] || '').replace(/['"]/g, '').trim() || 'there';
        const subLower = (subject || '').toLowerCase();
        const snipLower = (snippet || '').toLowerCase();

        let responseCore = "Thank you for getting in touch.";
        if (snipLower.includes("attachment") || snipLower.includes("attached") || snipLower.includes("file") || snipLower.includes("document") || snipLower.includes("pdf")) {
            responseCore = "Thank you for sending over the attached document(s). I have received the files and am currently reviewing them.";
        } else if (snipLower.includes("meeting") || snipLower.includes("schedule") || snipLower.includes("calendar") || snipLower.includes("call") || snipLower.includes("zoom")) {
            responseCore = "Thank you for reaching out regarding the meeting. I am checking my schedule and will confirm our availability shortly.";
        } else if (snipLower.includes("invoice") || snipLower.includes("payment") || snipLower.includes("bill") || snipLower.includes("amount") || snipLower.includes("due")) {
            responseCore = "Thank you for the update regarding the payment/invoice details. I am reviewing the figures and will proceed promptly.";
        } else if (snipLower.includes("application") || snipLower.includes("licence") || snipLower.includes("license") || snipLower.includes("renewal") || snipLower.includes("form")) {
            responseCore = "Thank you for the update on the application. I have noted the details and am ensuring all required items are in order.";
        } else if (snipLower.includes("question") || snipLower.includes("inquiry") || snipLower.includes("status") || snipLower.includes("update") || snipLower.includes("help")) {
            responseCore = "Thank you for your inquiry. I am currently looking into this matter and will get back to you with a detailed update shortly.";
        } else {
            responseCore = `Thank you for your email regarding '${subject || "this matter"}'. I am reviewing your message and will follow up with you as soon as possible.`;
        }

        return `Hello ${senderName},\n\n${responseCore}\n\nPlease let me know if you need any additional information in the meantime.\n\nBest regards,\n[Your Name]`;
    }

    // AI Draft Reply Generation (OmniRoute or OpenAI) with intelligent fallback
    async function generateDraftReply(sender, subject, snippet, threadId) {
        let bodyText = null;

        try {
            const prompt = `Write a professional, concise email reply to the following message:
Sender: ${sender}
Subject: ${subject}
Content snippet: ${snippet}`;

            const aiRes = await callAiChatCompletion({
                messages: [{ role: "user", content: prompt }],
                max_tokens: 250
            });

            if (aiRes.success && aiRes.content) {
                bodyText = aiRes.content.trim();
            }
        } catch (e) {
            console.warn("[GmailEngine] AI draft generation error, using fallback:", e);
        }

        if (!bodyText) {
            bodyText = generateFallbackReplyBody(sender, subject, snippet);
        }

        try {
            const token = await getAccessToken();
            const cleanSub = subject.toLowerCase().startsWith('re:') ? subject : `Re: ${subject}`;
            const rawEmail = [
                `To: ${sender}`,
                `Subject: ${cleanSub}`,
                'Content-Type: text/plain; charset=utf-8',
                '',
                bodyText
            ].join('\r\n');

            const base64Raw = btoa(unescape(encodeURIComponent(rawEmail)))
                .replace(/\+/g, '-')
                .replace(/\//g, '_')
                .replace(/=+$/, '');

            const draftResp = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/drafts", {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    message: {
                        threadId: threadId,
                        raw: base64Raw
                    }
                })
            });

            if (!draftResp.ok) {
                console.warn("[GmailEngine] Draft create HTTP error:", draftResp.status);
                return null;
            }
            const draftData = await draftResp.json();

            return {
                id: draftData.id,
                to: sender,
                subject: cleanSub,
                preview: bodyText.length > 140 ? bodyText.slice(0, 140) + "..." : bodyText,
                body: bodyText
            };
        } catch (e) {
            console.warn("[GmailEngine] Draft creation error:", e);
            return null;
        }
    }

    // In-memory synopsis cache
    const synopsisCache = {};

    async function getSynopsisFromStorage(key) {
        if (synopsisCache[key]) return synopsisCache[key];
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            return new Promise(resolve => {
                chrome.storage.local.get([`synopsis_${key}`], res => {
                    if (res && res[`synopsis_${key}`]) {
                        synopsisCache[key] = res[`synopsis_${key}`];
                        resolve(res[`synopsis_${key}`]);
                    } else {
                        resolve(null);
                    }
                });
            });
        }
        return null;
    }

    async function saveSynopsisToStorage(key, synopsis) {
        synopsisCache[key] = synopsis;
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({ [`synopsis_${key}`]: synopsis });
        }
    }

    // Helper to format file sizes
    function formatAttachmentSize(bytes) {
        if (!bytes || bytes < 1024) return (bytes || 0) + ' B';
        const units = ['KB', 'MB', 'GB'];
        let u = -1;
        let b = bytes;
        do {
            b /= 1024;
            u++;
        } while (b >= 1024 && u < units.length - 1);
        return b.toFixed(1) + ' ' + units[u];
    }

    // Helper to recursively extract attachments from Gmail API message payload
    function extractAttachmentsFromPayload(payload) {
        const attachments = [];
        const docExts = ['.pdf', '.docx', '.xlsx', '.doc', '.xls', '.csv', '.txt', '.zip', '.rar', '.7z', '.json', '.xml', '.ppt', '.pptx', '.odt', '.ods'];
        function walk(part) {
            if (!part) return;
            let filename = (part.filename || '').trim();
            const body = part.body || {};
            const attId = body.attachmentId;
            const mimeType = part.mimeType || '';
            let isInline = false;
            let hasCid = false;

            if (part.headers) {
                for (const h of part.headers) {
                    const name = (h.name || '').toLowerCase();
                    const val = (h.value || '').toLowerCase();
                    if (name === 'content-disposition' && val.includes('inline')) {
                        isInline = true;
                    }
                    if (name === 'content-id') {
                        hasCid = true;
                    }
                    if (!filename && (name === 'content-disposition' || name === 'content-type')) {
                        const match = (h.value || '').match(/filename\*?=(?:UTF-8'')?["']?([^"';\r\n]+)/i) || (h.value || '').match(/name=["']?([^"';\r\n]+)/i);
                        if (match && match[1]) {
                            filename = match[1].trim();
                        }
                    }
                }
            }

            const fnLow = filename.toLowerCase();
            const isDoc = docExts.some(ext => fnLow.endsWith(ext));

            // Skip inline layout images and newsletter marketing graphics
            if (!isDoc && (isInline || hasCid || fnLow.startsWith('images/') || (fnLow && mimeType.startsWith('image/') && !attId))) {
                if (part.parts && Array.isArray(part.parts)) {
                    part.parts.forEach(walk);
                }
                return;
            }

            if (!filename && attId && !isInline) {
                const ext = mimeType.includes('/') ? mimeType.split('/')[1] : 'bin';
                filename = `attachment.${ext}`;
            }

            if (filename && (attId || isDoc)) {
                attachments.push({
                    filename: filename || 'Attachment',
                    file_type: mimeType || 'Attachment',
                    size_bytes: body.size || 0,
                    size_human: formatAttachmentSize(body.size || 0),
                    attachment_id: attId
                });
            }
            if (part.parts && Array.isArray(part.parts)) {
                part.parts.forEach(walk);
            }
        }
        walk(payload);
        return attachments;
    }

    // AI & Heuristic Email Synopsis Generator
    async function generateEmailSynopsis(emailData = {}) {
        const { id = "", sender = "Unknown Sender", subject = "No Subject", snippet = "", date = "", attachments = [] } = emailData;
        const cacheKey = (id || `${sender}::${subject}`).trim();

        // 1. Check Cache
        const cached = await getSynopsisFromStorage(cacheKey);
        if (cached) return cached;

        const cfg = await getConfig();

        // Heuristic fallback generator incorporating attachments
        function makeFallbackSynopsis() {
            let text = `${subject} ${snippet}`.toLowerCase();
            if (attachments && attachments.length > 0) {
                text += " " + attachments.map(a => a.filename).join(" ").toLowerCase();
            }

            let urgency = "Normal";
            if (text.includes("urgent") || text.includes("asap") || text.includes("deadline") || text.includes("action required") || text.includes("immediate") || text.includes("due today") || text.includes("critical")) {
                urgency = "Urgent";
            } else if (text.includes("newsletter") || text.includes("digest") || text.includes("promo") || text.includes("discount") || text.includes("sale") || text.includes("unsubscribe") || text.includes("weekly")) {
                urgency = "Low";
            }

            let action = "No action required (Informational)";
            if (text.includes("licence") || text.includes("license") || text.includes("application") || text.includes("renewal") || text.includes("form 2")) {
                action = "Review application and verify required documents";
            } else if (text.includes("please review") || text.includes("action required") || text.includes("please find attached") || text.includes("feedback needed") || text.includes("review the")) {
                action = attachments.length > 0 ? `Review attached document(s): ${attachments.map(a => a.filename).join(', ')}` : "Review requested by sender";
            } else if (text.includes("reply") || text.includes("respond") || text.includes("confirm") || text.includes("rsvp") || text.includes("let me know")) {
                action = "Response required from you";
            } else if (text.includes("invoice") || text.includes("payment") || text.includes("bill") || text.includes("due date") || text.includes("receipt")) {
                action = "Payment / bill review required";
            } else if (text.includes("meeting") || text.includes("calendar invite") || text.includes("zoom") || text.includes("google meet")) {
                action = "Meeting invitation / check schedule";
            } else if (attachments && attachments.length > 0) {
                action = `Review attached file: ${attachments[0].filename}`;
            }

            let category = "Personal";
            if (text.includes("invoice") || text.includes("payment") || text.includes("bank") || text.includes("receipt") || text.includes("billing") || text.includes("$") || text.includes("transfer")) {
                category = "Finance";
            } else if (text.includes("discount") || text.includes("% off") || text.includes("sale") || text.includes("promo") || text.includes("deals") || text.includes("shop")) {
                category = "Promotions";
            } else if (text.includes("ticket") || text.includes("support") || text.includes("issue") || text.includes("case") || text.includes("helpdesk")) {
                category = "Support";
            } else if (text.includes("project") || text.includes("client") || text.includes("team") || text.includes("task") || text.includes("report") || text.includes("deliverable")) {
                category = "Work";
            }

            const cleanSnippet = (snippet || "No additional preview content.").trim().replace(/\s+/g, ' ');
            const sentences = cleanSnippet.split(/(?<=[.?!])\s+/).filter(s => s.trim().length > 6);
            let tldr = sentences.slice(0, 2).join(' ') || `${subject} received from ${sender}.`;
            if (attachments && attachments.length > 0) {
                const attNames = attachments.map(a => a.filename).join(', ');
                if (!snippet || snippet.length < 15) {
                    tldr = `Attached file(s) [${attNames}] in message from ${sender}.`;
                } else {
                    tldr += ` [Attached: ${attNames}]`;
                }
            }

            const points = sentences.slice(1, 4);
            if (points.length === 0) {
                points.push(cleanSnippet.length > 130 ? cleanSnippet.slice(0, 130) + '...' : cleanSnippet);
            }
            if (attachments && attachments.length > 0) {
                points.push(`Attached Documents: ${attachments.map(a => `${a.filename} (${a.size_human || a.file_type || 'File'})`).join(', ')}`);
            }

            return {
                id,
                sender,
                subject,
                date,
                tldr,
                key_points: points,
                action_item: action,
                urgency,
                category,
                attachments: attachments || [],
                cachedAt: Date.now()
            };
        }

        // 2. AI API call (OmniRoute or OpenAI)
        try {
            const sysPrompt = `You are an elite executive email assistant. Given an email's sender, subject, snippet/content, and attached files, create an accurate, razor-sharp synopsis.
Always respond in strictly valid JSON with this exact schema (no markdown, no backticks, no quotes around output):
{
  "tldr": "1 or 2 clear, informative sentences summarizing the core message and highlighting any attached documents.",
  "key_points": [
    "Key takeaway or point 1",
    "Key takeaway or point 2"
  ],
  "action_item": "Specific action required from the user, or 'No action needed (Informational)'",
  "urgency": "Urgent" | "Normal" | "Low",
  "category": "Work" | "Finance" | "Promotions" | "Personal" | "Support"
}`;
            let attStr = "";
            if (attachments && attachments.length > 0) {
                attStr = "\nAttachments:\n" + attachments.map(a => `- ${a.filename} (${a.file_type || ''})`).join("\n");
            }
            const userContent = `Sender: ${sender}\nSubject: ${subject}\nSnippet/Content: ${snippet}${attStr}`;

            const aiRes = await callAiChatCompletion({
                messages: [
                    { role: "system", content: sysPrompt },
                    { role: "user", content: userContent }
                ],
                temperature: 0.1,
                max_tokens: 300
            });

            if (aiRes.success && aiRes.content) {
                let rawContent = aiRes.content.trim();
                if (rawContent.startsWith("```")) {
                    rawContent = rawContent.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
                }
                const parsed = JSON.parse(rawContent);
                const synopsis = {
                    id,
                    sender,
                    subject,
                    date,
                    tldr: parsed.tldr || `${subject} from ${sender}`,
                    key_points: Array.isArray(parsed.key_points) && parsed.key_points.length > 0 ? parsed.key_points : [snippet.slice(0, 120)],
                    action_item: parsed.action_item || "No action needed (Informational)",
                    urgency: ["Urgent", "Normal", "Low"].includes(parsed.urgency) ? parsed.urgency : "Normal",
                    category: VALID_CATEGORIES.includes(parsed.category) ? parsed.category : "Work",
                    cachedAt: Date.now()
                };
                await saveSynopsisToStorage(cacheKey, synopsis);
                return synopsis;
            }
        } catch (err) {
            console.warn("[GmailEngine] AI synopsis generation error, using fallback:", err);
        }

        // 3. Heuristic fallback
        const fallback = makeFallbackSynopsis();
        await saveSynopsisToStorage(cacheKey, fallback);
        return fallback;
    }

    // Read and summarize all emails from a folder/query
    async function readFolderEmails(options = {}) {
        const folderQuery = options.query || "in:inbox";
        const maxScan = options.maxScan || 20;
        const token = await getAccessToken();

        const q = encodeURIComponent(folderQuery);
        const listResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages?q=${q}&maxResults=${maxScan}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (!listResp.ok) throw new Error(`Could not read emails from folder (${listResp.status})`);
        const listData = await listResp.json();
        const messages = listData.messages || [];

        const emailsWithSynopsis = [];
        for (const m of messages) {
            try {
                const getResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${m.id}?format=full`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (!getResp.ok) continue;
                const msg = await getResp.json();
                const headers = msg.payload?.headers || [];
                const sender = headers.find(h => h.name.toLowerCase() === 'from')?.value || 'Unknown';
                const subject = headers.find(h => h.name.toLowerCase() === 'subject')?.value || 'No Subject';
                const date = headers.find(h => h.name.toLowerCase() === 'date')?.value || '';
                const snippet = msg.snippet || '';
                const attachments = extractAttachmentsFromPayload(msg.payload);

                const synopsis = await generateEmailSynopsis({
                    id: m.id,
                    sender,
                    subject,
                    snippet,
                    date,
                    attachments
                });

                emailsWithSynopsis.push({
                    id: m.id,
                    threadId: msg.threadId,
                    sender,
                    subject,
                    snippet,
                    date,
                    attachments,
                    synopsis
                });
            } catch (err) {
                console.warn(`[GmailEngine] Error processing folder mail ${m.id}:`, err);
            }
        }

        return emailsWithSynopsis;
    }

    // Get or Create Gmail Label
    async function getOrCreateLabel(labelName) {
        const token = await getAccessToken();
        const listResp = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/labels", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const listData = await listResp.json();
        const existing = (listData.labels || []).find(l => l.name.toLowerCase() === labelName.toLowerCase());
        if (existing) return existing.id;

        const createResp = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/labels", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: labelName,
                labelListVisibility: "labelShow",
                messageListVisibility: "show"
            })
        });
        const createdData = await createResp.json();
        return createdData.id;
    }

    // Trash an email
    async function trashEmail(messageId) {
        const token = await getAccessToken();
        const resp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${messageId}/trash`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        return resp.ok;
    }

    // Modify labels (add label(s), remove UNREAD)
    async function applyLabelAndMarkRead(messageId, labelIds) {
        const token = await getAccessToken();
        const ids = Array.isArray(labelIds) ? labelIds.filter(Boolean) : [labelIds].filter(Boolean);
        const resp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${messageId}/modify`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                addLabelIds: ids,
                removeLabelIds: ["UNREAD"]
            })
        });
        return resp.ok;
    }

    const MULTI_PART_TLDS = [
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
    ];

    const PUBLIC_WEBMAIL_DOMAINS = new Set([
        'gmail.com', 'googlemail.com', 'yahoo.com', 'yahoo.co.in', 'yahoo.co.uk',
        'ymail.com', 'hotmail.com', 'outlook.com', 'live.com', 'msn.com',
        'icloud.com', 'me.com', 'mac.com', 'aol.com', 'proton.me', 'protonmail.com',
        'zoho.com', 'mail.com', 'gmx.com', 'rediffmail.com'
    ]);

    const DELIVERY_RELAY_DOMAINS = new Set([
        'sendgrid.net', 'sendgrid.com', 'mailchimp.com', 'billdesk.com', 'razorpay.com',
        'amazonses.com', 'cmail19.com', 'cmail20.com', 'mandrillapp.com', 'hubspot.com',
        'salesforce.com', 'exacttarget.com', 'intercom-mail.com', 'zendesk.com', 'freshdesk.com',
        'sparkpostmail.com', 'mailgun.org', 'mailgun.com', 'postmarkapp.com', 'campaignmonitor.com'
    ]);

    const NAME_STOPWORDS = new Set([
        'bank', 'ltd', 'limited', 'pvt', 'inc', 'corp', 'corporation', 'llc',
        'team', 'support', 'care', 'customer', 'service', 'services', 'official',
        'alerts', 'alert', 'notifications', 'notification', 'updates', 'update',
        'india', 'statement', 'statements', 'estatement', 'e-statement', 'netbanking',
        'cards', 'credit', 'card', 'debit', 'online', 'the', 'and'
    ]);

    // Helper to extract clean sender display name, email, domain root, and folder label path (e.g. 'indusind')
    function parseSenderInfo(fromHdr, folderPrefix = "") {
        let raw = fromHdr || "Unknown";
        let senderName = "";
        let senderEmail = "";

        const emailMatch = raw.match(/<([^>]+)>/);
        if (emailMatch) {
            senderEmail = emailMatch[1].toLowerCase().trim();
            senderName = raw.replace(/<[^>]+>/, '').trim().replace(/^["']|["']$/g, '').trim();
        } else if (raw.includes('@')) {
            const m = raw.match(/[\w\.-]+@[\w\.-]+\.\w+/);
            senderEmail = m ? m[0].toLowerCase().trim() : raw.toLowerCase().trim();
            senderName = "";
        } else {
            senderName = raw.trim();
        }

        const cleanEmail = senderEmail || "";
        const emailUser = cleanEmail.split('@')[0] || "";
        const emailDomain = (cleanEmail.split('@')[1] || "").toLowerCase();

        // 1. Personal / Public Webmail
        if (PUBLIC_WEBMAIL_DOMAINS.has(emailDomain)) {
            let cleanPersonal = senderName;
            if (cleanPersonal && cleanPersonal.toLowerCase() !== cleanEmail && !/^(no[-_]?reply|notification|support|info)/i.test(cleanPersonal)) {
                cleanPersonal = cleanPersonal.replace(/[/\\\[\]^:]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 40);
            } else {
                cleanPersonal = emailUser || "personal";
            }
            const labelName = folderPrefix ? `${folderPrefix}/${cleanPersonal}` : cleanPersonal;
            return {
                raw,
                senderName: senderName || emailUser,
                senderEmail: cleanEmail,
                domain: emailDomain,
                folderSlug: cleanPersonal,
                labelName,
                folderPrefix
            };
        }

        // 2. Extract domain root SLD
        let domainRoot = "";
        if (emailDomain) {
            let rem = emailDomain;
            for (const multi of MULTI_PART_TLDS) {
                if (rem.endsWith(multi)) {
                    rem = rem.slice(0, -multi.length);
                    break;
                }
            }
            if (rem === emailDomain && rem.includes('.')) {
                rem = rem.slice(0, rem.lastIndexOf('.'));
            }
            const parts = rem.split('.');
            domainRoot = parts[parts.length - 1] ? parts[parts.length - 1].toLowerCase() : emailDomain;
        }

        // 3. Check for Delivery Relay where brand is in display name
        let brandFromName = "";
        if (senderName) {
            const tokens = senderName.match(/[a-zA-Z0-9]+/g) || [];
            const meaningful = tokens.filter(t => !NAME_STOPWORDS.has(t.toLowerCase()));
            if (meaningful.length > 0) {
                brandFromName = meaningful[0].toLowerCase();
            }
        }

        let folderSlug = "";
        if (DELIVERY_RELAY_DOMAINS.has(emailDomain) && brandFromName) {
            folderSlug = brandFromName;
        } else if (domainRoot) {
            folderSlug = domainRoot;
        } else if (brandFromName) {
            folderSlug = brandFromName;
        } else {
            folderSlug = emailUser || "unknown";
        }

        folderSlug = folderSlug.toLowerCase().replace(/[/\\\[\]^:]/g, '').trim().slice(0, 40) || "unknown";
        const labelName = folderPrefix ? `${folderPrefix}/${folderSlug}` : folderSlug;

        return {
            raw,
            senderName: senderName || folderSlug,
            senderEmail: cleanEmail,
            domain: emailDomain,
            folderSlug,
            labelName,
            folderPrefix
        };
    }

    // Purge ALL historical/previous emails from blocked senders
    async function purgeBlockedSendersHistory(options = {}) {
        const cfg = await getConfig();
        const blacklisted = (cfg.delete_senders || []).map(s => s.trim().toLowerCase()).filter(Boolean);
        const maxPerSender = options.maxPerSender || 100;
        const token = await getAccessToken();

        let totalPurged = 0;
        const details = [];
        const perSender = {};

        if (blacklisted.length === 0) {
            return { totalPurged: 0, perSender: {}, details: [] };
        }

        console.log("[GmailEngine] Purging historical emails from blocked senders:", blacklisted);

        for (const target of blacklisted) {
            let count = 0;
            try {
                const q = encodeURIComponent(`from:${target} -in:trash`);
                const listResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages?q=${q}&maxResults=${maxPerSender}`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });

                if (listResp.ok) {
                    const listData = await listResp.json();
                    const messages = listData.messages || [];

                    for (const m of messages) {
                        try {
                            let subj = "No Subject";
                            let fromHdr = target;
                            const getResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${m.id}?format=metadata&metadataHeaders=Subject&metadataHeaders=From`, {
                                headers: { "Authorization": `Bearer ${token}` }
                            });
                            if (getResp.ok) {
                                const metaData = await getResp.json();
                                const hdrs = metaData.payload?.headers || [];
                                subj = hdrs.find(h => h.name.toLowerCase() === 'subject')?.value || "No Subject";
                                fromHdr = hdrs.find(h => h.name.toLowerCase() === 'from')?.value || target;
                            }

                            const ok = await trashEmail(m.id);
                            if (ok) {
                                count++;
                                details.push({
                                    id: m.id,
                                    sender: fromHdr,
                                    subject: subj,
                                    category: "Trash",
                                    action: `Moved to Trash (Purged historical mail from blocked sender '${target}')`,
                                    isHistoricalPurge: true
                                });
                                console.log(`[GmailEngine] Purged previous mail '${subj}' from '${fromHdr}'.`);
                            }
                        } catch (err) {
                            console.warn(`[GmailEngine] Failed to trash message ${m.id}:`, err);
                        }
                    }
                }
            } catch (queryErr) {
                console.error(`[GmailEngine] Error querying past mail for '${target}':`, queryErr);
            }
            perSender[target] = count;
            totalPurged += count;
        }

        console.log(`[GmailEngine] Purge complete: ${totalPurged} previous emails moved to Trash.`);
        return { totalPurged, perSender, details };
    }

    // Main Triage Function: Process unread emails
    async function processUnreadEmails(options = {}) {
        const cfg = await getConfig();
        if (cfg && cfg.agent_enabled === false) {
            console.log("[GmailEngine] Agent is deactivated. Skipping processUnreadEmails.");
            return [];
        }
        const maxScan = options.maxScan || cfg.max_scan || 10;
        const autoDelete = options.autoDelete !== undefined ? options.autoDelete : (cfg.auto_delete !== false);
        const purgeHistory = options.purgeHistory !== undefined ? options.purgeHistory : true;
        const designated = (cfg.designated_senders || []).map(s => s.trim().toLowerCase()).filter(Boolean);
        const blacklisted = (cfg.delete_senders || []).map(s => s.trim().toLowerCase()).filter(Boolean);

        const processedResults = [];

        // 0. Purge historical/previous emails from blocked senders
        if (autoDelete && purgeHistory && blacklisted.length > 0) {
            try {
                const purgeRes = await purgeBlockedSendersHistory();
                if (purgeRes.details && purgeRes.details.length > 0) {
                    processedResults.push(...purgeRes.details);
                }
            } catch (purgeErr) {
                console.warn("[GmailEngine] Auto-purge historical blocked senders failed:", purgeErr);
            }
        }

        const token = await getAccessToken();
        const listResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults=${maxScan}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (!listResp.ok) throw new Error(`Could not list unread messages: ${listResp.status}`);
        const listData = await listResp.json();
        const messages = listData.messages || [];

        if (messages.length === 0) {
            return processedResults;
        }

        for (const m of messages) {
            try {
                const getResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${m.id}?format=full`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (!getResp.ok) continue;
                const msg = await getResp.json();
                const headers = msg.payload?.headers || [];
                const sender = headers.find(h => h.name.toLowerCase() === 'from')?.value || 'Unknown';
                const subject = headers.find(h => h.name.toLowerCase() === 'subject')?.value || 'No Subject';
                const snippet = msg.snippet || '';
                const threadId = msg.threadId;
                const internalDateMs = parseInt(msg.internalDate || '0', 10);
                const senderLower = sender.toLowerCase();

                // 1. Blacklist Check (Checked FIRST so blocked senders are immediately trashed and not kept intact!)
                const isBlacklisted = blacklisted.some(target => senderLower.includes(target));
                if (isBlacklisted) {
                    if (autoDelete) {
                        await trashEmail(m.id);
                        processedResults.push({
                            id: m.id,
                            sender: sender,
                            subject: subject,
                            snippet: snippet,
                            category: "Trash",
                            action: "Moved to Trash (Blocked Sender)"
                        });
                        continue;
                    }
                }

                // 2. 1-Hour Grace Period for Legitimate Emails: Keep newly arrived emails intact at the top of the inbox
                const gracePeriodMinutes = options.gracePeriodMinutes !== undefined
                    ? options.gracePeriodMinutes
                    : (cfg.grace_period_minutes !== undefined ? cfg.grace_period_minutes : 60);
                const gracePeriodMs = gracePeriodMinutes * 60 * 1000;

                if (internalDateMs > 0) {
                    const ageMs = Date.now() - internalDateMs;
                    if (ageMs < gracePeriodMs) {
                        const minsAgo = Math.max(0, Math.floor(ageMs / 60000));
                        console.log(`[GmailEngine] Keeping newly arrived email '${subject}' intact on top of inbox (arrived ${minsAgo}m ago, cooling for ${gracePeriodMinutes}m).`);
                        processedResults.push({
                            id: m.id,
                            sender: sender,
                            subject: subject,
                            snippet: snippet,
                            category: "Inbox (Top)",
                            action: `Kept Intact on Top of Inbox (${minsAgo}m old, 1h grace)`,
                            draft: null,
                            isIntact: true
                        });
                        continue; // Leave completely intact, unread, and untouched on top of inbox!
                    }
                }

                // 3. Auto-draft Reply for Designated Senders
                let draftInfo = null;
                const isDesignated = designated.some(target => senderLower.includes(target));
                if (isDesignated) {
                    draftInfo = await generateDraftReply(sender, subject, snippet, threadId);
                }

                // 4. Classify & Move to Category Label + Sender Folder
                const category = await classifyEmail(sender, subject, snippet);
                const categoryLabelId = await getOrCreateLabel(category);

                // Auto-create and assign sender-named folder
                const senderInfo = parseSenderInfo(sender, "Senders");
                const senderLabelId = await getOrCreateLabel(senderInfo.labelName);

                const labelsToApply = [categoryLabelId, senderLabelId].filter(Boolean);
                await applyLabelAndMarkRead(m.id, labelsToApply);

                processedResults.push({
                    id: m.id,
                    sender: sender,
                    senderName: senderInfo.senderName,
                    subject: subject,
                    snippet: snippet,
                    category: category,
                    senderFolder: senderInfo.labelName,
                    action: draftInfo ? `Drafted Reply & Sorted into ${category} + ${senderInfo.labelName}` : `Categorized (${category}) & Sorted into ${senderInfo.labelName}`,
                    draft: draftInfo
                });

            } catch (msgErr) {
                console.error("[GmailEngine] Error processing email:", msgErr);
            }
        }

        return processedResults;
    }

    // Sort emails sender-wise, create Gmail sender folders, and group by sender using batchModify
    async function sortEmailsBySender(options = {}) {
        const cfg = await getConfig();
        const folderPrefix = options.folderPrefix !== undefined ? options.folderPrefix : (cfg.sender_folder_prefix || "");
        const folderQuery = options.folderQuery || "-in:trash -in:spam";
        const fetchAll = options.fetchAll !== false;
        const maxResults = options.maxResults || (fetchAll ? 150 : 50);
        const createLabels = options.createLabels !== false;
        const token = await getAccessToken();

        try {
            // 1. Paginated fetch of message IDs up to maxResults
            let allMessages = [];
            let pageToken = null;
            let pageCount = 0;
            const pageSize = Math.min(maxResults, 100);

            do {
                let url = `https://gmail.googleapis.com/gmail/v1/users/me/messages?q=${encodeURIComponent(folderQuery)}&maxResults=${pageSize}`;
                if (pageToken) {
                    url += `&pageToken=${encodeURIComponent(pageToken)}`;
                }
                const listResp = await fetch(url, { headers: { "Authorization": `Bearer ${token}` } });
                if (!listResp.ok) throw new Error(`Could not query mailbox: ${listResp.status}`);
                const listData = await listResp.json();
                const msgs = listData.messages || [];
                allMessages.push(...msgs);
                pageToken = listData.nextPageToken;
                pageCount++;
                if (!fetchAll || allMessages.length >= maxResults || !pageToken) {
                    break;
                }
            } while (pageToken && allMessages.length < maxResults && pageCount < 6);

            if (allMessages.length > maxResults) {
                allMessages = allMessages.slice(0, maxResults);
            }

            if (allMessages.length === 0) {
                return {
                    remark: `I checked your mailbox (${folderQuery}) and found 0 emails to sort.`,
                    totalEmails: 0,
                    totalSenders: 0,
                    senderGroups: [],
                    details: []
                };
            }

            // 2. Pre-fetch existing labels in ONE call to avoid redundant API queries
            const existingLabels = new Map();
            try {
                const labelsResp = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/labels", {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (labelsResp.ok) {
                    const lData = await labelsResp.json();
                    for (const lbl of (lData.labels || [])) {
                        if (lbl.name && lbl.id) {
                            existingLabels.set(lbl.name.toLowerCase(), lbl.id);
                        }
                    }
                }
            } catch (le) {
                console.warn("[GmailEngine] Could not pre-fetch labels list:", le);
            }

            async function ensureSenderLabel(labelName) {
                const key = labelName.toLowerCase();
                if (existingLabels.has(key)) {
                    return existingLabels.get(key);
                }
                try {
                    const cResp = await fetch("https://gmail.googleapis.com/gmail/v1/users/me/labels", {
                        method: "POST",
                        headers: {
                            "Authorization": `Bearer ${token}`,
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            name: labelName,
                            labelListVisibility: "labelShow",
                            messageListVisibility: "show"
                        })
                    });
                    if (cResp.ok) {
                        const created = await cResp.json();
                        existingLabels.set(key, created.id);
                        return created.id;
                    }
                } catch (ce) {
                    console.warn(`[GmailEngine] Failed creating label '${labelName}':`, ce);
                }
                return null;
            }

            // Ensure parent Senders folder exists
            if (createLabels && folderPrefix) {
                await ensureSenderLabel(folderPrefix);
            }

            // 3. Fetch message headers in parallel chunks using lightweight format=metadata
            const CHUNK_SIZE = 15;
            const fetchedMessages = [];

            for (let i = 0; i < allMessages.length; i += CHUNK_SIZE) {
                const chunk = allMessages.slice(i, i + CHUNK_SIZE);
                const chunkResults = await Promise.all(chunk.map(async (m) => {
                    try {
                        const getResp = await fetch(
                            `https://gmail.googleapis.com/gmail/v1/users/me/messages/${m.id}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date`,
                            { headers: { "Authorization": `Bearer ${token}` } }
                        );
                        if (!getResp.ok) return null;
                        return await getResp.json();
                    } catch (e) {
                        return null;
                    }
                }));
                fetchedMessages.push(...chunkResults.filter(Boolean));
            }

            // 4. Group by sender and prepare batch label modifications
            const sendersMap = {};
            const emailDetails = [];

            for (const msg of fetchedMessages) {
                const headers = msg.payload?.headers || [];
                const fromHdr = headers.find(h => h.name.toLowerCase() === 'from')?.value || 'Unknown';
                const subject = headers.find(h => h.name.toLowerCase() === 'subject')?.value || 'No Subject';
                const dateVal = headers.find(h => h.name.toLowerCase() === 'date')?.value || '';
                const snippet = msg.snippet || '';
                const labelIds = msg.labelIds || [];
                const isUnread = labelIds.includes('UNREAD');

                const senderInfo = parseSenderInfo(fromHdr, folderPrefix);
                // Group by folderSlug so all emails from the same sender (e.g. IndusInd) belong to one group!
                const senderKey = senderInfo.folderSlug || senderInfo.labelName.toLowerCase();

                const emailItem = {
                    id: msg.id,
                    sender: fromHdr,
                    senderName: senderInfo.senderName,
                    senderEmail: senderInfo.senderEmail,
                    subject,
                    date: dateVal,
                    snippet,
                    category: `Sender: ${senderInfo.senderName}`,
                    action: `Sorted into '${senderInfo.labelName}'`,
                    isUnread,
                    senderLabel: senderInfo.labelName
                };
                emailDetails.push(emailItem);

                if (!sendersMap[senderKey]) {
                    sendersMap[senderKey] = {
                        senderKey,
                        senderName: senderInfo.senderName,
                        senderEmail: senderInfo.senderEmail,
                        rawFrom: fromHdr,
                        labelName: senderInfo.labelName,
                        count: 0,
                        unreadCount: 0,
                        emails: [],
                        pendingMessageIds: []
                    };
                }

                const grp = sendersMap[senderKey];
                grp.count++;
                if (isUnread) grp.unreadCount++;
                grp.emails.push(emailItem);
                grp.pendingMessageIds.push({ id: msg.id, existingLabelIds: labelIds });
            }

            // 5. Create labels for each unique sender and execute batchModify
            if (createLabels) {
                for (const grp of Object.values(sendersMap)) {
                    const labelId = await ensureSenderLabel(grp.labelName);
                    if (!labelId) continue;

                    // Filter message IDs that don't already have this label
                    const idsToApply = grp.pendingMessageIds
                        .filter(p => !p.existingLabelIds.includes(labelId))
                        .map(p => p.id);

                    if (idsToApply.length > 0) {
                        for (let b = 0; b < idsToApply.length; b += 50) {
                            const batchIds = idsToApply.slice(b, b + 50);
                            try {
                                await fetch("https://gmail.googleapis.com/gmail/v1/users/me/messages/batchModify", {
                                    method: "POST",
                                    headers: {
                                        "Authorization": `Bearer ${token}`,
                                        "Content-Type": "application/json"
                                    },
                                    body: JSON.stringify({
                                        ids: batchIds,
                                        addLabelIds: [labelId]
                                    })
                                });
                            } catch (be) {
                                console.warn(`[GmailEngine] batchModify failed for ${grp.labelName}:`, be);
                            }
                        }
                    }
                }
            }

            const senderGroups = Object.values(sendersMap).sort((a, b) => b.count - a.count);

            const topBullets = senderGroups.slice(0, 6).map(g =>
                `• 📁 ${g.labelName}: ${g.count} email${g.count > 1 ? 's' : ''}${g.unreadCount ? ` (${g.unreadCount} unread)` : ''}`
            ).join('\n');

            const folderDesc = folderPrefix ? `under '${folderPrefix}/'` : 'directly';
            const remark = `📬 I've sorted all ${emailDetails.length} emails sender-wise into ${senderGroups.length} folders ${folderDesc} (e.g., all mails from IndusInd into folder 'indusind', and similar for other senders)!\n\nTop Sender Folders:\n${topBullets}\n\nAll future incoming emails from these senders will also be automatically organized into their respective folders.`;

            return {
                remark,
                totalEmails: emailDetails.length,
                totalSenders: senderGroups.length,
                senderGroups,
                details: emailDetails
            };
        } catch (e) {
            return {
                remark: `I had an issue sorting your emails sender-wise: ${e.message}`,
                totalEmails: 0,
                totalSenders: 0,
                senderGroups: [],
                details: []
            };
        }
    }

    // Block sender permanently, save config, and purge existing emails
    async function blockSender(senderTarget, options = {}) {
        let cleanTarget = (senderTarget || "").trim().toLowerCase();
        const selectedId = options.selectedEmailId;
        const purgeNow = options.purgeNow !== false;

        // If target is "this" or empty, resolve from selected email or latest inbox email
        if ((cleanTarget === "this" || cleanTarget === "this sender" || !cleanTarget) && selectedId) {
            try {
                const token = await getAccessToken();
                const resp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${selectedId}?format=metadata&metadataHeaders=From`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (resp.ok) {
                    const data = await resp.json();
                    const fromHdr = (data.payload?.headers || []).find(h => h.name.toLowerCase() === 'from')?.value || '';
                    const match = fromHdr.match(/<([^>]+)>/);
                    cleanTarget = (match ? match[1] : fromHdr).toLowerCase().trim();
                }
            } catch (e) {
                console.warn("[GmailEngine] Could not resolve sender from selected email:", e);
            }
        }

        // Extract email if formatted as "Name <email@domain.com>"
        const match = cleanTarget.match(/<([^>]+)>/);
        if (match) cleanTarget = match[1].toLowerCase().trim();
        cleanTarget = cleanTarget.replace(/['"<>]/g, '').trim();

        if (!cleanTarget || cleanTarget === "this" || cleanTarget === "sender") {
            return {
                remark: "Please specify the email address or sender you want to block (e.g., 'block spam@example.com').",
                blockedSender: null,
                purgedCount: 0
            };
        }

        const cfg = await getConfig();
        const currentList = (cfg.delete_senders || []).map(s => s.trim().toLowerCase());
        const alreadyBlocked = currentList.includes(cleanTarget);

        if (!alreadyBlocked) {
            currentList.push(cleanTarget);
            await saveConfig({ delete_senders: currentList });
        }

        let purgedCount = 0;
        if (purgeNow) {
            try {
                const token = await getAccessToken();
                const q = encodeURIComponent(`from:${cleanTarget} -in:trash`);
                const listResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages?q=${q}&maxResults=100`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (listResp.ok) {
                    const listData = await listResp.json();
                    for (const m of (listData.messages || [])) {
                        await trashEmail(m.id);
                        purgedCount++;
                    }
                }
            } catch (pe) {
                console.warn("[GmailEngine] Error purging historical emails for", cleanTarget, pe);
            }
        }

        const prefix = alreadyBlocked ? `⚠️ Sender '${cleanTarget}' is already in your blocked list.` : `🚫 **Blocked sender '${cleanTarget}'!**`;
        const remark = `${prefix}\n\n• Added to your blacklist rules in settings\n• Moved ${purgedCount} past email${purgedCount > 1 ? 's' : ''} from this sender to Trash\n• All future emails from '${cleanTarget}' will be automatically trashed.`;

        return {
            remark,
            blockedSender: cleanTarget,
            purgedCount
        };
    }

    // Unblock sender
    async function unblockSender(senderTarget) {
        let cleanTarget = (senderTarget || "").trim().toLowerCase();
        const match = cleanTarget.match(/<([^>]+)>/);
        if (match) cleanTarget = match[1].toLowerCase().trim();
        cleanTarget = cleanTarget.replace(/['"<>]/g, '').trim();

        const cfg = await getConfig();
        const currentList = (cfg.delete_senders || []).map(s => s.trim().toLowerCase());
        const filtered = currentList.filter(s => s !== cleanTarget && !s.includes(cleanTarget));

        if (filtered.length === currentList.length) {
            return {
                remark: `Sender '${cleanTarget}' was not found in your blocked senders list.`,
                unblocked: null
            };
        }

        await saveConfig({ delete_senders: filtered });
        return {
            remark: `✅ Unblocked sender '${cleanTarget}'. They have been removed from your blacklist.`,
            unblocked: cleanTarget
        };
    }

    // List all blocked senders
    async function listBlockedSenders() {
        const cfg = await getConfig();
        const blacklisted = (cfg.delete_senders || []).filter(Boolean);
        if (blacklisted.length === 0) {
            return {
                remark: "📋 You currently have 0 blocked senders. Your blacklist is clean!",
                blockedSenders: []
            };
        }
        const listStr = blacklisted.map(s => `• ${s}`).join('\n');
        return {
            remark: `📋 You currently have ${blacklisted.length} blocked sender(s):\n\n${listStr}\n\nAll emails from these senders are automatically moved to Trash.`,
            blockedSenders: blacklisted
        };
    }

    // Handle Natural Language Prompt from User
    async function handleUserPrompt(userPrompt) {
        const pLower = userPrompt.toLowerCase().trim();
        const cfg = await getConfig();
        const blacklisted = (cfg.delete_senders || []).map(s => s.trim().toLowerCase()).filter(Boolean);

        // 1. Sender-wise Email Sorting Intent
        const isSortSender = pLower.includes("sender wise") || pLower.includes("by sender") ||
            (pLower.includes("sort") && (pLower.includes("sender") || pLower.includes("senders") || pLower.includes("mail") || pLower.includes("email"))) ||
            (pLower.includes("organize") && pLower.includes("sender")) ||
            (pLower.includes("group") && pLower.includes("sender")) ||
            (pLower.includes("sender") && pLower.includes("wise")) ||
            pLower.includes("indusind") ||
            pLower.includes("put in a folder") ||
            pLower.includes("shall be put in a folder") ||
            pLower.includes("different folders") ||
            pLower.includes("folder named according") ||
            pLower.includes("folders named according") ||
            pLower.includes("according senders") ||
            pLower.includes("according to senders");

        if (isSortSender) {
            const isAll = pLower.includes("all") || pLower.includes("everything") || pLower.includes("entire");
            let targetQuery = "-in:trash -in:spam";
            let targetSender = null;
            let needsTarget = false;

            if (!pLower.includes("sender wise") && !pLower.includes("and similar") && !pLower.includes("by sender") && !pLower.includes("each sender") && !pLower.includes("all senders")) {
                const qMatch = userPrompt.match(/(?:from|for)\s+["']([^"']+)["']/i);
                if (qMatch) {
                    targetSender = qMatch[1].trim();
                } else {
                    const emMatch = userPrompt.match(/[\w\.-]+@[\w\.-]+\.\w+/);
                    if (emMatch) {
                        targetSender = emMatch[0].toLowerCase();
                    } else {
                        const wMatch = pLower.match(/(?:from|for)\s+([a-zA-Z0-9_\-\.]+)/);
                        const stopWords = ["each", "all", "every", "the", "a", "sender", "senders", "this", "particular", "specific", "one", "any", "my", "me", "our"];
                        if (wMatch && !stopWords.includes(wMatch[1])) {
                            targetSender = wMatch[1];
                        }
                    }
                }

                if (!targetSender && (pLower.includes("particular sender") || pLower.includes("specific sender") || pLower.includes("a sender"))) {
                    needsTarget = true;
                }

                if (targetSender) {
                    targetQuery = `from:${targetSender} -in:trash -in:spam`;
                }
            }

            if (!targetSender && needsTarget) {
                return {
                    remark: "📁 I can certainly put all mails from a particular sender in a folder named after that sender!\n\nWhich sender would you like me to sort? You can specify:\n• An email: 'put all mails from client@example.com in a folder'\n• A brand/bank: 'put all mails from IndusInd in a folder'\n• A name: 'put all mails from \"John Doe\" in a folder'",
                    sender_groups: [],
                    details: []
                };
            }

            return await sortEmailsBySender({
                createLabels: true,
                fetchAll: true,
                maxResults: isAll ? 200 : 50,
                folderQuery: targetQuery,
                targetSender: targetSender
            });
        }

        // 2. Block Sender Intent
        const isBlock = (pLower.startsWith("block") || pLower.includes("blacklist") || pLower.includes("ban")) &&
            !pLower.includes("who is blocked") && !pLower.includes("blocked senders") && !pLower.includes("delete all previous") && !pLower.includes("purge blocked");

        if (isBlock) {
            const emailMatch = userPrompt.match(/[\w\.-]+@[\w\.-]+\.\w+/);
            let target = emailMatch ? emailMatch[0] : "";
            if (!target) {
                const words = pLower.split(/\s+/);
                const sIdx = words.findIndex(w => w === "sender");
                if (sIdx !== -1 && words[sIdx + 1]) {
                    target = words[sIdx + 1];
                } else if (words.length > 1) {
                    target = words[words.length - 1];
                }
            }
            return await blockSender(target, { purgeNow: true });
        }

        // 3. Unblock Sender Intent
        const isUnblock = pLower.startsWith("unblock") || pLower.includes("unblock sender") || pLower.includes("whitelist");
        if (isUnblock) {
            const emailMatch = userPrompt.match(/[\w\.-]+@[\w\.-]+\.\w+/);
            const target = emailMatch ? emailMatch[0] : (pLower.split(/\s+/).pop() || "");
            return await unblockSender(target);
        }

        // 4. List Blocked Senders Intent
        const isListBlocked = pLower.includes("who is blocked") || pLower.includes("list blocked") || pLower.includes("show blocked") ||
            (pLower.includes("blocked senders") && !pLower.includes("clean") && !pLower.includes("trash") && !pLower.includes("delete"));
        if (isListBlocked) {
            return await listBlockedSenders();
        }

        // 1. Unread count question
        const isCount = (pLower.includes("how many") || pLower.includes("unread count") || pLower.includes("how many unread")) && !pLower.includes("scan") && !pLower.includes("clean") && !pLower.includes("trash");
        if (isCount) {
            try {
                const count = await getUnreadCount();
                return {
                    remark: `I checked your inbox: you currently have ${count}${count === 50 ? '+' : ''} unread email${count !== 1 ? 's' : ''}. Would you like me to scan and organize them?`,
                    results: []
                };
            } catch (e) {
                return { remark: `I had trouble checking your unread emails: ${e.message}`, results: [] };
            }
        }

        // 2. Draft Reply Intent ("make a draft reply", "draft reply", "draft a reply", "create draft")
        const isDraft = [
            "draft reply", "make a draft", "create a draft", "draft a reply",
            "compose a draft", "draft response", "prepare a draft", "write a draft",
            "reply draft", "write a reply", "create draft", "draft an email",
            "make draft reply", "make draft", "draft a response", "make a reply draft"
        ].some(k => pLower.includes(k)) || (
            pLower.includes("draft") && ["reply", "make", "create", "write", "compose", "prepare", "response"].some(w => pLower.includes(w))
        ) || (
            (pLower.startsWith("reply to") || pLower.includes("reply to the")) && !pLower.includes("scan")
        );

        if (isDraft) {
            try {
                const token = await getAccessToken();
                const listResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages?q=in:inbox&maxResults=5`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (!listResp.ok) throw new Error(`Could not query inbox: ${listResp.status}`);
                const listData = await listResp.json();
                const messages = listData.messages || [];
                if (messages.length === 0) {
                    return { remark: "I searched your inbox and found no emails to reply to.", results: [] };
                }

                const targetId = messages[0].id;
                const getResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${targetId}?format=full`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (!getResp.ok) throw new Error(`Could not fetch email details: ${getResp.status}`);
                const msg = await getResp.json();
                const headers = msg.payload?.headers || [];
                const sender = headers.find(h => h.name.toLowerCase() === 'from')?.value || 'Unknown';
                const subject = headers.find(h => h.name.toLowerCase() === 'subject')?.value || 'No Subject';
                const snippet = msg.snippet || '';
                const threadId = msg.threadId || targetId;

                const draftInfo = await generateDraftReply(sender, subject, snippet, threadId);
                if (draftInfo) {
                    const remark = `✉️ I've created a draft reply for you in Gmail Drafts to '${sender}' regarding '${subject}'!\n\nDraft Preview:\n"${draftInfo.preview}"\n\nYou can review, edit, or send it directly in Gmail!`;
                    return {
                        remark,
                        results: [{
                            id: targetId,
                            sender,
                            subject,
                            snippet,
                            category: "Draft",
                            action: `Created Draft Reply (ID: ${draftInfo.id})`,
                            draft: draftInfo
                        }]
                    };
                } else {
                    return { remark: `I found the email '${subject}' from '${sender}', but had an issue creating the draft.`, results: [] };
                }
            } catch (e) {
                return { remark: `I had an issue preparing your draft reply: ${e.message}`, results: [] };
            }
        }

        // 3. Attachment Summary Intent ("summarize mail with attachment", "read attachments", "summarize attachment")
        const isAttachmentIntent = [
            "summarize mail with attachment", "summarize mail with attachments",
            "summarize the email with attachment", "summarize email with attachment",
            "summarize emails with attachments", "mail with attachment", "email with attachment",
            "read attachment", "read attachments", "attached file", "attached files",
            "check attachment", "summarize attachment", "what is attached", "whats attached",
            "summarize attached", "summerise attached", "summarising attached", "summarizing attached",
            "summarize the attached", "summerise the attached", "summarising the attached",
            "summarizing the attached", "attached document", "attached documents",
            "summarize documents", "summerise documents", "read attached documents",
            "read the attached", "check attached", "inspect attachment", "analyze attachment",
            "attachment summary", "summarize attachments", "summerise attachments"
        ].some(k => pLower.includes(k)) || (
            (pLower.includes("attachment") || pLower.includes("attached") || pLower.includes("document")) &&
            ["read", "summar", "summer", "check", "what", "tell", "inspect", "show", "mail", "email"].some(k => pLower.includes(k))
        );

        if (isAttachmentIntent) {
            try {
                const token = await getAccessToken();

                let query = "has:attachment";
                const stopwords = ["summarize", "summerise", "summary", "mail", "email", "with", "attachment", "attachments", "attached", "the", "selected", "this", "my", "a", "an", "please", "can", "you", "and", "document", "documents", "file", "files", "check", "inspect", "read", "show", "tell", "give", "me", "that"];
                const targetWords = pLower.split(/\s+/).filter(w => !stopwords.includes(w) && w.length > 2);
                if (targetWords.length > 0) {
                    query += " " + targetWords.join(" ");
                }

                let listResp = await fetch(
                    `https://gmail.googleapis.com/gmail/v1/users/me/messages?q=${encodeURIComponent(query)}&maxResults=10`,
                    { headers: { "Authorization": `Bearer ${token}` } }
                );
                let listData = await listResp.json();
                let messages = listData.messages || [];

                if (messages.length === 0 && query !== "has:attachment") {
                    listResp = await fetch(
                        `https://gmail.googleapis.com/gmail/v1/users/me/messages?q=has:attachment&maxResults=10`,
                        { headers: { "Authorization": `Bearer ${token}` } }
                    );
                    listData = await listResp.json();
                    messages = listData.messages || [];
                }

                if (messages.length === 0) {
                    return { remark: "I searched your mailbox and found no recent emails with attachments.", results: [] };
                }

                const foundEmails = [];
                for (const m of messages) {
                    const getResp = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${m.id}?format=full`, {
                        headers: { "Authorization": `Bearer ${token}` }
                    });
                    if (!getResp.ok) continue;
                    const msg = await getResp.json();
                    const atts = extractAttachmentsFromPayload(msg.payload);
                    const headers = msg.payload?.headers || [];
                    let subj = headers.find(h => h.name.toLowerCase() === 'subject')?.value || '';
                    const sender = headers.find(h => h.name.toLowerCase() === 'from')?.value || 'Unknown';
                    const date = headers.find(h => h.name.toLowerCase() === 'date')?.value || '';
                    const snippet = msg.snippet || '';

                    // Filter out non-document images & layout banners
                    const realAtts = atts.filter(a => {
                        const fn = (a.filename || '').toLowerCase();
                        if (fn.startsWith('images/') || fn.startsWith('cid:')) return false;
                        return true;
                    });

                    if (realAtts.length > 0) {
                        if (!subj.trim()) {
                            subj = `(File: ${realAtts[0].filename})`;
                        }

                        const synopsis = await generateEmailSynopsis({
                            id: m.id,
                            sender,
                            subject: subj,
                            snippet,
                            date,
                            attachments: realAtts
                        });
                        foundEmails.push({
                            id: m.id,
                            sender,
                            subject: subj,
                            date,
                            snippet,
                            attachments: realAtts,
                            synopsis
                        });
                        if (foundEmails.length >= 2) break;
                    }
                }

                if (foundEmails.length > 0) {
                    const primary = foundEmails[0];
                    const pSyn = primary.synopsis;
                    const attNames = primary.attachments.map(a => `'${a.filename}' (${a.file_type || 'File'}, ${a.size_human || ''})`).join(', ');

                    let highlightsStr = "";
                    if (pSyn && pSyn.key_points && pSyn.key_points.length > 0) {
                        highlightsStr = "\n\nKey Highlights:\n" + pSyn.key_points.slice(0, 3).map(p => `• ${p}`).join('\n');
                    }

                    let remark = `📎 Here is the summary of your email with attachment:\n\n` +
                        `📧 From: ${primary.sender}\n` +
                        `📋 Subject: ${primary.subject}\n` +
                        `📝 Summary: ${pSyn.tldr || primary.snippet}\n` +
                        `📎 Attached File(s): ${attNames}\n` +
                        `⚡ Action Item: ${pSyn.action_item || 'Review document'} (${pSyn.urgency || 'Normal'} priority)` +
                        highlightsStr;

                    if (foundEmails.length > 1) {
                        const others = foundEmails.slice(1).map(e => `'${e.subject}' from ${e.sender}`).join('; ');
                        remark += `\n\nOther recent emails with attachments: ${others}`;
                    }

                    return {
                        remark,
                        results: foundEmails.map(e => ({
                            id: e.id,
                            sender: e.sender,
                            subject: e.subject,
                            snippet: e.snippet,
                            category: e.synopsis?.category || "Work",
                            action: e.synopsis?.action_item || "Summarized",
                            synopsis: e.synopsis,
                            attachments: e.attachments
                        }))
                    };
                } else {
                    return { remark: "I searched your mailbox for emails with attachments, but no accessible files were found.", results: [] };
                }
            } catch (e) {
                return { remark: `I had an issue summarizing email attachments: ${e.message}`, results: [] };
            }
        }

        // 4. Explicit Purge Intent for Blocked Senders / Past Spam
        const isPurge = [
            "delete all previous", "delete previous", "purge blocked", "clean spam",
            "trash spam", "delete spam", "delete past", "purge spam", "clear spam",
            "blocked sender", "blocked senders"
        ].some(k => pLower.includes(k));

        if (isPurge) {
            try {
                const purgeRes = await purgeBlockedSendersHistory();
                const count = purgeRes.totalPurged;
                const sendersStr = blacklisted.join(", ") || "None configured";
                let remark;
                if (count > 0) {
                    remark = `I searched your entire mailbox and deleted ${count} previous email${count > 1 ? 's' : ''} from blocked senders (${sendersStr}). All past spam has been moved to Trash!`;
                } else {
                    remark = `I checked your entire mailbox for previous emails from blocked senders (${sendersStr}), and found 0. Your mailbox is clean of past spam!`;
                }
                return { remark, results: purgeRes.details };
            } catch (e) {
                return { remark: `I had an issue purging past emails from blocked senders: ${e.message}`, results: [] };
            }
        }

        // 5. Folder Synopsis Intent ("read all mails from folder", "summarize folder", "synopsis")
        const isFolderSynopsis = [
            "summarize folder", "read all mails", "read all emails", "folder synopsis",
            "read folder", "summarize emails", "summarize my folder", "read all messages",
            "synopsis of all", "synopsis of that mail", "mail synopsis", "synopsis"
        ].some(k => pLower.includes(k));

        if (isFolderSynopsis) {
            try {
                const emails = await readFolderEmails({ maxScan: 15 });
                const total = emails.length;
                if (total === 0) {
                    return {
                        remark: "I looked through this folder and didn't find any emails to summarize. Your folder is empty or up to date!",
                        results: []
                    };
                }
                const actionCount = emails.filter(e => e.synopsis && (e.synopsis.urgency === "Urgent" || !e.synopsis.action_item.toLowerCase().includes("no action"))).length;
                const infoCount = total - actionCount;

                const remark = `I've read and analyzed all ${total} emails in this folder! ${actionCount} require your action, and ${infoCount} are informational. Hover your mouse over any email row in Gmail to view its synopsis in a floating text box!`;
                return {
                    remark,
                    results: emails.map(e => ({
                        id: e.id,
                        sender: e.sender,
                        subject: e.subject,
                        snippet: e.snippet,
                        category: e.synopsis?.category || "Work",
                        action: e.synopsis?.action_item || "Summarized",
                        synopsis: e.synopsis
                    }))
                };
            } catch (e) {
                return {
                    remark: `I couldn't read the folder emails via API: ${e.message}. Don't worry, you can still hover over any email directly on the screen to view its synopsis!`,
                    results: []
                };
            }
        }

        // 6. Scan / Triage intent
        const isScan = [
            "scan inbox", "scan my inbox", "scan now", "scan emails", "scan email",
            "scan", "triage inbox", "triage emails", "organize inbox", "categorize emails",
            "clean inbox", "triage my inbox"
        ].some(k => pLower.includes(k)) || (
            pLower.includes("scan") && !pLower.includes("read attachment")
        );

        if (isScan) {
            try {
                const results = await processUnreadEmails({ purgeHistory: true });
                if (results.length === 0) {
                    return {
                        remark: "I scanned your inbox and found 0 unread emails. Everything is clean and up to date!",
                        results: []
                    };
                }
                const historicalPurged = results.filter(r => r.isHistoricalPurge);
                const activeResults = results.filter(r => !r.isHistoricalPurge);
                const intactCount = activeResults.filter(r => r.isIntact).length;
                const triaged = activeResults.filter(r => !r.isIntact);
                const drafts = triaged.filter(r => r.draft).length;
                const trashed = triaged.filter(r => r.category === "Trash").length;
                const categorized = triaged.length - trashed;

                let summaryParts = [];
                if (historicalPurged.length > 0) {
                    summaryParts.push(`Deleted ${historicalPurged.length} previous email${historicalPurged.length > 1 ? 's' : ''} from blocked senders across your mailbox.`);
                }
                if (intactCount > 0) {
                    summaryParts.push(`Kept ${intactCount} newly arrived email${intactCount > 1 ? 's' : ''} intact on top of your inbox for the 1-hour window.`);
                }
                if (triaged.length > 0) {
                    summaryParts.push(`Triaged ${triaged.length} older email${triaged.length > 1 ? 's' : ''}: ${categorized} categorized into labels, ${drafts} draft prepared, ${trashed} spam trashed.`);
                } else if (intactCount > 0 && historicalPurged.length === 0) {
                    summaryParts.push("No older emails required triaging.");
                }
                summaryParts.push("What would you like me to do next?");

                return { remark: summaryParts.join(" "), results: results };
            } catch (e) {
                return { remark: `Error during scan: ${e.message}`, results: [] };
            }
        }

        // 6.5. OmniRoute Gateway Check Intent
        if (pLower.includes("omniroute") || pLower.includes("gateway status") || pLower.includes("check gateway")) {
            const test = await testOmniRouteConnection();
            if (test.ok) {
                return {
                    remark: `🟢 OmniRoute is active and connected!\n• Endpoint: ${test.url}\n• Model: ${test.model}\n• Test response: "${test.reply}"\nYour Gmail assistant is using OmniRoute to route AI requests!`,
                    results: []
                };
            } else {
                return {
                    remark: `⚠️ OmniRoute check:\n${test.message}\n• Tested URL: ${test.url}\nEnsure OmniRoute is started (e.g., run 'omniroute' in your terminal on port 20128). You can also configure its URL in Settings (⚙️ Rules).`,
                    results: []
                };
            }
        }

        // 7. Conversational / General Question via OmniRoute or OpenAI (with robust fallback)
        try {
            const sysPrompt = `You are an animated AI Gmail Assistant living inside the user's Gmail tab.
Your role: Help triage emails, categorize into labels (Work, Finance, Promotions, etc.), create drafts, keep new mail intact for 1 hour, summarize attachments, and delete all previous emails from blocked senders.
Current blocked senders: ${blacklisted.join(", ") || "None configured"}.
Answer the user directly and concisely in 1 to 2 friendly sentences.`;

            const aiRes = await callAiChatCompletion({
                messages: [
                    { role: "system", content: sysPrompt },
                    { role: "user", content: userPrompt }
                ],
                max_tokens: 140,
                temperature: 0.7
            });

            if (aiRes.success && aiRes.content) {
                return { remark: aiRes.content.trim(), results: [] };
            }
        } catch (e) {
            console.warn("[GmailEngine] General query error:", e);
        }

        return {
            remark: "👋 I'm your AI Gmail Assistant (powered by OmniRoute)!\n\n" +
                "• 🌐 'Test omniroute' - verifies connection to local OmniRoute gateway\n" +
                "• 📁 'Sort all mails in different folders named according to senders' - sorts all emails into dedicated sender folders\n" +
                "• 🚫 'Block sender spam@promos.com' - blocks sender & trashes their emails\n" +
                "• 📋 'Who is blocked' - lists currently blocked senders\n" +
                "• ✉️ 'Make a draft reply' - creates a draft reply in Gmail Drafts\n" +
                "• 📎 'Summarize mail with attachment' - summarizes email & attached files\n" +
                "• 🚀 'Scan now' - triages unread emails into category labels & sender folders\n" +
                "• 📑 'Summarize folder' - summarizes all emails in your current view\n" +
                "• 🧹 'Clean spam' - deletes past emails from blocked senders\n\n" +
                "What would you like me to do next?",
            results: []
        };
    }

    return {
        getConfig,
        saveConfig,
        getAccessToken,
        getUnreadCount,
        processUnreadEmails,
        purgeBlockedSendersHistory,
        generateEmailSynopsis,
        readFolderEmails,
        parseSenderInfo,
        sortEmailsBySender,
        blockSender,
        unblockSender,
        listBlockedSenders,
        handleUserPrompt,
        callAiChatCompletion,
        getAiEndpoint,
        testOmniRouteConnection
    };
})();

if (typeof window !== 'undefined') {
    window.GmailEngine = GmailEngine;
}
if (typeof self !== 'undefined') {
    self.GmailEngine = GmailEngine;
}

