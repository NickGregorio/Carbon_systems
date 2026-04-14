import requests
import json

# Configuration
N8N_BASE_URL = "http://n8n-zmtggl3trsftwkofhzm3vhs6.34.29.252.42.sslip.io/api/v1"
N8N_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhNDFmYTNmMi0zZmFkLTQwNmMtYjI5YS02Yzk4NGZlM2NiZTMiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiYTVlODI1NzQtNGI4MC00YzhmLWE3MWMtMzQ1ODU2MTgxZjJhIiwiaWF0IjoxNzc2MTM5MDg4fQ.ELz-3sL4yvwB3Vtq1ddhK9W3HAh3T8tGq16294uVMA4"
PLAYGROUND_WF_ID = "yjTqYTXLphYPA2rc"

# Credential IDs provided by user / discovered
MAPS_CRED_ID = "3Xd9vr6mBGsLY71d"
SHEETS_CRED_ID = "Zce5v6FCpfuGu6sw"

HEADERS = {
    "X-N8N-API-KEY": N8N_TOKEN,
    "Content-Type": "application/json"
}

def optimize():
    print(f"Starting optimization for workflow {PLAYGROUND_WF_ID}...")
    
    # 1. Fetch the playground workflow
    wf_res = requests.get(f"{N8N_BASE_URL}/workflows/{PLAYGROUND_WF_ID}", headers=HEADERS)
    wf_res.raise_for_status()
    wf = wf_res.json()
    
    nodes = wf['nodes']
    
    # 2. Modify Nodes
    for node in nodes:
        # a. Cleanup Edit Fields (Remove sensitive keys)
        if node['name'] == 'Edit Fields' or node['name'] == 'Edit Fields1':
            if 'assignments' in node['parameters'] and 'assignments' in node['parameters']['assignments']:
                assignments = node['parameters']['assignments']['assignments']
                node['parameters']['assignments']['assignments'] = [
                    a for a in assignments if a['name'] not in ['Google_Maps_API']
                ]
            
        # b. Secure Geo Coding API (Use credential instead of hardcoded key)
        if node['name'] == 'Geo Coding API':
            print("Securing Geo Coding API node...")
            node['parameters']['authentication'] = 'genericCredentialType'
            node['parameters']['genericAuthType'] = 'httpHeaderAuth'
            node['credentials'] = {'httpHeaderAuth': {'id': MAPS_CRED_ID}}
            # Remove hardcoded 'key' query param and use the credential's header instead
            if 'queryParameters' in node['parameters'] and 'parameters' in node['parameters']['queryParameters']:
                params = node['parameters']['queryParameters']['parameters']
                node['parameters']['queryParameters']['parameters'] = [
                    p for p in params if p['name'] != 'key'
                ]
            
        # c. Secure Google Places API (and variants)
        if 'Google Places API' in node['name']:
            print(f"Securing {node['name']} node...")
            node['parameters']['authentication'] = 'genericCredentialType'
            node['parameters']['genericAuthType'] = 'httpHeaderAuth'
            node['credentials'] = {'httpHeaderAuth': {'id': MAPS_CRED_ID}}
            # Remove hardcoded X-Goog-Api-Key header
            if 'headerParameters' in node['parameters'] and 'parameters' in node['parameters']['headerParameters']:
                params = node['parameters']['headerParameters']['parameters']
                node['parameters']['headerParameters']['parameters'] = [
                    p for p in params if p['name'] != 'X-Goog-Api-Key'
                ]
            
        # d. Ensure Google Sheets nodes use the correct credential
        if 'googleSheets' in node['type']:
            print(f"Updating credential for {node['name']}...")
            node['credentials'] = {'googleSheetsOAuth2Api': {'id': SHEETS_CRED_ID}}

    # 3. Push Update
    payload = {
        "name": wf['name'],
        "nodes": nodes,
        "connections": wf['connections'],
        "settings": wf['settings']
    }
    
    # Clean settings for API compatibility
    allowed_settings = ["errorWorkflow", "timezone", "saveExecutionProgress", "saveManualExecutions", "saveDataErrorExecution", "saveDataSuccessExecution", "executionTimeout", "callerPolicy"]
    payload['settings'] = {k: v for k, v in wf['settings'].items() if k in allowed_settings}

    update_res = requests.put(f"{N8N_BASE_URL}/workflows/{PLAYGROUND_WF_ID}", headers=HEADERS, json=payload)
    if update_res.status_code == 200:
        print("Optimization Complete! The AI version is now secure and uses your unified credentials.")
    else:
        print(f"Error updating workflow: {update_res.text}")

if __name__ == "__main__":
    optimize()
