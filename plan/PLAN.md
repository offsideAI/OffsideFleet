# PLAN.md — OffsideFleet · Plan v1

**Status:** awaiting founder approval (`APPROVED: PLAN v1`). Companions: `ARCHITECTURE.md` (ADRs), `DATA_MODEL.md`, `API_SURFACE.md`, `MILESTONES.md`, `RISKS.md`, `TESTING.md`, plus repo-root `ROADMAP.md` (full story breakdown) and `DECISIONS.md` (interview record, including two founder overrides carrying staff dissent).

## Executive summary

OffsideFleet is a standalone platform (portfolio consolidation was vetoed in the interview) for building, managing, and orchestrating cloud AI agents — differentiated not by authoring UX but by **production discipline at indie prices**: every agent action is a traced, per-step-costed, budgeted, deterministically replayable, killable Run. The MVP wedge, chosen in the interview, is a **roster of named agents with identities** (Buzz/GrokBot-inspired): agents as characters you chat with 1:1 and schedule to work autonomously — backed by a flight-recorder run inspector rather than a log dump.

The build is phased A→D over ~192 focused days (~11–12 months solo; see ROADMAP.md "Reading this honestly"). Phase A (~65 fd, 7 milestones, ships ~mid-late Jan 2027) delivers the MVP below. Phase B adds orchestration, multi-provider, TS SDK/CLI, and five more tools. Phase C adds agency multi-workspace, the browser extension, and shared channels. Phase D adds marketplace, headless API, voice/GTM, and the DAG editor. Nothing was killed; everything is sequenced with its price visible.

## MVP definition

**One paragraph:** A user signs into an OffsideFleet workspace and creates a roster of named agents — each with an identity (name, avatar, persona) and specific functionality (Anthropic model, system prompt, scoped tools, budget) — authored in a visual builder over a canonical JSON IR (TypeScript DSL authoring follows in M10). They talk to each agent in a dedicated 1:1 chat where the agent remembers prior conversations (pgvector semantic memory), and schedule any agent via cron. Every interaction — chat, manual, scheduled — executes as a request-scoped Run (15-min cap) in a hardened container on a DO runner droplet, using tools (web search, web fetch, Google Workspace read, Resend email) brokered by Fleet's own MCP layer so the model never holds credentials. Every Run yields a replay-grade step-level trace with per-step dollar cost, is budget-enforced pre-call and post-call (≤1-step overrun), is deterministically replayable offline, and dies within 2 seconds of the kill switch. Ships with three Stripe tiers ($0/$49/$199) and metered token pass-through.

**MVP acceptance test (the literal `just demo-mvp` script, M7.S5):**
1. Fresh signup → create a named agent (identity + persona + tools + budget) — under 15 minutes to first reply.
2. Chat with it; it uses web search + Google Calendar; flip a reply to its step trace with per-step dollar cost.
3. Next day (simulated), it correctly recalls a fact from the earlier conversation.
4. Schedule it every 2 minutes; watch an unattended traced run; receive its digest email.
5. Set a $0.05 budget; watch a run hard-stop before overshooting (≤1 step).
6. Hit the kill switch mid-run; the container dies in <2s; the kill is ledgered.
7. Replay yesterday's run offline; the trace is identical.
8. Subscribe to Squadron in Stripe test mode; usage from the above runs appears metered.
9. Run the tenant-isolation suite; a forged `X-Workspace-Id` gets 403 everywhere.

## What we are NOT building (in the MVP)

Webhook/event triggers · orchestration of any kind (schema exists, no UI/executor) · shared multi-party channels · non-Anthropic providers (interface stubbed only) · TS SDK/CLI (IR is designed for it; ships M10) · agency/org layer · browser extension · marketplace/template SDK (one hardcoded dogfood pack at most) · voice · DAG editor · Postgres RLS (Phase B) · OTel/metrics stack · Google OAuth verification (test mode only). Each has a named milestone in ROADMAP.md — deferred, not denied.

## Sequencing rationale

- **Spine first (M1):** every risky subsystem — sandbox, trace, kill — exists by day 8 in skeletal form; everything later decorates it rather than discovering it.
- **Identity before tools (M2–M3 before M4):** the founder's chosen hero is the roster + chat feel; we validate it on keyless dogfood before paying the OAuth/broker tax.
- **Replay before billing (M6 before M7):** the founder pulled replay into the MVP; placing it after budgets/kill (M5) and before ship (M7) gives it maximal schedule buffer and a pre-agreed fallback gate at M5 exit (ship recording, defer engine) if it blows 150%.
- **Tenancy hardening + billing last in Phase A (M7):** the adversarial isolation suite needs the full endpoint surface to exist to be meaningful; Stripe needs real run costs to meter.
- **Orchestration opens Phase B:** it multiplies the value of everything in Phase A and is the most-requested capability we deliberately excluded from MVP scope.

## Two standing dissents the approver should re-read before approving

1. **Deterministic replay inside the MVP** (DECISIONS.md) — lowest-confidence epic on the board, inside the ship gate; fallback pre-agreed at M5 exit.
2. **Customer secrets plaintext in Postgres** (DECISIONS.md) — tripwire: encrypt (~1 fd) or founder re-accepts on the record before the first external credential (M7.S5).

## Approval

**Reply `APPROVED: PLAN v1` to begin implementation, or list objections.**
