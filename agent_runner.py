"""
agent_runner.py
───────────────
Base agent execution loop. All agents in this system inherit from BaseAgent.

Usage:
    class MyAgent(BaseAgent):
        def run(self):
            # your agent logic here
            pass

    if __name__ == '__main__':
        MyAgent(name='my_agent').execute()
"""

import os
import json
import time
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import anthropic
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ─────────────────────────────────────────────
# Model routing — matches CLAUDE.md spec
# ─────────────────────────────────────────────
MODEL = {
    'haiku':  'claude-haiku-4-5-20251001',
    'sonnet': 'claude-sonnet-4-6',
}

# Approximate cost per 1M tokens (input/output) for budget tracking
TOKEN_COST = {
    'claude-haiku-4-5-20251001':  {'input': 0.80,  'output': 4.00},
    'claude-sonnet-4-6':          {'input': 3.00,  'output': 15.00},
}


class BaseAgent:
    """
    Base class for all system agents. Provides:
    - Supabase client
    - Anthropic client
    - Structured logging to events table
    - Cost tracking
    - Slack alerting on failure
    - Graceful error handling
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self.run_cost_usd = 0.0
        self.run_start = datetime.now(timezone.utc)

        # Clients
        self.supabase: Client = create_client(
            os.environ['SUPABASE_URL'],
            os.environ['SUPABASE_SERVICE_KEY']
        )
        self.anthropic = anthropic.Anthropic(
            api_key=os.environ['ANTHROPIC_API_KEY']
        )

    # ─────────────────────────────────────────
    # Claude API helpers
    # ─────────────────────────────────────────

    def call_claude(
        self,
        prompt: str,
        model_key: str = 'haiku',
        system: str = 'You are a helpful AI assistant.',
        max_tokens: int = 1000,
        action_name: str = 'claude_call',
        lead_id: Optional[str] = None,
        region_id: Optional[str] = None,
    ) -> str:
        """
        Call Claude API, track cost, log to events table.
        Returns the text content of the response.
        """
        model_id = MODEL[model_key]
        start = time.time()

        try:
            response = self.anthropic.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                system=system,
                messages=[{'role': 'user', 'content': prompt}]
            )
        except Exception as e:
            self.logger.error(f'Claude API error ({action_name}): {e}')
            self._alert(f'Claude API error in {self.name}/{action_name}: {e}')
            raise

        # Cost tracking
        input_tokens  = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        rates = TOKEN_COST[model_id]
        cost = (input_tokens / 1_000_000 * rates['input'] +
                output_tokens / 1_000_000 * rates['output'])
        self.run_cost_usd += cost

        elapsed = round(time.time() - start, 2)
        self.logger.info(
            f'{action_name} — {model_id} — '
            f'{input_tokens}in/{output_tokens}out — '
            f'${cost:.5f} — {elapsed}s'
        )

        # Log to events
        self._log_event(
            action=action_name,
            lead_id=lead_id,
            region_id=region_id,
            payload={
                'model': model_id,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'elapsed_s': elapsed,
            },
            cost_usd=cost
        )

        text = response.content[0].text
        return text

    def call_claude_json(
        self,
        prompt: str,
        model_key: str = 'haiku',
        system: str = 'Output only valid JSON. No markdown, no explanation.',
        max_tokens: int = 1000,
        action_name: str = 'claude_json_call',
        lead_id: Optional[str] = None,
        region_id: Optional[str] = None,
    ) -> dict:
        """
        Call Claude expecting JSON output. Parses and returns dict.
        Retries once on parse failure.
        """
        for attempt in range(2):
            raw = self.call_claude(
                prompt=prompt,
                model_key=model_key,
                system=system,
                max_tokens=max_tokens,
                action_name=action_name,
                lead_id=lead_id,
                region_id=region_id,
            )
            # Strip markdown code fences if present
            clean = raw.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError:
                if attempt == 0:
                    self.logger.warning(f'JSON parse failed, retrying: {clean[:100]}')
                    continue
                self.logger.error(f'JSON parse failed after retry: {clean[:200]}')
                raise ValueError(f'Could not parse Claude response as JSON: {clean[:200]}')

    # ─────────────────────────────────────────
    # Supabase helpers
    # ─────────────────────────────────────────

    def upsert(self, table: str, data: dict, conflict_column: str = 'id') -> dict:
        """Upsert a record. Returns the upserted row."""
        result = (
            self.supabase.table(table)
            .upsert(data, on_conflict=conflict_column)
            .execute()
        )
        return result.data[0] if result.data else {}

    def insert(self, table: str, data: dict) -> dict:
        """Insert a record. Returns the inserted row."""
        result = self.supabase.table(table).insert(data).execute()
        return result.data[0] if result.data else {}

    def select(self, table: str, filters: dict = None, limit: int = 1000) -> list:
        """Select records with optional equality filters."""
        query = self.supabase.table(table).select('*')
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        result = query.limit(limit).execute()
        return result.data or []

    def update(self, table: str, row_id: str, data: dict) -> dict:
        """Update a record by id."""
        result = (
            self.supabase.table(table)
            .update(data)
            .eq('id', row_id)
            .execute()
        )
        return result.data[0] if result.data else {}

    def _log_event(
        self,
        action: str,
        lead_id: Optional[str] = None,
        region_id: Optional[str] = None,
        payload: dict = None,
        cost_usd: float = 0.0,
        success: bool = True,
        error_msg: Optional[str] = None,
    ):
        """Append an event to the events table."""
        try:
            self.supabase.table('events').insert({
                'lead_id':    lead_id,
                'region_id':  region_id,
                'agent':      self.name,
                'action':     action,
                'payload':    payload or {},
                'cost_usd':   round(cost_usd, 6),
                'success':    success,
                'error_msg':  error_msg,
            }).execute()
        except Exception as e:
            # Never crash the agent over a logging failure
            self.logger.warning(f'Event logging failed: {e}')

    # ─────────────────────────────────────────
    # Alerting
    # ─────────────────────────────────────────

    def _alert(self, message: str):
        """Send a Slack alert. Fails silently if webhook not configured."""
        webhook = os.getenv('SLACK_WEBHOOK_URL')
        if not webhook:
            return
        try:
            import urllib.request
            payload = json.dumps({
                'text': f':warning: *{self.name}* — {message}'
            }).encode('utf-8')
            req = urllib.request.Request(
                webhook,
                data=payload,
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # Alert failure must never crash the agent

    # ─────────────────────────────────────────
    # Execution wrapper
    # ─────────────────────────────────────────

    def run(self):
        """Override this method in each agent subclass."""
        raise NotImplementedError('Subclasses must implement run()')

    def execute(self):
        """
        Top-level entry point. Wraps run() with timing, cost summary,
        error handling, and run-completion event logging.
        """
        self.logger.info(f'Starting {self.name}')
        self.run_start = datetime.now(timezone.utc)
        self.run_cost_usd = 0.0

        try:
            self.run()
            elapsed = (datetime.now(timezone.utc) - self.run_start).total_seconds()
            self.logger.info(
                f'{self.name} completed in {elapsed:.1f}s — '
                f'total cost: ${self.run_cost_usd:.4f}'
            )
            self._log_event(
                action='run_complete',
                payload={
                    'elapsed_s': round(elapsed, 1),
                    'total_cost_usd': round(self.run_cost_usd, 4),
                }
            )
            # Cost alert check
            daily_limit = float(os.getenv('COST_ALERT_DAILY_USD', '5.00'))
            if self.run_cost_usd > daily_limit:
                self._alert(
                    f'Cost alert: single run cost ${self.run_cost_usd:.2f} '
                    f'(limit ${daily_limit})'
                )

        except Exception as e:
            tb = traceback.format_exc()
            self.logger.error(f'{self.name} failed: {e}\n{tb}')
            self._log_event(
                action='run_failed',
                payload={'traceback': tb[:2000]},
                success=False,
                error_msg=str(e)
            )
            self._alert(f'Agent failed: {str(e)[:200]}')
            raise


# ─────────────────────────────────────────────
# Utility: validate environment
# ─────────────────────────────────────────────

REQUIRED_ENV_VARS = [
    'ANTHROPIC_API_KEY',
    'SUPABASE_URL',
    'SUPABASE_SERVICE_KEY',
]

PHASE_ENV_VARS = {
    2: ['NOAA_API_KEY', 'FRED_API_KEY'],
    3: ['APOLLO_API_KEY', 'GOOGLE_MAPS_API_KEY', 'RAPIDAPI_KEY'],
    4: ['INSTANTLY_API_KEY'],
    5: ['WAALAXY_API_KEY'],
    6: ['GHL_API_KEY', 'GHL_LOCATION_ID', 'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN', 'TWILIO_FROM_NUMBER'],
}


def validate_env(phase: int = 1) -> bool:
    """
    Check all required environment variables are present for the given phase.
    Logs missing vars and returns False if any are absent.
    """
    logger = logging.getLogger('env_validator')
    required = list(REQUIRED_ENV_VARS)
    for p in range(2, phase + 1):
        required.extend(PHASE_ENV_VARS.get(p, []))

    missing = [k for k in required if not os.getenv(k)]
    if missing:
        for k in missing:
            logger.error(f'Missing required env var: {k}')
        return False

    logger.info(f'All {len(required)} environment variables present for phase {phase}')
    return True


if __name__ == '__main__':
    """
    Smoke test: validate env vars + write a test event to Supabase.
    Run: python agent_runner.py
    """
    if not validate_env(phase=1):
        print('Environment validation failed. Check .env file.')
        exit(1)

    class SmokeTestAgent(BaseAgent):
        def run(self):
            self.logger.info('Running smoke test...')
            # Write a test event
            self._log_event(
                action='smoke_test',
                payload={'message': 'Agent runner is working correctly'},
            )
            self.logger.info('Smoke test passed — event written to Supabase.')

    SmokeTestAgent(name='smoke_test').execute()
    print('\nPhase 1 validation gate 3: PASSED')
    print('agent_runner.py is working. Supabase connection confirmed.')
