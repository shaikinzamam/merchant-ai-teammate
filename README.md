# Merchant AI Teammate

Hackathon prototype for **Paytm Build for India · Track 3: Autonomous AI Teammates**.
An AI teammate that understands a merchant's query (Hindi / Telugu / Kannada / English), acts through
tools **only within policy**, collaborates with human operators, and proposes growth leads.

> **Simulation notice.** All Paytm-style tools and data are **mocks** (`app/integrations/mock_paytm`).
> No production Paytm API or system is accessed, and none is claimed. A real integration would be a
> separate adapter in `app/integrations/paytm_real` (currently a placeholder that refuses to start).

## Architecture (modular monolith)

```
Merchant ─► POST /v1/chat ─► AgentService ──► Planner (rules | Groq LLM)   proposes only
                                  │
                                  ▼  every step, no exceptions
                            ToolGateway ──► PolicyEngine + RiskEngine ──► verdict
                                  │            ALLOW (Tier 1) ─► execute mock tool
                                  │            REQUIRE_APPROVAL (Tier 2) ─► human task ─► operator approves ─► re-checked ─► execute
                                  │            ESCALATE (Tier 3) ─► escalation + brief for a human
                                  │            DENY ─► nothing runs
                                  ▼
                       AuditService (hash-chained, PostgreSQL)
```

| Module (`backend/app/`) | Responsibility |
|---|---|
| `modules/policy` | Permission matrix (default-deny), risk engine (can only *raise* tiers), policy engine |
| `modules/tools` | `ToolGateway` (the **only** path to tools), registry, typed param schemas |
| `modules/approvals` | Approval/escalation tasks: expiring, single-use, bound to an exact action hash |
| `modules/audit` | Append-only audit log with SHA-256 hash chain + verification |
| `modules/planner` | `LLMPlanner` (Groq, selected in the demo env) with deterministic rules fallback |
| `modules/language` | Language detection + localised templates |
| `modules/voice` | Optional Sarvam speech-to-text and text-to-speech adapter |
| `modules/growth` | Proposes CRM leads; the lead itself is still a Tier-2 action |
| `modules/orchestrator` | Understand → Decide → Act → Collaborate → Grow |
| `integrations/mock_paytm` | **Simulated** tools + merchant data |
| `integrations/paytm_real` | Placeholder only |
| `container.py` | Composition root / dependency injection |

### Safety guarantees (each has a test)

- The LLM/planner output is **untrusted**; it never holds a tool handle. Unknown tools, extra params, and cross-merchant params are denied.
- Merchant scope comes from the session, never from tool params.
- Risk signals come from the system of record (not from the LLM or message) and **fail closed** if unavailable.
- An approval only works for the exact tool + params + merchant it was issued for, once, before it expires; policy is **re-evaluated** at execution.
- A fraud-flagged merchant, 3+ failed KYC attempts, or a high-value dispute is escalated even for normally Tier-1 actions.
- `tests/test_architecture.py` fails the build if anything but the composition root imports an integration.

## Run locally (Python 3.11, Docker Desktop)

```powershell
copy .env.example .env
docker compose up -d db
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app_factory --factory --reload
```

The copied `.env.example` contains local-only demo credentials and uses the offline `rules` planner.
The backend always loads the single project-root `.env`, regardless of the terminal's working
directory. Do not create `backend/.env`; this keeps Docker and the backend on the same settings.
The authentication variables are:

```dotenv
SERVICE_API_KEY=local-demo-service-key
OPERATOR_API_KEYS={"op-demo":"local-demo-operator-key"}
```

Use the service key in the UI for merchant chat. For operator features, enter ID `op-demo` and
key `local-demo-operator-key`; these are sent separately as `X-Operator-Id` and `X-Operator-Key`.
Keep the project-root `.env` private, replace both demo values before any non-local use, and use unique
random keys of at least 32 characters in production. The browser does not read or receive `.env`.

Docs: http://localhost:8000/docs · Tests (from repo root): `python -m pytest -q` (uses in-memory SQLite, no network).

### Try the deck's demo

```powershell
curl.exe -X POST http://localhost:8000/v1/chat -H "X-Api-Key: <SERVICE_API_KEY>" -H "Content-Type: application/json" `
  -d '{\"merchant_id\":\"M1001\",\"message\":\"Mera kal ka settlement abhi tak account me kyu nahi aaya?\"}'
curl.exe http://localhost:8000/v1/approvals -H "X-Operator-Id: op-demo" -H "X-Operator-Key: <operator key>"
```

The dashboard cannot read `.env` (that would expose secrets to the browser). Paste the same
`SERVICE_API_KEY`, operator ID and matching operator key into the credentials panel, then select
**Verify operator**. Missing values show the exact backend variable names to configure; invalid
values remain a 401 at the API.

Demo merchants: `M1001` Hindi (delayed settlement) · `M1002` Telugu · `M1003` fraud-flagged → escalates · `M1004` KYC failures → escalates · `M1005` high volume (EDC lead).

## API

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /v1/chat` | `X-Api-Key` | Merchant message → reply + action summaries |
| `GET /v1/voice/status` | `X-Api-Key` | Voice availability and configured model names (never credentials) |
| `POST /v1/voice/chat` | `X-Api-Key` | Push-to-talk audio → transcript, normal chat reply + optional audio |
| `GET /v1/approvals`, `POST /v1/approvals/{id}/approve\|reject` | operator | Tier-2 human check |
| `GET /v1/escalations`, `POST /v1/escalations/{id}/close` | operator | Tier-3 queue |
| `GET /v1/audit`, `GET /v1/audit/verify` | operator | Audit trail + tamper check |
| `GET /health` | none | DB check; reports simulated tools and whether the service key is configured (never its value) |

Operator auth = `X-Operator-Id` + `X-Operator-Key` (keys from `OPERATOR_API_KEYS`).

## Implementation status (honest)

| | |
|---|---|
| Implemented + unit/integration tested | FastAPI service, policy/risk engine, gateway, approvals, escalation, hash-chained audit, rules planner, mock tools, Alembic migration |
| Implemented + unit-tested | Groq LLM planner (live connectivity depends on the deployment's egress policy; covered by a fake LLM client) |
| Voice / Sarvam | Implemented, live test pending |
| Mocked | Settlement, dispute, technician, bank-check, CRM tools; merchant data |
| Not implemented | MCP tool layer, real Paytm systems, rate limiting |

## Known gaps before any real use

Merchant identity must come from an authenticated session (here `merchant_id` is in the body); Te/Kn/Hi strings need native-speaker review; audit-chain appends are serialised per process only; growth thresholds are placeholders; no PII/consent (DPDP) handling for leads; no rate limiting.

## Frontend (React + Vite)

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173 — proxies /api/* to http://localhost:8000
```

Open **Merchant chat** to talk to the teammate as a demo merchant, and **Operator console** to approve Tier-2 actions, resolve Tier-3 escalations and verify the audit hash chain. Enter `SERVICE_API_KEY` and your operator id/key under *API credentials* (stored in `sessionStorage` for this tab only; prototype-grade — real deployments need proper operator login/SSO).

## Voice (Sarvam)

Voice is **push-to-talk request/response, not real-time streaming or telephony**. The browser records WebM/Opus (or MP4 where that is the browser's supported recorder format; both are documented Sarvam STT formats) and sends it to the backend; the backend transcribes it, sends the untrusted transcript through the same chat agent and policy gateway as typed messages, then optionally synthesizes the reply. No audio is written to application storage. Browser playback starts when you select **Play / replay reply**.

1. Create a Sarvam API key in [Sarvam dashboard key management](https://indus.sarvam.ai/key-management?ref=docs).
2. Keep the key only in the project-root backend `.env` and set:

   ```dotenv
   VOICE_BACKEND=sarvam
   SARVAM_API_KEY=your-private-sarvam-api-key
   SARVAM_BASE_URL=https://api.sarvam.ai
   SARVAM_STT_MODEL=saaras:v4
   SARVAM_TTS_MODEL=bulbul:v4-flash
   SARVAM_TTS_SPEAKER=shubh_enhi_ads
   VOICE_MAX_AUDIO_BYTES=5000000
   VOICE_TIMEOUT_SECONDS=30
   ```

3. From the project root, run the live provider check (this makes one TTS and one STT request; it never prints the key):

   ```powershell
   cd backend
   python scripts/sarvam_check.py
   ```

   A successful round trip prints `TTS OK`, `STT OK`, and the transcript. This check is intentionally not part of the automated test suite.
4. Restart the backend, open **Merchant chat**, enter the service API key in the credentials panel, allow microphone access, then select **Start talking** and tap **Stop recording** to send. The Hindi settlement, Telugu, and dispute chips select a merchant and start recording with a suggested phrase. Recordings stop at 30 seconds. Select **Play / replay reply** to hear generated audio.

The backend accepts documented Sarvam STT audio MIME types, limits uploads to `VOICE_MAX_AUDIO_BYTES` (5,000,000 bytes by default), and uses Sarvam's synchronous STT endpoint for recordings under 30 seconds. TTS requests are subject to Sarvam's documented 2,500-character limit. Voice is **implemented; a real Sarvam round trip has not yet been confirmed**. All merchant tools remain simulated; this feature does not connect to Paytm.
#   m e r c h a n t - a i - t e a m m a t e  
 