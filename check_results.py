import os
import sys
import json
from agent_runner import BaseAgent

class ResultChecker(BaseAgent):
    def __init__(self):
        super().__init__(name='result_checker')

    def run(self):
        res = self.supabase.table('regions').select('*').order('total', desc=True).limit(5).execute()
        print("\nTOP OPPORTUNITY REGIONS:")
        print("=" * 60)
        for r in res.data:
            print(f"[{r['id'].upper()}] {r['name']:<15} | Score: {r['total']} | Economic: {r['economic']} | Industry: {r['industry_fit']}")
        print("=" * 60)

if __name__ == '__main__':
    ResultChecker().run()
