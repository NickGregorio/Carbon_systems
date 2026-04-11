import os
import requests
import sys

# Ensure parent directory is in path to import agent_runner
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent_runner import BaseAgent

REGIONS = {
    'sct': ['TX', 'LA', 'OK', 'AR'],
    'seu': ['FL', 'GA', 'NC', 'SC'],
    'mda': ['NY', 'NJ', 'PA', 'MD'],
    'pac': ['CA', 'OR', 'WA'],
    'swt': ['AZ', 'NV', 'NM', 'UT'],
    'glk': ['MI', 'OH', 'IL', 'WI'],
    'nen': ['MA', 'CT', 'ME', 'VT'],
    'npl': ['MN', 'IA', 'NE', 'ND'],
    'mtn': ['CO', 'MT', 'ID', 'WY'],
}

class FredPullerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='fred_puller')
        self.api_key = os.getenv('FRED_API_KEY')
        self.base_url = 'https://api.stlouisfed.org/fred/series/observations'

    def run(self):
        if not self.api_key or self.api_key.startswith('your_') or self.api_key == '...':
            self.logger.warning("FRED_API_KEY not configured. Skipping FRED pull.")
            return

        for region_id, states in REGIONS.items():
            for state in states:
                series_id = f"{state}UR"  # Unemployment Rate by State
                self.logger.info(f"Fetching {series_id} for region {region_id}")
                
                try:
                    response = requests.get(
                        self.base_url,
                        params={
                            'series_id': series_id,
                            'api_key': self.api_key,
                            'file_type': 'json',
                            'limit': 1,
                            'sort_order': 'desc'
                        }
                    )
                    data = response.json()
                    
                    if 'observations' in data and data['observations']:
                        latest_obs = data['observations'][0]
                        value = float(latest_obs['value'])
                        
                        # Insert into signals table securely
                        self.insert('signals', {
                            'region_id': region_id,
                            'source': 'fred',
                            'signal_type': 'unemployment_rate',
                            'value': value,
                            'raw_json': latest_obs
                        })
                        self._log_event(
                            action='pulled_fred_signal',
                            region_id=region_id,
                            payload={'state': state, 'value': value}
                        )
                except Exception as e:
                    self.logger.error(f"Error fetching data for {state}: {e}")

if __name__ == '__main__':
    FredPullerAgent().execute()
