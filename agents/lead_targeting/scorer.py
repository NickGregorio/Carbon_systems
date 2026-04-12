import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent_runner import BaseAgent

class LeadScorerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='lead_scorer')

    def run(self):
        self.logger.info("Starting AI Lead Scorer...")
        
        if not os.getenv('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY').startswith('sk-ant-...'):
            self.logger.warning("ANTHROPIC_API_KEY not configured. Skipping Scorer.")
            return
            
        # Select leads that have contacts but no total score yet
        response = self.supabase.table('leads').select('*').not_('contact_email', 'is', 'null').is_('total_score', 'null').execute()
        unscored_leads = response.data or []
        
        if not unscored_leads:
            self.logger.info("No leads pending scores.")
            return
            
        prompt_template = """
        You are a lead scoring specialist for an AI automation agency.
        Given this enriched business record, score the lead's investment readiness.

        Business record:
        {lead_json}

        Output ONLY valid JSON with these fields:
        {{
          "pain_score": <0-100>,
          "financial_score": <0-100>,
          "timing_score": <0-100>,
          "digital_score": <0-100>,
          "total_score": <weighted composite integer>,
          "tier": <"hot"|"warm"|"cold">,
          "pitch_angle": "<one sentence: the specific pain point most likely to resonate>"
        }}

        Scoring criteria (Be analytical):
        - pain_score: manual/paper workflows=80+, job postings for ops roles=70+, no CRM detected=75+, high review volume with no booking widget=65+
        - financial_score: 10-50 employees=70+, 50-200 reviews=65+, 10+ year old business=60+, growth signals in job postings=70+
        - digital_score: pre-2019 website=70+, no booking widget=80+, no SSL=60+, modern site with gaps=40
        """

        for lead in unscored_leads:
            lead_id = lead['id']
            company = lead['company_name']
            self.logger.info(f"AI Scoring for: {company}")
            
            # Remove giant fields or unnecessary items from JSON context to save Claude tokens
            lead_context = {k: v for k, v in lead.items() if k not in ['created_at', 'updated_at', 'id']}
            
            try:
                result = self.call_claude_json(
                    prompt=prompt_template.format(lead_json=json.dumps(lead_context)),
                    model_key='haiku',
                    action_name='lead_scoring',
                    lead_id=lead_id
                )
                
                # Update database with resulting scores and pitch
                self.update('leads', lead_id, {
                    'pain_score': result.get('pain_score', 0),
                    'financial_score': result.get('financial_score', 0),
                    'timing_score': result.get('timing_score', 50), # Mock fallback
                    'digital_score': result.get('digital_score', 0),
                    'total_score': result.get('total_score', 0),
                    'tier': result.get('tier', 'cold'),
                    'pitch_angle': result.get('pitch_angle', '')
                })
                
                self.logger.info(f"[{result.get('tier').upper()}] {company} Scored: {result.get('total_score')} | Hook: {result.get('pitch_angle')}")

            except Exception as e:
                self.logger.error(f"Scoring failed for {company}: {e}")

if __name__ == '__main__':
    LeadScorerAgent().execute()
