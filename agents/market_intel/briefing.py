import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent_runner import BaseAgent

class WeeklyBriefingAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='weekly_briefing')

    def run(self):
        self.logger.info("Generating weekly market intelligence briefing...")
        
        # We need Anthropic key for this script.
        if not os.getenv('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY').startswith('sk-ant-...'):
            self.logger.warning("ANTHROPIC_API_KEY not configured. Skipping Briefing Generation.")
            return
            
        # Get top 3 regions ordered by total score descending
        response = self.supabase.table('regions').select('*').order('total', desc=True).limit(3).execute()
        top_regions = response.data or []
        
        if not top_regions:
            self.logger.warning("No regions scored yet. Run scorer.py first. Skipping report generation.")
            return

        regions_context = json.dumps(top_regions, indent=2)
        
        prompt = f"""
        You are the Market Intelligence Analyst for an AI automation agency targeting US businesses.
        Synthesize this region data into a concise, professional weekly Markdown brief.

        Top Regions Data:
        {regions_context}

        Format exactly like this:
        # Weekly Market Intelligence Briefing
        
        ## Top Opportunity Window
        [1 paragraph analyzing the very top region, its total score, and why it's the target this week based on the numbers retrieved]
        
        ## Runners Up
        - **[Region 2]**: Score XX - [One sentence reasoning]
        - **[Region 3]**: Score XX - [One sentence reasoning]
        
        ## Recommended Next Action
        [One sentence clear instruction to the Lead Targeting agent on what region to process next]
        """

        try:
            briefing_md = self.call_claude(
                prompt=prompt,
                model_key='sonnet',
                system="You are a brilliant market analysts summarizing complex structured data into concise reports.",
                action_name='generate_briefing'
            )
            
            # For iteration context, output it locally entirely for review instead of triggering Instantly emails
            brief_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'latest_briefing.md'))
            with open(brief_path, 'w', encoding='utf-8') as f:
                f.write(briefing_md)
                
            self.logger.info(f"Briefing generation succeeded. Output safely written to {brief_path}")
            
            self._log_event(
                action='briefing_generated',
                payload={'target_path': brief_path}
            )
            
        except Exception as e:
            self.logger.error(f"Failed to generate briefing: {e}")

if __name__ == '__main__':
    WeeklyBriefingAgent().execute()
