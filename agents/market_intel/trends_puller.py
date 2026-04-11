import os
import requests
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent_runner import BaseAgent

REGIONS = {
    'sct': 'US-TX', # Simplified mapping to largest state for trends proxy
    'seu': 'US-FL',
    'mda': 'US-NY',
    'pac': 'US-CA',
    'swt': 'US-AZ',
    'glk': 'US-IL',
    'nen': 'US-MA',
    'npl': 'US-MN',
    'mtn': 'US-CO',
}

class TrendsPullerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='trends_puller')
        self.api_key = os.getenv('SERPAPI_KEY')
        self.base_url = 'https://serpapi.com/search'

    def run(self):
        if not self.api_key or self.api_key.startswith('your_') or self.api_key == '...':
            self.logger.warning("SERPAPI_KEY not configured. Skipping Trends pull.")
            return

        for region_id, geo in REGIONS.items():
            self.logger.info(f"Fetching Google Trends for region {region_id}")
            try:
                params = {
                    "engine": "google_trends",
                    "q": "AI automation, process automation",
                    "geo": geo,
                    "api_key": self.api_key
                }
                response = requests.get(self.base_url, params=params)
                data = response.json()
                
                # In production, parse timeline data. Logging raw json for Phase 2 validation.
                self.insert('signals', {
                    'region_id': region_id,
                    'source': 'trends',
                    'signal_type': 'search_interest',
                    'value': 1.0, # Placeholder until deep parsing
                    'raw_json': data.get('interest_over_time', {})
                })
                self._log_event(
                    action='pulled_trends_signal',
                    region_id=region_id,
                    payload={'geo': geo}
                )
            except Exception as e:
                self.logger.error(f"Error fetching trends for {region_id}: {e}")

if __name__ == '__main__':
    TrendsPullerAgent().execute()
