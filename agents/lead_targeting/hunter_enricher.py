import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent_runner import BaseAgent

class HunterEnricherAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='hunter_enricher')
        
    def run(self):
        self.logger.info("Starting Hunter Enrichment (Using MOCK data)")
        
        # Grab leads that haven't been enriched yet (missing contact_email)
        response = self.supabase.table('leads').select('id, company_name').is_('contact_email', 'null').execute()
        unenriched_leads = response.data or []
        
        if not unenriched_leads:
            self.logger.info("No unenriched leads found.")
            return

        for lead in unenriched_leads:
            lead_id = lead['id']
            company = lead['company_name']
            self.logger.info(f"Enriching record: {company}")
            
            # MOCK response mimicking Hunter payloads based on company name
            mock_payload = {
                'contact_name': f"John ({company})",
                'contact_email': f"admin@{company.split()[0].lower()}.com",
                'contact_title': 'Owner / Operations Manager',
                'linkedin_url': f"linkedin.com/in/{company.split()[0].lower()}",
                'employee_count': '10-50',
                'revenue_range': '$1M-$5M'
            }
            
            try:
                self.update('leads', lead_id, mock_payload)
                self._log_event(
                    action='lead_enriched_hunter',
                    lead_id=lead_id,
                    payload={'mocked': True, 'email_found': True}
                )
            except Exception as e:
                self.logger.error(f"Error enriching lead {company}: {e}")

if __name__ == '__main__':
    HunterEnricherAgent().execute()
