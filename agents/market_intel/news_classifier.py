import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from agent_runner import BaseAgent

class NewsClassifierAgent(BaseAgent):
    def __init__(self):
        super().__init__(name='news_classifier')
        # Hardcoded sample news for early Phase 2 testing. Later swapped with RSS feed fetch.
        self.sample_headlines = [
            ("sct", "Texas manufacturer invests $50M in new facility expansion."),
            ("seu", "Hurricane recovery efforts stall in Florida due to contractor shortages."),
            ("pac", "California adopts new strict emissions tracking regulations for HVAC companies.")
        ]

    def run(self):
        # We need Anthropic key for this script.
        if not os.getenv('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY').startswith('sk-ant-...'):
            self.logger.warning("ANTHROPIC_API_KEY not configured. Skipping News Classification.")
            return

        prompt_template = """
        Classify this news article into exactly one tag.
        Article: {headline}

        Output ONLY valid JSON:
        {{
            "tag": "<disaster_recovery|business_expansion|labor_shortage|regulatory_change|industry_disruption|noise>"
        }}
        """

        for region_id, headline in self.sample_headlines:
            self.logger.info(f"Classifying news for {region_id}...")
            try:
                result = self.call_claude_json(
                    prompt=prompt_template.format(headline=headline),
                    model_key='haiku',
                    action_name='classify_news'
                )
                
                tag = result.get('tag', 'noise')
                self.logger.info(f"Result: {tag}")
                
                if tag != 'noise':
                    self.insert('signals', {
                        'region_id': region_id,
                        'source': 'news',
                        'signal_type': tag,
                        'value': 1.0,
                        'raw_json': {'headline': headline, 'tag': tag}
                    })
            except Exception as e:
                self.logger.error(f"Error classifying news: {e}")

if __name__ == '__main__':
    NewsClassifierAgent().execute()
