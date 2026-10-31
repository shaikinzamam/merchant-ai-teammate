from tests.conftest import OP, SVC, chat


def test_chat_requires_service_key(client):
    r = client.post("/v1/chat", json={"merchant_id": "M1001", "message": "hi"})
    assert r.status_code == 401
    assert "SERVICE_API_KEY" in r.json()["error"]["message"]


def test_chat_accepts_only_the_configured_x_api_key(client):
    body = {"merchant_id": "M1001", "message": "settlement status"}

    valid = client.post("/v1/chat", json=body, headers={"X-Api-Key": SVC["X-Api-Key"]})
    assert valid.status_code == 200

    for headers in ({"X-Api-Key": "wrong"}, {"X-Service-Key": SVC["X-Api-Key"]}):
        rejected = client.post("/v1/chat", json=body, headers=headers)
        assert rejected.status_code == 401
        assert rejected.json()["error"]["code"] == "unauthorized"


def test_every_protected_endpoint_requires_its_own_credentials(client):
    operator_routes = [
        ("get", "/v1/operator/whoami", None),
        ("get", "/v1/approvals", None),
        ("post", "/v1/approvals/missing/approve", {}),
        ("post", "/v1/approvals/missing/reject", {}),
        ("get", "/v1/escalations", None),
        ("post", "/v1/escalations/missing/close", {}),
        ("get", "/v1/audit", None),
        ("get", "/v1/audit/verify", None),
    ]
    for method, path, body in operator_routes:
        request = getattr(client, method)
        if method == "get":
            unauthorized = request(path, headers=SVC)
            response = request(path)
        else:
            unauthorized = request(path, json=body, headers=SVC)
            response = request(path, json=body)
        assert unauthorized.status_code == 401
        assert response.status_code == 401
        assert "OPERATOR_API_KEYS" in response.json()["error"]["message"]

    assert client.post(
        "/v1/chat", json={"merchant_id": "M1001", "message": "hi"}, headers=OP
    ).status_code == 401
    assert client.post(
        "/v1/chat",
        json={"merchant_id": "M1001", "message": "hi"},
        headers={"X-Api-Key": "wrong"},
    ).status_code == 401


def test_hindi_settlement_demo_flow(client, container):
    r = chat(client, "M1001", "Mera kal ka settlement abhi tak account me kyu nahi aaya?")
    assert r.status_code == 200
    body = r.json()
    assert body["language"] == "hi" and body["intent"] == "settlement_status"
    assert "11:30" in body["reply"] and body["tools_environment"] == "SIMULATED"
    status = {a["tool"]: a["status"] for a in body["actions"]}
    assert status["check_settlement_status"] == "EXECUTED"
    assert status["create_crm_lead"] == "PENDING_APPROVAL"   # lead needs Tier-2 approval
    assert container.integration.leads == []

    pending = client.get("/v1/approvals", headers=OP).json()
    assert len(pending) == 1 and pending[0]["tool_name"] == "create_crm_lead"
    ap = client.post(f"/v1/approvals/{pending[0]['id']}/approve", headers=OP).json()
    assert ap["outcome"]["status"] == "EXECUTED" and len(container.integration.leads) == 1

    events = client.get("/v1/audit", params={"session_id": body["session_id"]}, headers=OP).json()
    kinds = {e["event_type"] for e in events}
    assert {"chat.received", "plan.proposed", "policy.decision", "tool.executed"} <= kinds
    assert client.get("/v1/audit/verify", headers=OP).json()["valid"] is True


def test_operator_endpoints_require_credentials(client):
    assert client.get("/v1/approvals").status_code == 401
    bad = {"X-Operator-Id": "op1", "X-Operator-Key": "wrong"}
    assert client.get("/v1/approvals", headers=bad).status_code == 401
    assert client.get("/v1/approvals", headers=SVC).status_code == 401  # service key != operator


def test_operator_whoami_validates_credentials_without_returning_a_key(client):
    assert client.get("/v1/operator/whoami", headers=OP).json() == {"operator_id": "op1"}
    assert client.get("/v1/operator/whoami").status_code == 401


def test_operator_can_reject_approval_and_close_escalation(client):
    approval_chat = chat(client, "M1001", "dispute for TXN100001 double debit").json()
    approval_id = approval_chat["actions"][0]["human_task_id"]
    escalation_chat = chat(client, "M1001", "someone hacked my account, unauthorized transfers").json()
    assert escalation_chat["actions"][0]["status"] == "ESCALATED"

    approvals = client.get("/v1/approvals", headers=OP).json()
    assert any(task["id"] == approval_id for task in approvals)
    rejected = client.post(f"/v1/approvals/{approval_id}/reject", headers=OP, json={})
    assert rejected.status_code == 200 and rejected.json()["task"]["status"] == "REJECTED"

    escalations = client.get("/v1/escalations", headers=OP).json()
    assert len(escalations) == 1
    closed = client.post(f"/v1/escalations/{escalations[0]['id']}/close", headers=OP, json={})
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert client.get("/v1/audit", headers=OP).status_code == 200
    assert client.get("/v1/audit/verify", headers=OP).json()["valid"] is True


def test_fraud_flagged_merchant_is_escalated_not_served(client, container):
    r = chat(client, "M1003", "mera settlement kal ka nahi aaya")
    body = r.json()
    assert all(a["status"] != "EXECUTED" for a in body["actions"])
    assert any(a["status"] == "ESCALATED" for a in body["actions"])
    assert len(client.get("/v1/escalations", headers=OP).json()) == 1


def test_fraud_report_escalates(client):
    body = chat(client, "M1001", "someone hacked my account, unauthorized transfers").json()
    assert body["actions"][0]["tool"] == "escalate_to_human"
    assert body["actions"][0]["status"] == "ESCALATED"


def test_soundbox_issue_runs_diagnostics(client):
    body = chat(client, "M1001", "My soundbox is not working").json()
    assert body["intent"] == "soundbox_issue"
    assert body["actions"][0]["tool"] == "soundbox_diagnostics"
    assert body["actions"][0]["status"] == "EXECUTED"


def test_dispute_needs_txn_then_waits_for_approval(client):
    assert "TXN" in chat(client, "M1001", "I want to raise a dispute").json()["reply"]
    body = chat(client, "M1001", "dispute for TXN100001 double debit").json()
    assert body["actions"][0] == {"tool": "file_dispute", "status": "PENDING_APPROVAL",
                                  "tier": 2, "human_task_id": body["actions"][0]["human_task_id"]}


def test_high_value_dispute_is_escalated_by_risk_engine(client):
    body = chat(client, "M1001", "dispute TXN100002 not received").json()
    assert body["actions"][0]["status"] == "ESCALATED"


def test_session_cannot_be_reused_by_another_merchant(client):
    sid = chat(client, "M1001", "settlement status?").json()["session_id"]
    assert chat(client, "M1002", "settlement status?", sid).status_code == 403


def test_unknown_merchant_does_not_leak_details(client):
    r = chat(client, "M9999", "settlement")
    assert r.status_code == 200 and r.json()["actions"] == []
