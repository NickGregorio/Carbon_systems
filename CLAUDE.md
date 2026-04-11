# CLAUDE.md — AI Business Development System
## Operating Environment for Claude Code

This file is the authoritative context document for all AI agents in this system.
Claude Code should read this file before executing any task. All agents, schemas,
tools, workflows, and rules are defined here.

---

## System Overview

This is a multi-agent AI business development system designed to automate outreach
to US businesses that are likely to invest in AI automation services. The system
operates as four specialized agents coordinated by a CEO orchestrator.

**Mission**: Identify economic opportunity windows by US region and season, find
businesses within those windows that show investment readiness signals, reach out
with hyper-personalized campaigns, and nurture leads through to closed deals —
with minimal human intervention.

**Stack**: Python agents · n8n workflows · Supabase database · Claude API ·
GoHighLevel CRM · Instantly.ai email · Waalaxy LinkedIn

---

## Repository Structure

```
/
├── CLAUDE.md                          # This file — read first always
├── README.md                          # Setup and deployment guide
├── .env.example                       # All required environment variables
├── docker-compose.yml                 # n8n + supporting services
├── schema.sql                         # Full Supabase schema
├── agent_runner.py                    # Base agent execution loop
│
├── agents/
│   ├── market_intel/
│   │   ├── noaa_puller.py             # NOAA climate signals per region
│   │   ├── fred_puller.py             # FRED/BLS economic signals
│   │   ├── trends_puller.py           # Google Trends via SerpAPI
│   │   ├── news_classifier.py         # RSS feeds → Haiku signal tagging
│   │   ├── scorer.py                  # Weighted regional opportunity score
│   │   └── briefing.py                # Weekly markdown brief generator
│   │
│   ├── lead_targeting/
│   │   ├── maps_finder.py             # Google Maps API → candidate leads
│   │   ├── apollo_enricher.py         # Apollo.io firmographics + contacts
│   │   ├── job_scanner.py             # Indeed/LinkedIn job posting signals
│   │   ├── website_scanner.py         # Tech stack + funnel gap detection
│   │   └── scorer.py                  # Lead investment readiness score
│   │
│   ├── outreach/
│   │   ├── personalization_engine.py  # Haiku → subject + hook + CTA JSON
│   │   ├── email_templates/           # 5 base templates per sequence step
│   │   ├── instantly_client.py        # Instantly.ai API wrapper
│   │   ├── waalaxy_syncer.py          # LinkedIn sequence enrollment
│   │   └── reply_handler.py           # Reply classification + routing
│   │
│   ├── nurture/
│   │   ├── ghl_webhook_handler.py     # GoHighLevel stage change receiver
│   │   ├── precall_sequence.py        # Confirmation + reminder + SMS
│   │   ├── call_brief.py              # Pre-call AI briefing generator
│   │   ├── postcall_sequences.py      # Won / Follow-up / Not-now routing
│   │   └── proposal_generator.py      # Sonnet proposal draft from call notes
│   │
│   └── ceo/
│       ├── daily_briefing.py          # Morning summary of all system activity
│       ├── decision_logger.py         # Human action logging back to Supabase
│       └── health_monitor.py          # Error detection + Slack alerting
│
└── n8n/
    ├── market_intel_workflow.json
    ├── lead_targeting_workflow.json
    ├── outreach_email_workflow.json
    ├── nurture_workflow.json
    └── ceo_briefing_workflow.json
```

---

## Environment Variables

All secrets live in `.env`. Never hardcode keys. Load with `python-dotenv`.

```bash
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Data APIs (Market Intelligence)
NOAA_API_KEY=...
FRED_API_KEY=...                        # Free at fred.stlouisfed.org
SERPAPI_KEY=...                         # Google Trends (100 free/mo)
GOOGLE_MAPS_API_KEY=...

# Lead Targeting
APOLLO_API_KEY=...
RAPIDAPI_KEY=...                        # Indeed job postings

# Outreach
INSTANTLY_API_KEY=...
WAALAXY_API_KEY=...

# Nurture + CRM
GHL_API_KEY=...                         # GoHighLevel
GHL_LOCATION_ID=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+1...
PANDADOC_API_KEY=...

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
NOTIFICATION_EMAIL=your@email.com
```

---

## Database Schema (Supabase)

### Table: `regions`
Stores weekly opportunity scores per US region.

```sql
CREATE TABLE regions (
  id           TEXT PRIMARY KEY,          -- e.g. 'sct', 'seu', 'pac'
  name         TEXT NOT NULL,             -- 'S. Central'
  states       TEXT NOT NULL,             -- 'TX · LA · OK'
  scored_at    TIMESTAMPTZ DEFAULT now(),
  seasonal     INTEGER,                   -- 0–100
  economic     INTEGER,                   -- 0–100
  news         INTEGER,                   -- 0–100
  industry_fit INTEGER,                   -- 0–100 (static per region)
  total        INTEGER,                   -- weighted composite
  trigger_text TEXT,                      -- 'Pre-hurricane season window'
  week_delta   INTEGER                    -- change from last week (+ = accelerating)
);
```

### Table: `signals`
Raw data points from all puller agents, append-only.

```sql
CREATE TABLE signals (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id    TEXT REFERENCES regions(id),
  source       TEXT,     -- 'noaa' | 'fred' | 'bls' | 'trends' | 'news'
  signal_type  TEXT,     -- 'climate_anomaly' | 'unemployment_delta' | 'job_openings' | etc
  value        FLOAT,
  raw_json     JSONB,
  fetched_at   TIMESTAMPTZ DEFAULT now()
);
```

### Table: `leads`
One record per business. Enriched progressively across agents.

```sql
CREATE TABLE leads (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id         TEXT REFERENCES regions(id),
  company_name      TEXT NOT NULL,
  website           TEXT,
  phone             TEXT,
  address           TEXT,
  google_rating     FLOAT,
  google_review_cnt INTEGER,

  -- Apollo enrichment
  contact_name      TEXT,
  contact_email     TEXT,
  contact_title     TEXT,
  linkedin_url      TEXT,
  employee_count    TEXT,
  revenue_range     TEXT,

  -- Scoring
  pain_score        INTEGER,       -- 0–100
  financial_score   INTEGER,       -- 0–100
  timing_score      INTEGER,       -- 0–100
  digital_score     INTEGER,       -- 0–100
  total_score       INTEGER,       -- weighted composite
  tier              TEXT,          -- 'hot' | 'warm' | 'cold'
  pitch_angle       TEXT,          -- one-sentence personalized hook

  -- Signal flags
  has_crm           BOOLEAN,
  has_booking_widget BOOLEAN,
  tech_stack        TEXT[],
  job_posting_flags TEXT[],        -- roles detected in job postings

  -- Outreach state
  outreach_status   TEXT DEFAULT 'pending',
  -- pending | enrolled | replied_interested | replied_notnow
  -- replied_unsubscribe | call_booked | proposal_sent | won | lost
  sequence_step     INTEGER DEFAULT 0,
  last_contact_at   TIMESTAMPTZ,
  reply_text        TEXT,
  reply_class       TEXT,

  -- CRM
  ghl_contact_id    TEXT,
  ghl_stage         TEXT,

  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now()
);
```

### Table: `events`
Append-only audit log of every action taken by any agent.

```sql
CREATE TABLE events (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id     UUID REFERENCES leads(id),
  agent       TEXT,      -- 'market_intel' | 'lead_targeting' | 'outreach' | 'nurture' | 'ceo'
  action      TEXT,      -- 'email_sent' | 'reply_received' | 'call_booked' | etc
  payload     JSONB,
  cost_usd    FLOAT,     -- API cost for this action
  created_at  TIMESTAMPTZ DEFAULT now()
);
```

---

## Agent Specifications

### Agent 1: Market Intelligence
**Schedule**: Every Monday 06:00 local time via n8n cron
**Model**: Claude Haiku (news classification) + Claude Sonnet (briefing synthesis)
**Input**: External APIs (NOAA, FRED, BLS, SerpAPI, RSS feeds)
**Output**: Updated `regions` table + weekly markdown brief emailed to operator

**Scoring formula**:
```python
total = (
    seasonal_score  * 0.25 +
    economic_score  * 0.25 +
    news_score      * 0.20 +
    industry_fit    * 0.30
)
```

**Regional definitions** (9 zones):
```python
REGIONS = {
    'sct': {'name': 'S. Central',    'states': 'TX,LA,OK,AR', 'industry_fit': 84},
    'seu': {'name': 'Southeast',     'states': 'FL,GA,NC,SC',  'industry_fit': 80},
    'mda': {'name': 'Mid-Atlantic',  'states': 'NY,NJ,PA,MD',  'industry_fit': 80},
    'pac': {'name': 'Pacific Coast', 'states': 'CA,OR,WA',     'industry_fit': 82},
    'swt': {'name': 'Southwest',     'states': 'AZ,NV,NM,UT',  'industry_fit': 72},
    'glk': {'name': 'Great Lakes',   'states': 'MI,OH,IL,WI',  'industry_fit': 74},
    'nen': {'name': 'New England',   'states': 'MA,CT,ME,VT',  'industry_fit': 68},
    'npl': {'name': 'N. Plains',     'states': 'MN,IA,NE,ND',  'industry_fit': 58},
    'mtn': {'name': 'Mountain West', 'states': 'CO,MT,ID,WY',  'industry_fit': 65},
}
```

**News signal tags** (Haiku classifies each RSS article into one):
- `disaster_recovery` — opportunity window: 3 weeks
- `business_expansion` — opportunity window: 6 weeks
- `labor_shortage` — opportunity window: 8 weeks
- `regulatory_change` — opportunity window: 12 weeks
- `industry_disruption` — opportunity window: 10 weeks
- `noise` — discard

---

### Agent 2: Lead Targeting
**Schedule**: Every Tuesday 07:00, triggered after market intel completes
**Model**: Claude Haiku (lead scoring + pitch angle)
**Input**: Top 3 regions by score from `regions` table
**Output**: New `leads` records with scores, tiers, and pitch angles

**Target company profile**:
- Employee count: 5–75 (owner-operated, not enterprise)
- Revenue range: $1M–$20M estimated
- Google reviews: 50+ (doing real volume)
- Industries (priority order): HVAC, Roofing/Restoration, Insurance, Logistics,
  Real Estate, Healthcare Admin, Construction/Trades

**Job posting trigger phrases** (flag lead as high-pain):
```python
PAIN_JOB_TITLES = [
    'dispatcher', 'scheduling coordinator', 'customer service rep',
    'office manager', 'admin assistant', 'call center', 'receptionist',
    'estimator', 'follow-up coordinator', 'intake coordinator'
]
```

**Lead scoring weights**:
```python
WEIGHTS = {
    'pain':     0.35,  # operational pain signals
    'financial': 0.30, # revenue size + growth indicators
    'timing':   0.20,  # regional score + seasonal proximity
    'digital':  0.15,  # website maturity + automation gaps
}

TIERS = {
    'hot':  (72, 100),  # immediate personalized outreach
    'warm': (52, 71),   # automated nurture sequence
    'cold': (0,  51),   # newsletter list + re-score trigger
}
```

**Haiku scoring prompt** (use exactly):
```
You are a lead scoring specialist for an AI automation agency.
Given this enriched business record, score the lead's investment readiness.

Business record:
{lead_json}

Output ONLY valid JSON with these fields:
{
  "pain_score": <0-100>,
  "financial_score": <0-100>,
  "timing_score": <0-100>,
  "digital_score": <0-100>,
  "total_score": <weighted composite>,
  "tier": <"hot"|"warm"|"cold">,
  "pitch_angle": "<one sentence: the specific pain point most likely to resonate>"
}

Scoring criteria:
- pain_score: manual/paper workflows=80+, job postings for ops roles=70+,
  no CRM detected=75+, high review volume with no booking widget=65+
- financial_score: 10-50 employees=70+, 50-200 reviews=65+,
  10+ year old business=60+, growth signals in job postings=70+
- timing_score: directly pass the region's current opportunity score
- digital_score: pre-2019 website=70+, no booking widget=80+,
  no SSL=60+, modern site with gaps=40
```

---

### Agent 3: Outreach
**Schedule**: Wednesday–Friday, triggered after lead targeting
**Model**: Claude Haiku (personalization + reply classification)
**Input**: Hot leads from `leads` table with status='pending'
**Output**: Enrolled email sequences + LinkedIn queue + reply classifications

**Email sequence timing**:
```python
SEQUENCE = [
    {'step': 1, 'day_offset': 0,  'type': 'hook',      'subject_style': 'personal_question'},
    {'step': 2, 'day_offset': 4,  'type': 'proof',     'subject_style': 'result_reference'},
    {'step': 3, 'day_offset': 9,  'type': 'resource',  'subject_style': 'value_first'},
    {'step': 4, 'day_offset': 16, 'type': 'linkedin',  'channel': 'linkedin'},
    {'step': 5, 'day_offset': 21, 'type': 'breakup',   'subject_style': 'last_email'},
]
```

**Personalization prompt** (Haiku, ~$0.001/call):
```
You are writing outreach for an AI automation agency targeting small-mid US businesses.

Lead data:
- Company: {company_name}
- Industry: {industry}
- First name: {contact_name}
- Pain signal: {pitch_angle}
- Seasonal trigger: {trigger_text}
- Digital gap: {digital_gap}
- Region: {region_name}

Output ONLY valid JSON:
{
  "subject": "<max 8 words, no punctuation, feels like a colleague>",
  "hook": "<opening sentence only, 1-2 lines, hyper-specific to their situation>",
  "pain_phrase": "<how they likely describe their own pain in casual speech>",
  "seasonal_urgency": "<one sentence connecting their business to current timing>",
  "cta": "<single low-friction ask, 15-min call or quick question>"
}

Rules:
- Never use: 'I hope this finds you well', 'touching base', 'quick question',
  'reaching out', 'synergy', 'game-changing', 'revolutionary'
- Subject lines that work: statements, observations, named references to their city
  or industry event, incomplete sentences that create curiosity
- Hook must feel like you've actually looked at their business
```

**Reply classification prompt** (Haiku):
```
Classify this email reply into exactly one category.

Reply: "{reply_text}"

Output ONLY one word:
- interested   (wants to learn more, open to a call, asks a question)
- not_now      (too busy, not right time, try later)
- referral     (suggests another person to contact)
- unsubscribe  (remove me, stop emailing, not interested)
- objection    (has a specific concern: price, past experience, relevance)
- other        (anything that doesn't fit above)
```

**LinkedIn message templates**:
```python
LINKEDIN_CONNECTION = """
Hi {first_name} — noticed {company_name} is doing impressive volume in {region}.
I work with {industry} companies on automating their intake and follow-up systems.
Would love to connect.
"""  # Max 300 chars

LINKEDIN_MSG_1 = """
Hi {first_name} — thanks for connecting. Sent you an email last week about
{pitch_angle} — figured LinkedIn might be an easier channel. Happy to share a
quick example of what this looks like for a company your size if useful.
"""

LINKEDIN_MSG_2 = """
No pressure at all {first_name} — just wanted to close the loop. If the timing
ever makes sense, I'm here. Hope {seasonal_context} treats {company_name} well.
"""
```

---

### Agent 4: Nurture & Close
**Schedule**: Event-driven (webhook from GoHighLevel + Calendly)
**Model**: Claude Sonnet (call briefs + proposals) + Haiku (sequences + routing)
**Input**: GHL stage change webhooks + Calendly booking webhooks
**Output**: Pre-call sequences, call briefs, post-call sequences, proposals

**GHL pipeline stages** (create exactly these in GoHighLevel):
```
1. Interested
2. Call Booked
3. Call Completed
4. Proposal Sent
5. Won
6. Not Now
7. Lost
```

**Pre-call sequence** (fires on Calendly booking webhook):
```python
PRE_CALL_SEQUENCE = [
    {'offset_hrs': 0,   'channel': 'email', 'template': 'booking_confirmation'},
    {'offset_hrs': -24, 'channel': 'email', 'template': 'call_reminder_insight'},
    {'offset_hrs': -2,  'channel': 'sms',   'template': 'sms_reminder'},
    {'offset_mins': -30,'channel': 'email', 'template': 'call_brief_to_operator'},
]
```

**Call brief prompt** (Sonnet, fires 30 min before call):
```
You are preparing a sales call brief for a discovery call happening in 30 minutes.

Lead record:
{lead_json}

Output a call brief in this exact format:

CALL BRIEF — {company_name} — {contact_name}
Time: {call_time}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
• Industry: {industry} in {region_name}
• Est. revenue: {revenue_range} | Employees: {employee_count}
• Business age: {company_age} | Reviews: {review_count}
• Score: {total_score}/100 ({tier})

PAIN SIGNALS DETECTED
• {pain_signal_1}
• {pain_signal_2}
• {pain_signal_3}

OPENING ANGLE
{pitch_angle} — reference this in your first 60 seconds.

DISCOVERY QUESTIONS (pick 2–3)
• Walk me through what happens when a new lead calls you right now.
• How are you currently tracking which jobs are in progress?
• What's the biggest operational headache heading into {season}?
• Have you looked at any automation tools before? What happened?

PREDICTED OBJECTION
{predicted_objection}

SUGGESTED RESPONSE TO OBJECTION
{objection_reframe}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Post-call routing** (based on outcome logged in GHL):
```python
OUTCOMES = {
    'won':      ['send_contract_pandadoc', 'start_onboarding_sequence', 'slack_notify'],
    'followup': ['generate_proposal_sonnet', 'start_postcall_4touch', 'set_followup_reminder'],
    'notnow':   ['start_monthly_drip', 'set_rescore_trigger', 'log_reason'],
    'lost':     ['log_reason', 'suppress_90days'],
}
```

**Re-activation triggers** (monitor continuously for not-now leads):
```python
REACTIVATION_TRIGGERS = [
    {'type': 'region_score_spike', 'threshold': 15},  # points increase in 1 week
    {'type': 'new_job_postings',   'count': 3},        # 3+ new ops role postings
    {'type': 'time_elapsed',       'days': 90},        # 90-day re-intro
    {'type': 'news_mention',       'tags': ['disaster_recovery', 'business_expansion']},
]
```

---

### Agent 5: CEO Orchestrator
**Schedule**: Daily 07:00 (briefing) + event-driven (interested reply alerts)
**Model**: Claude Sonnet
**Role**: Reads all agent outputs, surfaces decisions requiring human input,
monitors system health, escalates anomalies

**Daily briefing prompt**:
```
You are the CEO agent for an AI business development system. Review last 24 hours
of activity and produce a structured daily briefing.

System data (last 24hrs):
{supabase_summary_json}

Output format:
## Daily Brief — {date}

**Pipeline snapshot**
- Leads scored today: X (X hot / X warm / X cold)
- Emails sent: X | Open rate: X% | Reply rate: X%
- Interested replies: X — [list names + companies]
- Calls booked: X | Calls completed: X
- Deals won this week: X ($X MRR)

**Actions required from you**
1. [specific action with lead name and context]
2. ...

**System health**
- [any errors, anomalies, or cost overruns to flag]
- Total API spend today: $X.XX

**Top opportunity right now**
[1 paragraph: highest-scoring region + industry + why this week is the window]
```

---

## Model Routing Rules

Route to the cheapest model that can handle the task quality requirements.

```python
MODEL_ROUTING = {
    # Haiku — fast, cheap (~$0.001/call): classification, scoring, simple generation
    'news_classification':      'claude-haiku-4-5-20251001',
    'lead_scoring':             'claude-haiku-4-5-20251001',
    'reply_classification':     'claude-haiku-4-5-20251001',
    'email_personalization':    'claude-haiku-4-5-20251001',
    'sms_generation':           'claude-haiku-4-5-20251001',
    'sequence_email_2_3_5':     'claude-haiku-4-5-20251001',

    # Sonnet — higher quality (~$0.010/call): synthesis, strategy, persuasion
    'weekly_briefing':          'claude-sonnet-4-6',
    'call_brief':               'claude-sonnet-4-6',
    'proposal_generation':      'claude-sonnet-4-6',
    'ceo_daily_briefing':       'claude-sonnet-4-6',
    'sequence_email_1':         'claude-sonnet-4-6',  # first email only
    'objection_responses':      'claude-sonnet-4-6',
}
```

---

## Cost Budget & Alerts

**Monthly cost targets by phase**:
```
Phase 1 (Wks 1–2):  $0      — no external APIs yet
Phase 2 (Wk 3):     $2      — NOAA/FRED/BLS (free tiers)
Phase 3 (Wk 4):     $50     — Apollo credits added
Phase 4 (Wks 5–6):  $90     — Instantly.ai + Haiku personalization
Phase 5 (Wk 7):     $130    — Waalaxy LinkedIn added
Phase 6 (Wks 8–9):  $330    — GoHighLevel + Twilio + Sonnet calls
Phase 7 (Wk 10):    $400    — Full system, all agents live
```

**Alert thresholds** (Slack notify if exceeded):
```python
COST_ALERTS = {
    'anthropic_daily_usd':    5.00,
    'apollo_weekly_credits':  200,
    'cost_per_lead_usd':      0.10,  # should be under $0.05
    'cost_per_email_usd':     0.002,
}
```

---

## Validation Gates

Before proceeding to the next phase, all gates for the current phase must pass.
Claude Code should check these programmatically where possible.

```python
VALIDATION_GATES = {
    'phase_1': [
        'supabase_tables_exist',         # SELECT COUNT(*) from each table
        'n8n_accessible',                # HTTP GET n8n health endpoint
        'agent_runner_posts_to_db',      # test record in events table
        'env_vars_all_present',          # check all keys in .env.example exist
    ],
    'phase_2': [
        'weekly_brief_delivered',        # check email received
        'regions_table_has_9_scores',    # SELECT COUNT(*) FROM regions = 9
        'cost_per_run_under_015',        # check events table cost sum
        'highest_region_plausible',      # manual review gate
    ],
    'phase_3': [
        'hot_leads_generated_20plus',    # SELECT COUNT(*) FROM leads WHERE tier='hot'
        'lead_records_complete',         # all required fields non-null
        'apollo_spend_under_30_week',    # manual check
        'manual_review_5_leads_pass',    # human gate — operator must sign off
    ],
    'phase_4': [
        'first_emails_delivered',        # Instantly dashboard open rate > 0
        'one_reply_received',            # SELECT COUNT(*) FROM events WHERE action='reply_received'
        'reply_routed_within_15min',     # check timestamp delta
        'open_rate_above_35pct',         # Instantly API stats
    ],
    'phase_5': [
        'daily_brief_arrives_7am',       # manual check
        'linkedin_under_25_per_day',     # Waalaxy dashboard
        'zero_manual_intervention',      # full week autonomous run
    ],
    'phase_6': [
        'end_to_end_test_passes',        # seed test lead, verify full flow
        'show_rate_above_65pct',         # calls_shown / calls_booked
        'one_real_discovery_call',       # human gate
        'post_call_sequence_fires',      # check events table
    ],
    'phase_7': [
        'full_week_autonomous',          # zero manual interventions logged
        'weekly_metrics_email',          # received with accurate data
        'total_cost_under_450',          # sum of all API costs
        'roi_positive',                  # at least 1 deal OR 3 qualified calls
    ],
}
```

---

## Claude Code Instructions

When Claude Code is working on this project, follow these rules:

1. **Always read this file first.** Before writing any code, confirm you have
   read and understood the full schema, agent specs, and model routing rules.

2. **Write to Supabase, not files.** All agent state lives in the database.
   Never use local files or in-memory state for anything that needs to persist.

3. **Log every AI call to the events table.** Include agent name, action,
   cost_usd (calculate from token counts), and a payload summary.

4. **Use the model routing table.** Do not use Sonnet where Haiku is specified.
   Cost discipline is a first-class requirement.

5. **Every agent must be idempotent.** Running it twice should not create
   duplicate records. Use upsert logic on natural keys.

6. **Handle API failures gracefully.** External APIs (NOAA, Apollo, Instantly)
   will fail. Catch exceptions, log to events table, send Slack alert, continue
   processing remaining records. Never crash the full pipeline over one bad record.

7. **Validate before proceeding.** After completing a phase, run the validation
   gates programmatically. Surface any failures to the operator before continuing.

8. **Prompt for human gates.** Some validation gates require human review
   (marked 'human gate' or 'manual review gate'). Pause and ask the operator
   to confirm before proceeding to the next phase.

9. **Keep prompts in this file.** If you modify a prompt for any agent,
   update it here so this file stays authoritative.

10. **Test with seed data first.** Before running any agent against real APIs,
    create a `tests/seed_data.json` with 5 fake lead records and validate the
    full pipeline end-to-end at zero API cost.

---

## Weekly Operating Rhythm

```
Monday    06:00  Market Intelligence agent runs → regions scored → brief emailed
Tuesday   07:00  Lead Targeting agent runs → hot leads generated → CSV to operator
Wednesday 09:00  Outreach agent runs → top 20 hot leads enrolled in email sequence
Thursday         Ongoing — reply handler polling every 4hrs
Friday    08:00  CEO agent weekly performance report
Saturday         System idle
Sunday           System idle
```

---

## Current System Status

Update this section manually each week.

```
Phase:           [ ] 1  [ ] 2  [ ] 3  [ ] 4  [ ] 5  [ ] 6  [ ] 7
Current phase:   1 — Environment setup
Last updated:    —
Leads in system: 0
Hot leads:       0
Calls booked:    0
MRR added:       $0
Weekly infra $:  $0
```

---

*This document is the single source of truth for the system.
All agents, prompts, schemas, and rules defined here take precedence
over anything written in individual agent files.*
