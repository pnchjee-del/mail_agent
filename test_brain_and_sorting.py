"""
Comprehensive Verification Test for AI Agent Brain, Sender-Wise Sorting, and Sender Blocking.
"""
import os
import json
from agent_brain import AgentBrain
from gmail_agent import GmailAIAgent

def test_brain_intents():
    print("==================================================")
    print("TEST 1: Testing Cognitive Brain Intent Classifications")
    print("==================================================")
    brain = AgentBrain()

    test_cases = [
        ("please make this agent to sort mails sender wise, like all mails from indusind shall be put in a folder indusind and similar", "SORT_BY_SENDER"),
        ("all mails from indusind shall be put in a folder indusind and similar", "SORT_BY_SENDER"),
        ("put all mails from indusind in a folder indusind", "SORT_BY_SENDER"),
        ("sort mails from indusind", "SORT_BY_SENDER"),
        ("I need to sort my mails sender wise", "SORT_BY_SENDER"),
        ("sort my mails sender wise", "SORT_BY_SENDER"),
        ("please group all my emails by sender", "SORT_BY_SENDER"),
        ("organize inbox sender-wise", "SORT_BY_SENDER"),
        ("I want this agent to put all mails from a particular sender in a folder named after the sender", "SORT_BY_SENDER"),
        ("put all mails from client@example.com in a folder named after the sender", "SORT_BY_SENDER"),
        ("put all mails from boss@company.com into a folder named after the sender", "SORT_BY_SENDER"),
        ("put all mails from \"Amazon\" in a folder named after the sender", "SORT_BY_SENDER"),
        ("block sender malicious@phishing.com", "BLOCK_SENDER"),
        ("block badactor@xyz.com", "BLOCK_SENDER"),
        ("block this sender", "BLOCK_SENDER"),
        ("who is blocked", "LIST_BLOCKED"),
        ("show blocked senders", "LIST_BLOCKED"),
        ("unblock client@example.com", "UNBLOCK_SENDER"),
        ("how many unread emails do I have?", "COUNT_UNREAD"),
        ("make a draft reply to the latest mail", "DRAFT_REPLY"),
        ("summarize mail with attachment", "SUMMARIZE_ATTACHMENTS"),
        ("scan my inbox", "SCAN_INBOX")
    ]

    all_passed = True
    for prompt, expected_intent in test_cases:
        res = brain.think(prompt)
        intent = res.get("intent")
        status = "✅ PASS" if intent == expected_intent else f"❌ FAIL (Got {intent})"
        if intent != expected_intent:
            all_passed = False
        print(f"[{status}] \"{prompt}\" -> {intent} (params: {res.get('parameters')})")

    assert all_passed, "Some brain intent tests failed!"
    print("\n✅ All Brain Intent Classifications Passed Successfully!\n")

def test_agent_block_and_unblock():
    print("==================================================")
    print("TEST 2: Testing Agent Sender Blocking & Persistence")
    print("==================================================")
    agent = GmailAIAgent()

    test_sender = "test_spammer_123@blockme.com"

    # Ensure clean slate for test sender
    if test_sender in agent.delete_senders:
        agent.delete_senders.remove(test_sender)
        agent._persist_delete_senders()

    # Block sender via natural prompt
    prompt = f"block sender {test_sender}"
    remark, details = agent.handle_user_prompt(prompt)
    print(f"Block Prompt Output:\n{remark}\n")
    assert test_sender in agent.delete_senders, "Sender was not added to agent.delete_senders!"

    # Verify persisted in config.json
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    assert test_sender in cfg.get("delete_senders", []), "Sender was not persisted to config.json!"
    print(f"✅ Verified '{test_sender}' in config.json delete_senders.")

    # Test listing blocked
    rem_list, _ = agent.handle_user_prompt("who is blocked")
    assert test_sender in rem_list, f"Sender '{test_sender}' not found in list output: {rem_list}"
    print(f"✅ Verified '{test_sender}' in list blocked senders.")

    # Test unblocking
    rem_unblock, _ = agent.handle_user_prompt(f"unblock {test_sender}")
    assert test_sender not in agent.delete_senders, "Sender was not removed from agent.delete_senders!"
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    assert test_sender not in cfg.get("delete_senders", []), "Sender was not removed from config.json!"
    print(f"✅ Verified unblock and removal from config.json: {rem_unblock}\n")

def test_indusind_and_similar_sender_parsing():
    print("==================================================")
    print("TEST 3: Testing IndusInd & Similar Sender Folder Parsing")
    print("==================================================")
    agent = GmailAIAgent()

    indusind_cases = [
        ('"IndusInd Bank Ltd." <creditcards@indusind.com>', 'indusind'),
        ('"IndusInd Bank Alerts" <alerts@indusind.com>', 'indusind'),
        ('"IndusInd Bank" <reachus@indusind.com>', 'indusind'),
        ('"IndusInd NetBanking" <donotreply@netbanking.indusind.com>', 'indusind'),
        ('<statements@indusind.co.in>', 'indusind'),
        ('"creditcards@indusind.com" <creditcards@indusind.com>', 'indusind'),
        ('"IndusInd Bank" <statements@billdesk.com>', 'indusind'),
        ('"no-reply@indusind.com"', 'indusind'),
        ('"INDUSIND BANK" <statements@indusind.com>', 'indusind'),
    ]

    for header, expected_folder in indusind_cases:
        info = agent.parse_sender_info(header)
        folder = info["label_name"]
        print(f"[IndusInd Check] '{header}' -> folder '{folder}' (slug: {info['folder_slug']})")
        assert folder == expected_folder, f"Expected '{expected_folder}', but got '{folder}' for header '{header}'"

    print("✅ All IndusInd variations correctly mapped to folder 'indusind'!\n")

    similar_cases = [
        ('"HDFC Bank InstaAlerts" <alerts@hdfcbank.net>', 'hdfcbank'),
        ('"team_cdc.cppc@alerts.sbi.co.in"', 'sbi'),
        ('"SBI Alerts" <alerts@sbi.co.in>', 'sbi'),
        ('"Amazon.in" <shipment-tracking@amazon.in>', 'amazon'),
        ('"Google Security Alert" <no-reply@accounts.google.com>', 'google'),
        ('"Flipkart" <newsletter@flipkart.com>', 'flipkart'),
        ('"Swiggy" <order@swiggy.in>', 'swiggy'),
        ('"Zomato" <noreply@mailers.zomato.com>', 'zomato'),
        ('"Netflix" <info@mailer.netflix.com>', 'netflix'),
        ('"GitHub" <notifications@github.com>', 'github'),
        ('"P N Chatterjee" <pnchjee@gmail.com>', 'P N Chatterjee')
    ]

    for header, expected_folder in similar_cases:
        info = agent.parse_sender_info(header)
        folder = info["label_name"]
        print(f"[Similar Check] '{header}' -> folder '{folder}' (slug: {info['folder_slug']})")
        assert folder.lower() == expected_folder.lower(), f"Expected '{expected_folder}', but got '{folder}' for header '{header}'"

    print("✅ All similar corporate & personal senders correctly organized into folders!\n")

def test_agent_sort_sender_routing():
    print("==================================================")
    print("TEST 4: Testing Agent Sender-Wise Sorting Routing")
    print("==================================================")
    agent = GmailAIAgent()

    # Test the user's exact prompt:
    user_prompt = "please make this agent to sort mails sender wise, like all mails from indusind shall be put in a folder indusind and similar"
    remark, details = agent.handle_user_prompt(user_prompt)
    print(f"Prompt: \"{user_prompt}\"")
    print(f"Avatar Remark Output: {remark}")

    assert "What would you like me to do next?" not in remark or "sorted" in remark.lower(), "Fell through to generic fallback!"
    print("\n✅ User's prompt 'please make this agent to sort mails sender wise, like all mails from indusind shall be put in a folder indusind and similar' was understood and routed successfully!\n")

def test_particular_sender_prompt_handling():
    print("==================================================")
    print("TEST 5: Testing Particular Sender Prompt & Entity Extraction")
    print("==================================================")
    brain = AgentBrain()

    # 1. When user requests particular sender without naming one:
    p_generic = "I want this agent to put all mails from a particular sender in a folder named after the sender"
    res_generic = brain.think(p_generic)
    assert res_generic.get("intent") == "SORT_BY_SENDER", f"Expected SORT_BY_SENDER, got {res_generic.get('intent')}"
    assert res_generic.get("parameters", {}).get("needs_target_sender") is True, "Expected needs_target_sender to be True!"
    assert res_generic.get("parameters", {}).get("target_sender") is None, "Expected target_sender to be None!"
    print(f"✅ Generic request '{p_generic}' correctly flagged needs_target_sender=True.")

    # 2. Agent handle_user_prompt with generic prompt returns helpful guidance
    agent = GmailAIAgent()
    remark, _ = agent.handle_user_prompt(p_generic)
    assert "Which sender would you like me to organize?" in remark or "particular sender in a folder" in remark, f"Unexpected remark: {remark}"
    print(f"✅ Agent returned guided instructions:\n{remark}\n")

    # 3. Email address sender extraction
    p_email = "put all mails from client@example.com in a folder named after the sender"
    res_email = brain.think(p_email)
    assert res_email.get("parameters", {}).get("target_sender") == "client@example.com", f"Expected client@example.com, got {res_email.get('parameters', {}).get('target_sender')}"
    print(f"✅ Email sender extracted: {res_email.get('parameters', {}).get('target_sender')}")

    # 4. Quoted entity sender extraction
    p_quoted = 'put all mails from "Amazon" in a folder named after the sender'
    res_quoted = brain.think(p_quoted)
    assert res_quoted.get("parameters", {}).get("target_sender") == "Amazon", f"Expected Amazon, got {res_quoted.get('parameters', {}).get('target_sender')}"
    print(f"✅ Quoted sender extracted: {res_quoted.get('parameters', {}).get('target_sender')}")

    # 5. Domain / company sender extraction
    p_company = "put all mails from boss@company.com into a folder named after the sender"
    res_company = brain.think(p_company)
    assert res_company.get("parameters", {}).get("target_sender") == "boss@company.com", f"Expected boss@company.com, got {res_company.get('parameters', {}).get('target_sender')}"
    print(f"✅ Company email sender extracted: {res_company.get('parameters', {}).get('target_sender')}")

def test_server_routes():
    print("==================================================")
    print("TEST 5: Testing Flask Server Endpoints")
    print("==================================================")
    from server import app
    client = app.test_client()

    # 1. Test status
    status_res = client.get("/api/status")
    assert status_res.status_code == 200, f"Status failed: {status_res.status_code}"
    print("✅ /api/status returned 200 OK")

    # 2. Test blocked senders
    b_res = client.get("/api/blocked_senders")
    assert b_res.status_code == 200, f"Blocked senders failed: {b_res.status_code}"
    b_json = b_res.get_json()
    assert "blocked_senders" in b_json, "Response missing 'blocked_senders'"
    print(f"✅ /api/blocked_senders returned: {b_json.get('blocked_senders')}")

    # 3. Test block endpoint
    blk_res = client.post("/api/block_sender", json={"sender": "test_api_spammer@deals.com"})
    assert blk_res.status_code == 200, f"Block endpoint failed: {blk_res.status_code}"
    blk_json = blk_res.get_json()
    assert blk_json.get("blocked_sender") == "test_api_spammer@deals.com", "Block endpoint did not block target sender!"
    print(f"✅ /api/block_sender successfully blocked: {blk_json.get('blocked_sender')}")

    # 4. Test unblock endpoint
    unblk_res = client.post("/api/unblock_sender", json={"sender": "test_api_spammer@deals.com"})
    assert unblk_res.status_code == 200, f"Unblock endpoint failed: {unblk_res.status_code}"
    print("✅ /api/unblock_sender successfully unblocked.")

    # 5. Test prompt endpoint with sender-wise sort
    p_res = client.post("/api/prompt", json={"prompt": "I need to sort my mails sender wise"})
    assert p_res.status_code == 200, f"Prompt endpoint failed: {p_res.status_code}"
    p_json = p_res.get_json()
    assert "remark" in p_json, "Response missing remark!"
    print(f"✅ /api/prompt handled 'I need to sort my mails sender wise' successfully: {p_json.get('remark')[:80]}...")

    # 6. Test /api/sort_sender with target_sender
    s_res = client.post("/api/sort_sender", json={"target_sender": "indusind", "max_scan": 10})
    assert s_res.status_code == 200, f"Sort sender failed: {s_res.status_code}"
    s_json = s_res.get_json()
    assert "remark" in s_json, "Response missing remark!"
    assert "indusind" in s_json.get("remark", "").lower(), "Expected remark to mention target sender indusind!"
    print(f"✅ /api/sort_sender targeting 'indusind' successfully: {s_json.get('remark')[:80]}...")

if __name__ == "__main__":
    test_brain_intents()
    test_agent_block_and_unblock()
    test_indusind_and_similar_sender_parsing()
    test_agent_sort_sender_routing()
    test_particular_sender_prompt_handling()
    test_server_routes()
    print("==================================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! 100% VERIFIED!")
    print("==================================================")
