import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent_runner import BaseAgent

class JobScannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='job_scanner')

    def run(self):
        self.logger.info("Starting Job Scanner (Using MOCK data)")
        
        # Find leads where job posting arrays haven't been touched 
        response = self.supabase.table('leads').select('id, company_name').is_('job_posting_flags', 'null').execute()
        leads = response.data or []
        
        if not leads:
            self.logger.info("No leads found pending job scan.")
            return
            
        for lead in leads:
            lead_id = lead['id']
            self.logger.info(f"Scanning boards for: {lead['company_name']}")
            
            # MOCK pain signals based on dummy indeed logic
            flags = []
            if "HVAC" in lead['company_name']:
                flags.append("dispatcher")
            elif "Logistics" in lead['company_name']:
                flags.append("scheduling coordinator")
            
            payload = {'job_posting_flags': flags}
            
            try:
                self.update('leads', lead_id, payload)
                self._log_event(
                    action='job_scan_complete',
                    lead_id=lead_id,
                    payload={'mocked': True, 'flags_found': len(flags)}
                )
            except Exception as e:
                self.logger.error(f"Error scanning jobs for {lead['company_name']}: {e}")

if __name__ == '__main__':
    JobScannerAgent().execute()
