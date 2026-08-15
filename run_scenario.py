import json
from pathlib import Path
from evaluation.evaluate import ScenarioApiClient
from agent import Agent

scenarios = json.loads(Path('evaluation/scenarios.json').read_text())
scenario = next((s for s in scenarios if s.get('id') == 'happy_conversational_success'), None)
if scenario is None:
    raise SystemExit('Scenario not found')

client = ScenarioApiClient(scenario)
agent = Agent(api_client=client)
for m in scenario.get('messages', []):
    r = agent.next(m)
    print(r['message'])

print(client.payment_calls)
print(agent.state.state)
