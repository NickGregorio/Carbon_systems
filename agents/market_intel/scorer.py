import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent_runner import BaseAgent

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

class MarketIntelScorer(BaseAgent):
    def __init__(self):
        super().__init__(name='market_intel_scorer')

    def run(self):
        self.logger.info("Starting Market Intelligence scoring...")
        
        # Calculate time window for "recent" signals (e.g., last 7 days)
        one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        
        response = self.supabase.table('signals').select('*').gte('fetched_at', one_week_ago).execute()
        signals = response.data or []
        
        # Group signals by region
        from collections import defaultdict
        region_signals = defaultdict(list)
        for s in signals:
            if s.get('region_id'):
                region_signals[s['region_id']].append(s)

        for region_id, info in REGIONS.items():
            self.logger.info(f"Scoring region: {region_id}")
            
            # Sub-scores (0-100 defaults)
            seasonal_score = 50   
            economic_score = 50   
            news_score = 50       
            
            # Analyze region signals to adjust baseline
            r_signals = region_signals.get(region_id, [])
            for sig in r_signals:
                source = sig.get('source')
                val = sig.get('value', 0)
                
                if source == 'fred':
                    # Example evaluation: unemployment rate above 4.0% adds to the economic readiness score 
                    if val > 4.0:
                        economic_score = min(100, economic_score + 5)
                elif source == 'noaa':
                    seasonal_score = min(100, seasonal_score + 10)
                elif source == 'news':
                    tag = sig.get('signal_type', '')
                    if tag in ['business_expansion', 'disaster_recovery']:
                        news_score = min(100, news_score + 20)
                    elif tag == 'labor_shortage':
                        news_score = min(100, news_score + 15)

            # Aggregate according to CLAUDE.md specification
            industry_fit = info['industry_fit']
            total = (
                seasonal_score * 0.25 +
                economic_score * 0.25 +
                news_score     * 0.20 +
                industry_fit   * 0.30
            )
            
            total_int = int(round(total))
            
            # Upsert updated scores into regions table structure
            self.upsert('regions', {
                'id': region_id,
                'name': info['name'],
                'states': info['states'],
                'seasonal': seasonal_score,
                'economic': economic_score,
                'news': news_score,
                'industry_fit': industry_fit,
                'total': total_int,
                'trigger_text': f"Latest composite target based on {len(r_signals)} trailing signals.",
                'scored_at': datetime.now(timezone.utc).isoformat()
            })
            
            self._log_event(
                action='region_scored',
                region_id=region_id,
                payload={'total_score': total_int, 'signal_count': len(r_signals)}
            )

        self.logger.info("Market Intelligence scoring phase complete.")

if __name__ == '__main__':
    MarketIntelScorer().execute()
