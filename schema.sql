-- AI Business Development System — Supabase Schema
-- Run this in the Supabase SQL editor to initialize all tables.
-- Order matters: regions before signals and leads.

-- ─────────────────────────────────────────────
-- REGIONS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS regions (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  states        TEXT NOT NULL,
  scored_at     TIMESTAMPTZ DEFAULT now(),
  seasonal      INTEGER CHECK (seasonal BETWEEN 0 AND 100),
  economic      INTEGER CHECK (economic BETWEEN 0 AND 100),
  news          INTEGER CHECK (news BETWEEN 0 AND 100),
  industry_fit  INTEGER CHECK (industry_fit BETWEEN 0 AND 100),
  total         INTEGER CHECK (total BETWEEN 0 AND 100),
  trigger_text  TEXT,
  week_delta    INTEGER DEFAULT 0
);

-- Seed the 9 static regions (industry_fit is static per region)
INSERT INTO regions (id, name, states, industry_fit) VALUES
  ('sct', 'S. Central',    'TX,LA,OK,AR', 84),
  ('seu', 'Southeast',     'FL,GA,NC,SC', 80),
  ('mda', 'Mid-Atlantic',  'NY,NJ,PA,MD', 80),
  ('pac', 'Pacific Coast', 'CA,OR,WA',    82),
  ('swt', 'Southwest',     'AZ,NV,NM,UT', 72),
  ('glk', 'Great Lakes',   'MI,OH,IL,WI', 74),
  ('nen', 'New England',   'MA,CT,ME,VT', 68),
  ('npl', 'N. Plains',     'MN,IA,NE,ND', 58),
  ('mtn', 'Mountain West', 'CO,MT,ID,WY', 65)
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────
-- SIGNALS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id    TEXT REFERENCES regions(id) ON DELETE CASCADE,
  source       TEXT NOT NULL,
  signal_type  TEXT NOT NULL,
  value        FLOAT,
  raw_json     JSONB,
  fetched_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS signals_region_source
  ON signals(region_id, source, fetched_at DESC);

-- ─────────────────────────────────────────────
-- LEADS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id           TEXT REFERENCES regions(id),

  -- Discovery (Google Maps)
  company_name        TEXT NOT NULL,
  website             TEXT,
  phone               TEXT,
  address             TEXT,
  google_place_id     TEXT UNIQUE,
  google_rating       FLOAT,
  google_review_cnt   INTEGER,
  industry            TEXT,

  -- Apollo enrichment
  contact_name        TEXT,
  contact_email       TEXT,
  contact_title       TEXT,
  linkedin_url        TEXT,
  employee_count      TEXT,
  revenue_range       TEXT,
  company_age_years   INTEGER,
  apollo_id           TEXT,

  -- Scoring
  pain_score          INTEGER DEFAULT 0,
  financial_score     INTEGER DEFAULT 0,
  timing_score        INTEGER DEFAULT 0,
  digital_score       INTEGER DEFAULT 0,
  total_score         INTEGER DEFAULT 0,
  tier                TEXT DEFAULT 'cold' CHECK (tier IN ('hot','warm','cold')),
  pitch_angle         TEXT,

  -- Signal flags
  has_crm             BOOLEAN,
  has_booking_widget  BOOLEAN,
  tech_stack          TEXT[],
  job_posting_flags   TEXT[],

  -- Outreach state
  outreach_status     TEXT DEFAULT 'pending',
  sequence_step       INTEGER DEFAULT 0,
  last_contact_at     TIMESTAMPTZ,
  reply_text          TEXT,
  reply_class         TEXT,
  instantly_id        TEXT,
  waalaxy_enrolled    BOOLEAN DEFAULT FALSE,

  -- CRM
  ghl_contact_id      TEXT,
  ghl_stage           TEXT,
  call_booked_at      TIMESTAMPTZ,
  call_completed_at   TIMESTAMPTZ,
  proposal_sent_at    TIMESTAMPTZ,
  deal_value_usd      FLOAT,

  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS leads_region_tier
  ON leads(region_id, tier, outreach_status);

CREATE INDEX IF NOT EXISTS leads_status
  ON leads(outreach_status, updated_at DESC);

-- Auto-update updated_at on any row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
  BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────
-- EVENTS  (append-only audit log)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id      UUID REFERENCES leads(id) ON DELETE SET NULL,
  region_id    TEXT REFERENCES regions(id) ON DELETE SET NULL,
  agent        TEXT NOT NULL,
  action       TEXT NOT NULL,
  payload      JSONB,
  cost_usd     FLOAT DEFAULT 0,
  success      BOOLEAN DEFAULT TRUE,
  error_msg    TEXT,
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS events_agent_action
  ON events(agent, action, created_at DESC);

CREATE INDEX IF NOT EXISTS events_lead
  ON events(lead_id, created_at DESC);

-- ─────────────────────────────────────────────
-- SEQUENCES  (active drip sequence tracker)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sequences (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id         UUID REFERENCES leads(id) ON DELETE CASCADE,
  sequence_type   TEXT NOT NULL,
  -- email_5step | pre_call | post_call_followup | not_now_drip | onboarding
  current_step    INTEGER DEFAULT 1,
  total_steps     INTEGER NOT NULL,
  next_send_at    TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,
  paused          BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sequences_next_send
  ON sequences(next_send_at) WHERE completed_at IS NULL AND paused = FALSE;

-- ─────────────────────────────────────────────
-- SYSTEM_METRICS  (weekly performance snapshots)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_metrics (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  week_start          DATE NOT NULL UNIQUE,
  leads_scored        INTEGER DEFAULT 0,
  hot_leads           INTEGER DEFAULT 0,
  emails_sent         INTEGER DEFAULT 0,
  open_rate_pct       FLOAT,
  reply_rate_pct      FLOAT,
  interested_replies  INTEGER DEFAULT 0,
  calls_booked        INTEGER DEFAULT 0,
  calls_completed     INTEGER DEFAULT 0,
  deals_won           INTEGER DEFAULT 0,
  mrr_added_usd       FLOAT DEFAULT 0,
  total_api_cost_usd  FLOAT DEFAULT 0,
  created_at          TIMESTAMPTZ DEFAULT now()
);
