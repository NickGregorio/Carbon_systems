import os
import sys
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent_runner import BaseAgent

class MapsFinderAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='maps_finder')
        # MOCK DATA for testing pipeline without Google Maps API keys
        self.mock_leads = [
            {'company_name': 'Apex HVAC Solutions', 'website': 'apexhvactx.com', 'phone': '555-0101', 'address': 'Austin, TX', 'google_rating': 4.7, 'google_review_cnt': 105, 'region_id': 'sct'},
            {'company_name': 'Southern Roof Masters', 'website': 'southernroofmasters.com', 'phone': '555-0102', 'address': 'Atlanta, GA', 'google_rating': 4.5, 'google_review_cnt': 63, 'region_id': 'seu'},
            {'company_name': 'Pacific Coast Logistics', 'website': 'paccoastlogistics.com', 'phone': '555-0103', 'address': 'Seattle, WA', 'google_rating': 4.2, 'google_review_cnt': 210, 'region_id': 'pac'}
        ]

    def run(self):
        self.logger.info("Starting Maps Finder (Using MOCK data)")
        
        for lead_data in self.mock_leads:
            self.logger.info(f"Inserting mock lead: {lead_data['company_name']}")
            try:
                # Use insert to create the new base lead in the database
                inserted = self.insert('leads', lead_data)
                lead_id = inserted.get('id')
                
                if lead_id:
                    self._log_event(
                        action='lead_sourced_maps',
                        lead_id=lead_id,
                        region_id=lead_data['region_id'],
                        payload={'company_name': lead_data['company_name'], 'mocked': True}
                    )
            except Exception as e:
                self.logger.error(f"Error inserting mock lead {lead_data['company_name']}: {e}")

if __name__ == '__main__':
    MapsFinderAgent().execute()
