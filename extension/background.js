// Background Service Worker for Gmail AI Avatar Assistant
// Runs autonomous alarms in the background without needing any external server

try {
    importScripts('gmail_engine.js');
} catch (e) {
    console.warn("Could not import gmail_engine into service worker:", e);
}

chrome.runtime.onInstalled.addListener(() => {
    console.log("[Gmail Avatar Assistant] Extension installed.");
    // Register alarm to run background triage every 5 minutes
    chrome.alarms.create("gmailAutoTriage", {
        delayInMinutes: 1,
        periodInMinutes: 5
    });
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request && request.type === "GENERATE_SYNOPSIS") {
        if (typeof GmailEngine !== 'undefined') {
            GmailEngine.generateEmailSynopsis(request.emailData)
                .then(synopsis => sendResponse({ success: true, synopsis }))
                .catch(err => sendResponse({ success: false, error: err.message }));
            return true; // Keep message channel open for async response
        } else {
            sendResponse({ success: false, error: "GmailEngine not loaded in background worker" });
        }
    } else if (request && request.type === "READ_FOLDER_EMAILS") {
        if (typeof GmailEngine !== 'undefined') {
            GmailEngine.readFolderEmails(request.options || {})
                .then(emails => sendResponse({ success: true, emails }))
                .catch(err => sendResponse({ success: false, error: err.message }));
            return true;
        } else {
            sendResponse({ success: false, error: "GmailEngine not loaded in background worker" });
        }
    }
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
        if (typeof GmailEngine !== 'undefined') {
            try {
                const cfg = await GmailEngine.getConfig();
                if (cfg && cfg.agent_enabled === false) {
                    console.log("[Gmail Avatar Assistant Background] Agent is deactivated. Skipping background triage.");
                    return;
                }
                console.log("[Gmail Avatar Assistant Background] Alarm triggered. Checking inbox...");
                const results = await GmailEngine.processUnreadEmails();
                if (results.length > 0) {
                    console.log(`[Gmail Avatar Assistant Background] Auto-triaged ${results.length} email(s).`);
                }
            } catch (err) {
                console.warn("[Gmail Avatar Assistant Background] Auto-triage error:", err);
            }
        }
});

