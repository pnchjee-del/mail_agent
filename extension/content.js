// Gmail 3D Avatar Assistant Content Script
// Real-time Folder Mail Reading & Mouseover Synopsis Popover
(function () {
    console.log("%c[Gmail 3D Avatar Assistant] Content script active with Mouseover Synopsis Engine", "color: #38bdf8; font-weight: bold;");

    let popoverEl = null;
    let isMouseInsidePopover = false;
    let currentHoveredRow = null;
    let hoverDebounceTimer = null;
    let hideDebounceTimer = null;
    let lastMousePos = { x: 0, y: 0 };
    const localSynopsisCache = new Map();

    async function isAgentEnabled() {
        return new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.get(['gmail_agent_config'], (result) => {
                    const cfg = result?.gmail_agent_config;
                    if (cfg && cfg.agent_enabled === false) {
                        // Auto-recover so the avatar assistant is always accessible
                        chrome.storage.local.set({ gmail_agent_config: { ...cfg, agent_enabled: true } });
                    }
                    resolve(true);
                });
            } else {
                resolve(true);
            }
        });
    }

    // ==========================================================
    // 1. Injected Floating Synopsis Popover Element
    // ==========================================================
    function getOrCreatePopover() {
        if (popoverEl && document.body.contains(popoverEl)) {
            return popoverEl;
        }

        popoverEl = document.createElement('div');
        popoverEl.id = 'gmail-synopsis-popover';
        popoverEl.innerHTML = `
            <div id="synopsis-popover-inner">
                <div class="synopsis-header">
                    <div class="synopsis-badges">
                        <span id="syn-cat-badge" class="syn-badge syn-badge-cat">WORK</span>
                        <span id="syn-urg-badge" class="syn-badge syn-badge-urgency Normal">NORMAL</span>
                    </div>
                    <span id="syn-date-text" class="synopsis-date">Just now</span>
                </div>
                <div id="syn-subject-text" class="synopsis-subject">Loading email...</div>
                <div id="syn-sender-text" class="synopsis-sender">From: sender@example.com</div>
                <div id="syn-body-container">
                    <div id="syn-tldr-box" class="synopsis-tldr-box">Analyzing email synopsis...</div>
                    <div class="synopsis-points-title">Key Highlights</div>
                    <ul id="syn-points-list" class="synopsis-points-list">
                        <li>Reading email contents...</li>
                    </ul>
                    <div id="syn-action-box" class="synopsis-action-box">
                        <span>⚡</span>
                        <span id="syn-action-text">Reviewing action item...</span>
                    </div>
                </div>
                <div class="synopsis-footer">
                    <span>🤖 AI Synopsis • Gmail Assistant</span>
                    <button id="syn-copy-btn" class="synopsis-copy-btn" title="Copy synopsis to clipboard">📋 Copy</button>
                </div>
            </div>
        `;

        document.body.appendChild(popoverEl);

        // Keep popover visible when user moves mouse into the popover itself
        popoverEl.addEventListener('mouseenter', () => {
            isMouseInsidePopover = true;
            if (hideDebounceTimer) {
                clearTimeout(hideDebounceTimer);
                hideDebounceTimer = null;
            }
        });

        popoverEl.addEventListener('mouseleave', () => {
            isMouseInsidePopover = false;
            hideDebounceTimer = setTimeout(() => {
                hidePopover();
            }, 180);
        });

        // Copy synopsis text button
        const copyBtn = popoverEl.querySelector('#syn-copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tldr = popoverEl.querySelector('#syn-tldr-box')?.innerText || "";
                const action = popoverEl.querySelector('#syn-action-text')?.innerText || "";
                const subject = popoverEl.querySelector('#syn-subject-text')?.innerText || "";
                const textToCopy = `📌 ${subject}\n\n📝 Synopsis: ${tldr}\n⚡ Action: ${action}`;
                navigator.clipboard.writeText(textToCopy).then(() => {
                    copyBtn.innerText = "✓ Copied!";
                    setTimeout(() => { copyBtn.innerText = "📋 Copy"; }, 1800);
                }).catch(() => {});
            });
        }

        return popoverEl;
    }

    function positionPopover(x, y, rowRect) {
        const popover = getOrCreatePopover();
        const popoverWidth = 380;
        const popoverHeight = popover.offsetHeight || 260;

        // Calculate left position (clamp within viewport boundaries)
        let left = x + 16;
        if (left + popoverWidth > window.innerWidth - 20) {
            left = window.innerWidth - popoverWidth - 20;
        }
        if (left < 16) left = 16;

        // Calculate top position: prefer appearing below the row/cursor, or above if near bottom
        let top = y + 18;
        if (top + popoverHeight > window.innerHeight - 15) {
            // Flip above row
            top = (rowRect ? rowRect.top : y) - popoverHeight - 12;
        }
        if (top < 15) top = 15;

        popover.style.left = `${left}px`;
        popover.style.top = `${top}px`;
    }

    function renderLoadingPopover(emailData) {
        const popover = getOrCreatePopover();
        const catBadge = popover.querySelector('#syn-cat-badge');
        const urgBadge = popover.querySelector('#syn-urg-badge');
        const dateText = popover.querySelector('#syn-date-text');
        const subjectText = popover.querySelector('#syn-subject-text');
        const senderText = popover.querySelector('#syn-sender-text');
        const tldrBox = popover.querySelector('#syn-tldr-box');
        const pointsList = popover.querySelector('#syn-points-list');
        const actionBox = popover.querySelector('#syn-action-box');
        const actionText = popover.querySelector('#syn-action-text');

        catBadge.className = 'syn-badge syn-badge-cat';
        catBadge.innerText = 'READING...';
        urgBadge.className = 'syn-badge syn-badge-urgency Normal';
        urgBadge.innerText = 'AI AGENT';

        dateText.innerText = emailData.date || '';
        subjectText.innerText = emailData.subject || 'No Subject';
        senderText.innerText = `From: ${emailData.sender || 'Unknown'}`;

        tldrBox.innerHTML = `
            <div class="synopsis-loading">
                <div class="synopsis-shimmer-line" style="width: 90%;"></div>
                <div class="synopsis-shimmer-line" style="width: 70%;"></div>
            </div>
        `;
        pointsList.innerHTML = `
            <div class="synopsis-loading">
                <div class="synopsis-shimmer-line" style="width: 85%;"></div>
                <div class="synopsis-shimmer-line" style="width: 60%;"></div>
            </div>
        `;
        actionBox.className = 'synopsis-action-box';
        actionText.innerText = 'Reading mail content & synthesizing synopsis...';

        popover.classList.add('visible');
    }

    function renderLoadedPopover(emailData, synopsis) {
        const popover = getOrCreatePopover();
        const catBadge = popover.querySelector('#syn-cat-badge');
        const urgBadge = popover.querySelector('#syn-urg-badge');
        const dateText = popover.querySelector('#syn-date-text');
        const subjectText = popover.querySelector('#syn-subject-text');
        const senderText = popover.querySelector('#syn-sender-text');
        const tldrBox = popover.querySelector('#syn-tldr-box');
        const pointsList = popover.querySelector('#syn-points-list');
        const actionBox = popover.querySelector('#syn-action-box');
        const actionText = popover.querySelector('#syn-action-text');

        const category = synopsis.category || 'Work';
        catBadge.className = `syn-badge syn-badge-cat ${category}`;
        catBadge.innerText = category.toUpperCase();

        const urgency = synopsis.urgency || 'Normal';
        urgBadge.className = `syn-badge syn-badge-urgency ${urgency}`;
        urgBadge.innerText = urgency.toUpperCase();

        dateText.innerText = emailData.date || synopsis.date || '';
        subjectText.innerText = emailData.subject || synopsis.subject || 'No Subject';
        senderText.innerText = `From: ${emailData.sender || synopsis.sender || 'Unknown'}`;

        tldrBox.innerText = synopsis.tldr || 'Synopsis available.';

        // Render bullet points
        const points = Array.isArray(synopsis.key_points) && synopsis.key_points.length > 0
            ? synopsis.key_points
            : [emailData.snippet || 'No detailed points'];
        pointsList.innerHTML = points.map(p => `<li>${escapeHtml(p)}</li>`).join('');

        // Render attachments if present
        let attContainer = popover.querySelector('#syn-attachments-box');
        if (!attContainer) {
            attContainer = document.createElement('div');
            attContainer.id = 'syn-attachments-box';
            attContainer.className = 'synopsis-attachments-box';
            actionBox.parentNode.insertBefore(attContainer, actionBox);
        }
        const atts = synopsis.attachments || emailData.attachments || [];
        if (atts && atts.length > 0) {
            attContainer.style.display = 'block';
            attContainer.innerHTML = `<div class="synopsis-att-title">📎 Attached Documents (${atts.length}):</div>` +
                atts.map(a => `<div class="synopsis-att-item"><span class="syn-badge-pill syn-badge-fin">📄 ${escapeHtml(a.filename || 'File')}</span> <span style="font-size:11px;color:#94a3b8;">(${escapeHtml(a.size_human || a.file_type || '')})</span>${a.summary ? `<div style="font-size:11px;color:#cbd5e1;margin-top:2px;line-height:1.4;">${escapeHtml(a.summary)}</div>` : ''}</div>`).join('');
        } else {
            attContainer.style.display = 'none';
        }

        // Action Item Box
        const action = synopsis.action_item || 'No action needed (Informational)';
        const isNoAction = action.toLowerCase().includes('no action');
        actionBox.className = isNoAction ? 'synopsis-action-box no-action' : 'synopsis-action-box';
        actionBox.querySelector('span:first-child').innerText = isNoAction ? '✅' : '⚡';
        actionText.innerText = action;

        popover.classList.add('visible');
    }

    function hidePopover() {
        if (popoverEl) {
            popoverEl.classList.remove('visible');
        }
        currentHoveredRow = null;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    let lastInteractedRow = null;

    // ==========================================================
    // 2. Email Row Extraction, Open Thread Inspection & Synopsis Fetching
    // ==========================================================
    function extractEmailDataFromRow(row) {
        if (!row) return null;

        // Subject selector in Gmail rows
        const subjectEl = row.querySelector('.bog, .bqe, span[data-thread-id], div.y6 span') || row.querySelector('span[id]');
        let subject = subjectEl?.innerText?.trim() || "";

        // Sender selector in Gmail rows
        const senderEl = row.querySelector('.bA4, .yX, span[name], .bJ4, span[email]') || row.querySelector('span[email]');
        const sender = senderEl?.getAttribute('name') || senderEl?.innerText?.trim() || "Unknown Sender";

        // Snippet preview selector in Gmail rows
        const snippetEl = row.querySelector('.y2') || row.querySelector('span.y2');
        let snippet = snippetEl?.innerText?.trim() || "";
        if (snippet.startsWith('- ')) snippet = snippet.substring(2).trim();

        // Date selector
        const dateEl = row.querySelector('.xW, .by1, td[role="gridcell"]:last-child, span[aria-label*="date"]');
        const date = dateEl?.innerText?.trim() || "";

        // Thread/Message ID
        const threadId = row.getAttribute('data-legacy-thread-id') || row.getAttribute('data-thread-id') || row.id || "";

        // Detect attachments from DOM chips/icons across Gmail variants
        const attachments = [];
        const attChips = row.querySelectorAll('.brd, .a3I, div[role="button"][aria-label*="Attachment"], div[data-tooltip*="attachment"], span[aria-label*="Attachment"], div.Wq, span.bvt, .aZo');
        attChips.forEach(chip => {
            const txt = chip.innerText?.trim() || chip.getAttribute('aria-label') || '';
            if (txt && !txt.toLowerCase().includes('attachment') && txt.length > 2) {
                const cleanName = txt.split('\n')[0].trim();
                if (!attachments.some(a => a.filename === cleanName)) {
                    attachments.push({ filename: cleanName, file_type: 'Attachment' });
                }
            }
        });
        const hasAttachmentIcon = attachments.length > 0 || row.querySelector('span[aria-label*="Attachment"]') !== null || row.querySelector('.brd, .a3I') !== null;

        if (!subject && attachments.length > 0) {
            subject = attachments[0].filename;
        } else if (!subject) {
            subject = "No Subject";
        }

        const cacheKey = (threadId || `${sender}::${subject}`).trim();

        return {
            id: threadId,
            cacheKey,
            sender,
            subject,
            snippet,
            date,
            hasAttachments: hasAttachmentIcon,
            attachments
        };
    }

    // Inspect currently opened email message in thread/reading view
    function getOpenEmailData() {
        const subjectEl = document.querySelector('h2.hP, span.hP, div.ha h2');
        if (!subjectEl || !subjectEl.innerText.trim()) return null;

        let subject = subjectEl.innerText.trim();
        const senderEl = document.querySelector('span.gD, span[email], .gD');
        const sender = senderEl ? (senderEl.getAttribute('email') ? `${senderEl.innerText.trim()} <${senderEl.getAttribute('email')}>` : senderEl.innerText.trim()) : "Unknown Sender";
        const dateEl = document.querySelector('.g3, span[aria-label*="date"]');
        const date = dateEl?.innerText?.trim() || "";

        const bodyEl = document.querySelector('div.a3s.aiL, div.a3s, div[dir="ltr"]');
        const snippet = bodyEl ? bodyEl.innerText.slice(0, 500).trim().replace(/\s+/g, ' ') : "";

        const attachments = [];
        const attElements = document.querySelectorAll('.hq, div.aZo, div[aria-label*="Attachment"], span.a3I, a[aria-label*="Attachment"], div.aSK');
        attElements.forEach(el => {
            const name = el.innerText?.trim() || el.getAttribute('aria-label') || '';
            if (name && !name.toLowerCase().includes('download') && name.length > 2) {
                const cleanName = name.split('\n')[0].trim();
                if (!attachments.some(a => a.filename === cleanName)) {
                    attachments.push({ filename: cleanName, file_type: 'Attachment' });
                }
            }
        });

        const hashMatch = window.location.hash.match(/[#/]([a-zA-Z0-9_-]{10,})/);
        const threadId = hashMatch ? hashMatch[1] : "";

        if (!subject && attachments.length > 0) {
            subject = attachments[0].filename;
        }

        return {
            id: threadId,
            cacheKey: threadId || `${sender}::${subject}`,
            sender,
            subject: subject || "No Subject",
            snippet,
            date,
            hasAttachments: attachments.length > 0,
            attachments,
            source: "open_email"
        };
    }

    // Grab currently selected or focused email from Gmail DOM
    function getSelectedOrActiveEmail() {
        // 1. Check if user checked any checkbox(es) in the email list
        const rows = Array.from(document.querySelectorAll('tr.zA, div[role="row"].zA, tr[role="row"]'));
        const checkedRows = rows.filter(r => {
            const cb = r.querySelector('div[role="checkbox"], input[type="checkbox"]');
            const isChecked = cb && (cb.getAttribute('aria-checked') === 'true' || cb.checked);
            const isSelected = r.classList.contains('x7') || r.classList.contains('selected') || r.getAttribute('aria-selected') === 'true';
            return isChecked || isSelected;
        });

        if (checkedRows.length > 0) {
            const rowWithAtt = checkedRows.find(r => r.querySelector('.brd, .a3I, span[aria-label*="Attachment"], div[aria-label*="Attachment"], div.Wq, span.bvt, .aZo'));
            const targetRow = rowWithAtt || checkedRows[0];
            const data = extractEmailDataFromRow(targetRow);
            if (data) {
                data.source = "checked_row";
                data.domRow = targetRow;
                return data;
            }
        }

        // 2. Check if an email is currently opened on screen in reading view
        const openEmail = getOpenEmailData();
        if (openEmail) {
            return openEmail;
        }

        // 3. Check if user clicked on a row
        if (lastInteractedRow && document.body.contains(lastInteractedRow)) {
            const data = extractEmailDataFromRow(lastInteractedRow);
            if (data) {
                data.source = "clicked_row";
                data.domRow = lastInteractedRow;
                return data;
            }
        }

        // 4. Check if currently hovered over a row
        if (currentHoveredRow && document.body.contains(currentHoveredRow)) {
            const data = extractEmailDataFromRow(currentHoveredRow);
            if (data) {
                data.source = "hovered_row";
                data.domRow = currentHoveredRow;
                return data;
            }
        }

        return null;
    }

    async function fetchSynopsis(emailData) {
        const key = emailData.cacheKey;
        if (localSynopsisCache.has(key)) {
            return localSynopsisCache.get(key);
        }

        // Try direct call via window.GmailEngine
        if (typeof GmailEngine !== 'undefined' && GmailEngine.generateEmailSynopsis) {
            try {
                const synopsis = await GmailEngine.generateEmailSynopsis(emailData);
                if (synopsis) {
                    localSynopsisCache.set(key, synopsis);
                    return synopsis;
                }
            } catch (err) {
                console.warn("[Gmail 3D Avatar Assistant] Direct synopsis error:", err);
            }
        }

        // Fallback: Send message to background service worker
        return new Promise((resolve) => {
            if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({ type: "GENERATE_SYNOPSIS", emailData }, (resp) => {
                    if (resp && resp.success && resp.synopsis) {
                        localSynopsisCache.set(key, resp.synopsis);
                        resolve(resp.synopsis);
                    } else {
                        // Heuristic fallback inside content script
                        const fb = createInstantFallbackSynopsis(emailData);
                        localSynopsisCache.set(key, fb);
                        resolve(fb);
                    }
                });
            } else {
                const fb = createInstantFallbackSynopsis(emailData);
                localSynopsisCache.set(key, fb);
                resolve(fb);
            }
        });
    }

    function createInstantFallbackSynopsis(data) {
        const text = `${data.subject} ${data.snippet}`.toLowerCase();
        let urgency = "Normal";
        if (text.includes("urgent") || text.includes("asap") || text.includes("deadline") || text.includes("action required") || text.includes("immediate")) {
            urgency = "Urgent";
        } else if (text.includes("newsletter") || text.includes("digest") || text.includes("promo") || text.includes("sale") || text.includes("discount")) {
            urgency = "Low";
        }

        let action = "No action needed (Informational)";
        if (text.includes("review") || text.includes("attached") || text.includes("feedback")) {
            action = "Review requested by sender";
        } else if (text.includes("reply") || text.includes("respond") || text.includes("confirm") || text.includes("let me know")) {
            action = "Response required from you";
        } else if (text.includes("invoice") || text.includes("payment") || text.includes("bill") || text.includes("due date")) {
            action = "Payment / invoice review required";
        }

        let category = "Work";
        if (text.includes("invoice") || text.includes("receipt") || text.includes("bank") || text.includes("billing") || text.includes("$")) {
            category = "Finance";
        } else if (text.includes("discount") || text.includes("promo") || text.includes("offer") || text.includes("deal")) {
            category = "Promotions";
        } else if (text.includes("ticket") || text.includes("support") || text.includes("helpdesk")) {
            category = "Support";
        } else if (text.includes("family") || text.includes("friend") || text.includes("personal")) {
            category = "Personal";
        }

        const cleanSnippet = (data.snippet || "No preview text available.").trim().replace(/\s+/g, ' ');
        const sentences = cleanSnippet.split(/(?<=[.?!])\s+/).filter(s => s.trim().length > 6);
        let tldr = sentences.slice(0, 2).join(' ') || `${data.subject} from ${data.sender}`;
        const points = sentences.slice(1, 4);
        if (points.length === 0) points.push(cleanSnippet.slice(0, 120));

        if (data.attachments && data.attachments.length > 0) {
            const attNames = data.attachments.map(a => a.filename).join(', ');
            if (!cleanSnippet || cleanSnippet.length < 15) {
                tldr = `Attached document(s): [${attNames}] in message from ${data.sender}.`;
            } else {
                tldr += ` [Attached: ${attNames}]`;
            }
            points.push(`Attached Documents: ${attNames}`);
            if (action.includes("No action")) {
                action = `Review attached document(s): ${attNames}`;
            }
        }

        return {
            id: data.id,
            sender: data.sender,
            subject: data.subject,
            date: data.date,
            tldr,
            key_points: points,
            action_item: action,
            urgency,
            category,
            attachments: data.attachments || []
        };
    }

    // ==========================================================
    // 3. Email Rows Mouseover Hook
    // ==========================================================
    function setupEmailRowHoverListeners() {
        // Match Gmail's email rows across modern & legacy web clients
        const rows = document.querySelectorAll('tr.zA, div[role="row"].zA, tr[role="row"]');

        rows.forEach(row => {
            if (row.dataset.synopsisAttached === "true") return;
            row.dataset.synopsisAttached = "true";

            // Track mouse position over row
            row.addEventListener('mousemove', (e) => {
                lastMousePos.x = e.clientX;
                lastMousePos.y = e.clientY;
            });

            // Track user interaction/click on row
            row.addEventListener('click', () => {
                lastInteractedRow = row;
            });

            // Mouse enter row
            row.addEventListener('mouseenter', (e) => {
                lastMousePos.x = e.clientX;
                lastMousePos.y = e.clientY;
                currentHoveredRow = row;

                if (hideDebounceTimer) {
                    clearTimeout(hideDebounceTimer);
                    hideDebounceTimer = null;
                }

                // Debounce hover to prevent flickering while rapidly scrolling past rows
                if (hoverDebounceTimer) clearTimeout(hoverDebounceTimer);
                hoverDebounceTimer = setTimeout(async () => {
                    if (currentHoveredRow !== row) return;

                    const emailData = extractEmailDataFromRow(row);
                    if (!emailData || (!emailData.subject && !emailData.sender)) return;

                    const rowRect = row.getBoundingClientRect();
                    positionPopover(lastMousePos.x, lastMousePos.y, rowRect);

                    // Check if already cached
                    const key = emailData.cacheKey;
                    if (localSynopsisCache.has(key)) {
                        renderLoadedPopover(emailData, localSynopsisCache.get(key));
                        return;
                    }

                    // Otherwise show sleek loading shimmer and fetch
                    renderLoadingPopover(emailData);

                    try {
                        const synopsis = await fetchSynopsis(emailData);
                        // Make sure user is still hovering this row or popover
                        if (currentHoveredRow === row || isMouseInsidePopover) {
                            renderLoadedPopover(emailData, synopsis);
                            positionPopover(lastMousePos.x, lastMousePos.y, rowRect);
                            attachRowBadge(row);
                        }
                    } catch (err) {
                        console.warn("[Gmail 3D Avatar Assistant] Hover synopsis failed:", err);
                    }
                }, 180);
            });

            // Mouse leave row
            row.addEventListener('mouseleave', () => {
                if (hoverDebounceTimer) {
                    clearTimeout(hoverDebounceTimer);
                    hoverDebounceTimer = null;
                }

                hideDebounceTimer = setTimeout(() => {
                    if (!isMouseInsidePopover) {
                        hidePopover();
                    }
                }, 160);
            });
        });
    }

    function attachRowBadge(row) {
        if (!row || row.querySelector('.gmail-synopsis-row-badge')) return;
        const target = row.querySelector('.bog, .bqe, span[data-thread-id]') || row.querySelector('.yX');
        if (target) {
            const badge = document.createElement('span');
            badge.className = 'gmail-synopsis-row-badge';
            badge.innerText = '📑';
            badge.title = 'AI Synopsis Ready (Hover mouse to view)';
            target.parentElement.insertBefore(badge, target);
        }
    }

    // ==========================================================
    // 4. Read & Summarize All Emails in Active Folder
    // ==========================================================
    async function summarizeAllFolderEmails() {
        const rows = Array.from(document.querySelectorAll('tr.zA, div[role="row"].zA, tr[role="row"]'));
        if (rows.length === 0) {
            console.log("[Gmail 3D Avatar Assistant] No email rows found to summarize in current folder.");
            notifyAvatar("I looked for emails in this folder, but couldn't find any visible messages.");
            return;
        }

        const toolbarBtn = document.getElementById('gmail-read-folder-btn');
        if (toolbarBtn) {
            toolbarBtn.disabled = true;
            toolbarBtn.innerHTML = `⏳ Reading ${rows.length} mails...`;
        }

        notifyAvatar(`Reading all ${rows.length} emails in this folder... Preparing synopses!`);

        let processed = 0;
        let actionCount = 0;
        let infoCount = 0;

        // Process visible rows with parallel batching
        const batchSize = 4;
        for (let i = 0; i < rows.length; i += batchSize) {
            const batch = rows.slice(i, i + batchSize);
            await Promise.all(batch.map(async (row) => {
                const data = extractEmailDataFromRow(row);
                if (data) {
                    try {
                        const synopsis = await fetchSynopsis(data);
                        attachRowBadge(row);
                        processed++;
                        if (synopsis.urgency === "Urgent" || !synopsis.action_item.toLowerCase().includes("no action")) {
                            actionCount++;
                        } else {
                            infoCount++;
                        }
                    } catch (e) {
                        console.warn("[Gmail 3D Avatar Assistant] Error reading folder email:", e);
                    }
                }
            }));
            if (toolbarBtn) {
                toolbarBtn.innerHTML = `⏳ Summarized ${processed}/${rows.length}...`;
            }
        }

        if (toolbarBtn) {
            toolbarBtn.disabled = false;
            toolbarBtn.innerHTML = `✓ ${processed} Mails Summarized`;
            setTimeout(() => {
                toolbarBtn.innerHTML = `📑 Read Folder Synopsis (${processed})`;
            }, 3000);
        }

        const speechRemark = `I've read and analyzed all ${processed} emails in this folder! ${actionCount} require your action, and ${infoCount} are informational. Hover your mouse over any email row to view its synopsis in a floating text box!`;
        notifyAvatar(speechRemark);
        console.log(`%c[Gmail 3D Avatar Assistant] Folder synopsis complete: ${processed} emails indexed.`, "color: #22c55e; font-weight: bold;");
    }

    function notifyAvatar(text) {
        const iframe = document.getElementById('gmail-avatar-frame');
        if (iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage({
                type: "AVATAR_SET_REMARK",
                remark: text
            }, "*");
        }
    }

    // ==========================================================
    // 5. Injected Toolbar Action Buttons in Gmail
    // ==========================================================
    function toggleAvatarWidget() {
        let root = document.getElementById('gmail-avatar-widget-root');
        if (!root) {
            injectWidget();
            return;
        }

        const win = root.querySelector('#gmail-avatar-window');
        const lch = root.querySelector('#gmail-avatar-launcher');
        if (!win || !lch) return;

        const isWinVisible = win.style.display !== 'none';
        if (isWinVisible) {
            win.style.setProperty('display', 'none', 'important');
            lch.style.setProperty('display', 'flex', 'important');
        } else {
            lch.style.setProperty('display', 'none', 'important');
            win.style.setProperty('display', 'flex', 'important');
            win.style.transition = 'transform 0.2s ease';
            win.style.transform = 'scale(1.02)';
            setTimeout(() => { win.style.transform = 'scale(1)'; }, 200);
        }
    }

    function injectFolderToolbarButton() {
        if (document.getElementById('gmail-assistant-toolbar-actions')) return;

        // Look for Gmail's action toolbars across modern and legacy Gmail interfaces
        const toolbars = [
            document.querySelector('div.G-atb:not([style*="display: none"])'),
            document.querySelector('div[gh="tm"]'),
            document.querySelector('div.G-tF'),
            document.querySelector('div[role="toolbar"]'),
            document.querySelector('.nH.aqK')
        ];

        const targetToolbar = toolbars.find(t => t && t.offsetParent !== null);
        if (!targetToolbar) return;

        const container = document.createElement('div');
        container.id = 'gmail-assistant-toolbar-actions';
        container.style.display = 'inline-flex';
        container.style.alignItems = 'center';
        container.style.gap = '8px';
        container.style.marginLeft = '10px';
        container.style.verticalAlign = 'middle';

        // 1. Avatar Toggle Button
        const avatarBtn = document.createElement('button');
        avatarBtn.id = 'gmail-toggle-avatar-btn';
        avatarBtn.className = 'gmail-synopsis-toolbar-btn';
        avatarBtn.innerHTML = `<span>🤖</span><span>AI Avatar</span>`;
        avatarBtn.title = "Show or hide 3D Avatar Assistant";

        avatarBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleAvatarWidget();
        });

        // 2. Read Folder Synopsis Button
        const synBtn = document.createElement('button');
        synBtn.id = 'gmail-read-folder-btn';
        synBtn.className = 'gmail-synopsis-toolbar-btn';
        synBtn.innerHTML = `<span>📑</span><span>Read Folder Synopsis</span>`;
        synBtn.title = "Read all emails in this folder and enable mouseover synopsis text boxes";

        synBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            summarizeAllFolderEmails();
        });

        container.appendChild(avatarBtn);
        container.appendChild(synBtn);
        targetToolbar.appendChild(container);
        console.log("[Gmail 3D Avatar Assistant] Toolbar actions successfully injected into Gmail!");
    }

    // ==========================================================
    // 6. 3D Avatar Widget Injection
    // ==========================================================
    async function injectWidget() {
        const enabled = await isAgentEnabled();
        let existingRoot = document.getElementById('gmail-avatar-widget-root');

        if (!document.body) {
            setTimeout(injectWidget, 300);
            return;
        }

        // If existing root is present, ensure it is attached and visible
        if (existingRoot) {
            if (!document.body.contains(existingRoot)) {
                document.body.appendChild(existingRoot);
            }
            const win = existingRoot.querySelector('#gmail-avatar-window');
            const lch = existingRoot.querySelector('#gmail-avatar-launcher');
            if (win && lch) {
                const winHidden = win.style.display === 'none';
                const lchHidden = lch.style.display === 'none';
                if (winHidden && lchHidden) {
                    win.style.setProperty('display', 'flex', 'important');
                }
            }
            return;
        }

        try {
            const root = document.createElement('div');
            root.id = 'gmail-avatar-widget-root';
            root.setAttribute('style', [
                'position: fixed !important',
                'bottom: 24px !important',
                'right: 24px !important',
                'z-index: 2147483647 !important',
                'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important',
                'display: flex !important',
                'flex-direction: column !important',
                'align-items: flex-end !important',
                'user-select: none !important',
                'pointer-events: auto !important'
            ].join('; '));

            // Minimized Floating Launcher Pill
            const launcher = document.createElement('div');
            launcher.id = 'gmail-avatar-launcher';
            launcher.setAttribute('style', [
                'display: none !important',
                'align-items: center !important',
                'gap: 10px !important',
                'background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%) !important',
                'color: #38bdf8 !important',
                'border: 1px solid rgba(56, 189, 248, 0.5) !important',
                'box-shadow: 0 10px 30px rgba(0, 0, 0, 0.55) !important',
                'padding: 10px 18px !important',
                'border-radius: 30px !important',
                'cursor: pointer !important',
                'font-size: 13.5px !important',
                'font-weight: 600 !important',
                'transition: transform 0.2s ease !important'
            ].join('; '));
            launcher.innerHTML = `
                <span style="width: 9px; height: 9px; border-radius: 50%; background: #22c55e; display: inline-block; box-shadow: 0 0 10px #22c55e;"></span>
                <span>🤖 AI Avatar Assistant</span>
            `;

            // Main Floating Window
            const windowEl = document.createElement('div');
            windowEl.id = 'gmail-avatar-window';
            windowEl.setAttribute('style', [
                'display: flex !important',
                'flex-direction: column !important',
                'width: 380px !important',
                'height: 570px !important',
                'background: #0f172a !important',
                'border: 1px solid rgba(56, 189, 248, 0.45) !important',
                'border-radius: 18px !important',
                'box-shadow: 0 20px 55px rgba(0, 0, 0, 0.7) !important',
                'overflow: hidden !important'
            ].join('; '));

            // Header with minimize and close controls
            const header = document.createElement('div');
            header.id = 'gmail-avatar-header';
            header.setAttribute('style', [
                'display: flex !important',
                'justify-content: space-between !important',
                'align-items: center !important',
                'padding: 10px 16px !important',
                'background: rgba(15, 23, 42, 0.98) !important',
                'border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important',
                'color: #f8fafc !important',
                'font-size: 13px !important',
                'font-weight: 600 !important',
                'cursor: move !important'
            ].join('; '));
            header.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="width: 8px; height: 8px; border-radius: 50%; background: #22c55e; display: inline-block; box-shadow: 0 0 8px #22c55e;"></span>
                    <span>Gmail Avatar Assistant</span>
                </div>
                <div style="display: flex; gap: 6px;">
                    <button id="avatar-min-btn" style="background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12); color: #cbd5e1; cursor: pointer; font-size: 13px; padding: 2px 9px; border-radius: 6px;" title="Minimize to launcher pill">─</button>
                    <button id="avatar-close-btn" style="background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #f87171; cursor: pointer; font-size: 13px; padding: 2px 9px; border-radius: 6px;" title="Minimize">✕</button>
                </div>
            `;

            // Iframe pointing to extension avatar.html
            const iframe = document.createElement('iframe');
            iframe.id = 'gmail-avatar-frame';
            iframe.src = chrome.runtime.getURL('avatar.html');
            iframe.setAttribute('style', [
                'width: 100% !important',
                'height: 520px !important',
                'flex: 1 !important',
                'border: none !important',
                'background: transparent !important'
            ].join('; '));

            windowEl.appendChild(header);
            windowEl.appendChild(iframe);
            root.appendChild(launcher);
            root.appendChild(windowEl);
            document.body.appendChild(root);

            // Toggle Minimize / Expand
            const minBtn = header.querySelector('#avatar-min-btn');
            minBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                windowEl.style.setProperty('display', 'none', 'important');
                launcher.style.setProperty('display', 'flex', 'important');
            });

            // Close Button minimizes to pill
            const closeBtn = header.querySelector('#avatar-close-btn');
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                windowEl.style.setProperty('display', 'none', 'important');
                launcher.style.setProperty('display', 'flex', 'important');
            });

            launcher.addEventListener('click', () => {
                launcher.style.setProperty('display', 'none', 'important');
                windowEl.style.setProperty('display', 'flex', 'important');
            });

            // Draggable window support
            let isDragging = false;
            let dragStartX = 0;
            let dragStartY = 0;
            let rootStartRight = 24;
            let rootStartBottom = 24;

            header.addEventListener('mousedown', (e) => {
                if (e.target.tagName === 'BUTTON') return;
                isDragging = true;
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                const rect = root.getBoundingClientRect();
                rootStartRight = window.innerWidth - rect.right;
                rootStartBottom = window.innerHeight - rect.bottom;
                header.style.cursor = 'grabbing';
                e.preventDefault();
            });

            window.addEventListener('mousemove', (e) => {
                if (!isDragging) return;
                const dx = e.clientX - dragStartX;
                const dy = e.clientY - dragStartY;
                const newRight = Math.max(8, rootStartRight - dx);
                const newBottom = Math.max(8, rootStartBottom - dy);
                root.style.setProperty('right', `${newRight}px`, 'important');
                root.style.setProperty('bottom', `${newBottom}px`, 'important');
            });

            window.addEventListener('mouseup', () => {
                if (isDragging) {
                    isDragging = false;
                    header.style.cursor = 'move';
                }
            });

            console.log("%c[Gmail 3D Avatar Assistant] Widget successfully mounted into Gmail!", "color: #22c55e; font-weight: bold;");
        } catch (err) {
            console.error("[Gmail 3D Avatar Assistant] Error mounting widget:", err);
        }
    }

    // ==========================================================
    // 7. Message Channel & Context-Aware Prompt Resolver
    // ==========================================================
    async function handleAvatarPromptWithDomContext(promptText) {
        const lower = (promptText || '').toLowerCase().trim();

        // 1. Folder synopsis intent
        const isFolderScanPrompt = (lower.includes("folder") || lower.includes("all mails") || lower.includes("all emails") || lower.includes("read all") || (lower.includes("summarize") && !lower.includes("attachment") && !lower.includes("attached") && !lower.includes("mail with") && !lower.includes("email with") && !lower.includes("draft") && !lower.includes("reply") && !lower.includes("selected")));
        if (isFolderScanPrompt) {
            summarizeAllFolderEmails();
            return;
        }

        // 2. Check if user is asking to summarize email attachments
        const isAttIntent = lower.includes("attachment") || lower.includes("attached") || lower.includes("document");
        // 3. Check if user wants a draft reply
        const isDraftIntent = lower.includes("draft") || lower.includes("reply");

        const selected = getSelectedOrActiveEmail();

        if (isAttIntent) {
            if (selected) {
                // Highlighting the selected row so the user visually sees what was picked!
                if (selected.domRow) {
                    try {
                        selected.domRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        selected.domRow.style.outline = '2px solid #38bdf8';
                        selected.domRow.style.boxShadow = '0 0 16px rgba(56, 189, 248, 0.5)';
                        setTimeout(() => {
                            if (selected.domRow) {
                                selected.domRow.style.outline = '';
                                selected.domRow.style.boxShadow = '';
                            }
                        }, 5000);
                    } catch (e) {}
                }

                notifyAvatar(`Inspecting attachments in selected email: "${selected.subject}" from ${selected.sender}...`);

                let synopsis = null;
                try {
                    synopsis = await fetchSynopsis(selected);
                } catch (e) {
                    synopsis = createInstantFallbackSynopsis(selected);
                }

                const attList = (synopsis.attachments && synopsis.attachments.length > 0)
                    ? synopsis.attachments
                    : (selected.attachments || []);
                const attNames = attList.length > 0
                    ? attList.map(a => `'${a.filename}'`).join(', ')
                    : "Attached document";

                const cleanSubj = selected.subject !== "No Subject" ? selected.subject : (attList[0]?.filename ? `(File: ${attList[0].filename})` : "No Subject");

                let kpLines = "";
                if (synopsis.key_points && synopsis.key_points.length > 0) {
                    kpLines = "\n\nKey Highlights:\n" + synopsis.key_points.slice(0, 3).map(p => `• ${p}`).join('\n');
                }

                let attBoxes = "";
                if (attList.length > 0) {
                    attBoxes = "\n📎 Attached Document(s): " + attNames;
                }

                const remark = `📎 Here is the summary of your selected email with attachments:\n\n` +
                    `📧 From: ${selected.sender}\n` +
                    `📋 Subject: ${cleanSubj}\n` +
                    `📝 Summary: ${synopsis.tldr || selected.snippet}` +
                    attBoxes +
                    `\n⚡ Action Item: ${synopsis.action_item} (${synopsis.urgency} priority)` +
                    kpLines;

                notifyAvatar(remark);
                return;
            } else {
                // No email is checked or opened yet: scan the current view for rows with attachments
                const rows = Array.from(document.querySelectorAll('tr.zA, div[role="row"].zA'));
                const rowsWithAtt = rows.filter(r => r.querySelector('.brd, .a3I, span[aria-label*="Attachment"], div[aria-label*="Attachment"], div.Wq, span.bvt, .aZo'));

                if (rowsWithAtt.length > 0) {
                    const firstAttRow = rowsWithAtt[0];
                    const data = extractEmailDataFromRow(firstAttRow);
                    if (data) {
                        try {
                            firstAttRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                            firstAttRow.style.outline = '2px solid #38bdf8';
                            setTimeout(() => { if (firstAttRow) firstAttRow.style.outline = ''; }, 4000);
                        } catch (e) {}

                        const synopsis = await fetchSynopsis(data);
                        const cleanSubj = data.subject !== "No Subject" ? data.subject : (data.attachments[0]?.filename ? `(File: ${data.attachments[0].filename})` : "No Subject");
                        const attNames = (data.attachments && data.attachments.length > 0)
                            ? data.attachments.map(a => `'${a.filename}'`).join(', ')
                            : "Attached document";

                        const remark = `📎 You didn't select an email, so I summarized the latest email with attachments in this folder:\n\n` +
                            `📧 From: ${data.sender}\n` +
                            `📋 Subject: ${cleanSubj}\n` +
                            `📝 Summary: ${synopsis.tldr || data.snippet}\n` +
                            `📎 Attached Document(s): ${attNames}\n` +
                            `⚡ Action Item: ${synopsis.action_item} (${synopsis.urgency} priority)\n\n` +
                            `💡 Tip: Check the checkbox ☑️ next to any specific email to summarize that exact one!`;

                        notifyAvatar(remark);
                        return;
                    }
                }
            }
        }

        if (isDraftIntent && selected) {
            notifyAvatar(`Preparing a draft reply to selected email from ${selected.sender}...`);
            try {
                if (typeof GmailEngine !== 'undefined' && GmailEngine.handleUserPrompt) {
                    const result = await GmailEngine.handleUserPrompt(`draft reply to ${selected.sender} regarding ${selected.subject}`);
                    notifyAvatar(result.remark || "Draft created in Gmail Drafts!");
                    return;
                }
            } catch (e) {}
        }

        // Fallback: Let GmailEngine handle it
        try {
            if (typeof GmailEngine !== 'undefined' && GmailEngine.handleUserPrompt) {
                const res = await GmailEngine.handleUserPrompt(promptText);
                notifyAvatar(res.remark || "Done!");
            }
        } catch (err) {
            const msg = (err && err.message) ? err.message : String(err);
            if (msg.includes('Extension context invalidated')) {
                notifyAvatar('🔄 The extension was reloaded or updated. Please refresh this Gmail tab (F5) to reconnect!');
            } else {
                notifyAvatar(`I encountered an issue: ${msg}`);
            }
        }
    }

    window.addEventListener('message', async (e) => {
        if (!e.data) return;
        if (e.data.type === "TRIGGER_FOLDER_SYNOPSIS") {
            summarizeAllFolderEmails();
        } else if (e.data.type === "RESOLVE_PROMPT_WITH_DOM") {
            handleAvatarPromptWithDomContext(e.data.promptText);
        }
    });

    // ==========================================================
    // 8. Lifecycle & Continuous Inspection
    // ==========================================================
    function runScanCycles() {
        if (typeof chrome === 'undefined' || !chrome.runtime || !chrome.runtime.id) {
            return;
        }
        injectWidget();
        injectFolderToolbarButton();
        setupEmailRowHoverListeners();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            runScanCycles();
        });
    } else {
        runScanCycles();
    }

    // Continuously check when user navigates between folders/labels in Gmail SPA
    setInterval(runScanCycles, 1500);

})();
