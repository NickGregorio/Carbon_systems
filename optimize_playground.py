import requests
import json

# Configuration
N8N_BASE_URL = "http://n8n-zmtggl3trsftwkofhzm3vhs6.34.29.252.42.sslip.io/api/v1"
N8N_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhNDFmYTNmMi0zZmFkLTQwNmMtYjI5YS02Yzk4NGZlM2NiZTMiLCJpc3MiOiJuOG4iLCJhdWQiOiBwdWJsaWMtYXBpIiwianRpIjoiYTVlODI1NzQtNGI4MC00YzhmLWE3MWMtMzQ1ODU2MTgxZjJhIiwiaWF0IjoxNzc2MTM5MDg4fQ.ELz-3sL4yvwB3Vtq1ddhK9W3HAh3T8tGq16294uVMA4"
PLAYGROUND_WF_ID = "yjTqYTXLphYPA2rc"

HEADERS = {
    "X-N8N-API-KEY": N8N_TOKEN,
    "Content-Type": "application/json"
}

def optimize():
    # 1. Fetch current credential IDs
    creds_res = requests.get(f"{N8N_BASE_URL}/credentials", headers=HEADERS)
    if creds_res.status_code != 200:
        print(f"Error fetching credentials: {creds_res.text}")
        return
    
    data = creds_res.json()
    if 'data' not in data:
        print(f"Unexpected response format: {data}")
        return
    creds = data['data']
    
    maps_cred_id = None
    sheets_cred_id = "Zce5v6FCpfuGu6sw" # We know this from earlier
    
    for c in creds:
        if c['type'] == 'httpHeaderAuth':
            maps_cred_id = c['id']
            break
            
    if not maps_cred_id:
        print("Error: Could not find Header Auth credential for Maps API.")
        return

    # 2. Fetch the playground workflow
    wf_res = requests.get(f"{N8N_BASE_URL}/workflows/{PLAYGROUND_WF_ID}", headers=HEADERS)
    wf = wf_res.json()
    
    nodes = wf['nodes']
    
    # 3. Modify Nodes
    for node in nodes:
        # a. Cleanup Edit Fields
        if node['name'] == 'Edit Fields':
            assignments = node['parameters'].get('assignments', {}).get('assignments', [])
            node['parameters']['assignments']['assignments'] = [
                a for a in assignments if a['name'] not in ['Google_Maps_API']
            ]
            
        # b. Secure Geo Coding API
        if node['name'] == 'Geo Coding API':
            node['parameters']['authentication'] = 'genericCredentialType'
            node['parameters']['genericAuthType'] = 'httpHeaderAuth'
            node['credentials'] = {'httpHeaderAuth': {'id': maps_cred_id}}
            # Remove hardcoded key query param
            params = node['parameters'].get('queryParameters', {}).get('parameters', [])
            node['parameters']['queryParameters']['parameters'] = [
                p for p in params if p['name'] != 'key'
            ]
            
        # c. Secure Google Places API (and variants)
        if 'Google Places API' in node['name']:
            node['parameters']['authentication'] = 'genericCredentialType'
            node['parameters']['genericAuthType'] = 'httpHeaderAuth'
            node['credentials'] = {'httpHeaderAuth': {'id': maps_cred_id}}
            # Remove hardcoded header
            params = node['parameters'].get('headerParameters', {}).get('parameters', [])
            node['parameters']['headerParameters']['parameters'] = [
                p for p in params if p['name'] != 'X-Goog-Api-Key'
            ]
            
        # d. Ensure Google Sheets nodes use the correct credential
        if 'googleSheets' in node['type']:
            node['credentials'] = {'googleSheetsOAuth2Api': {'id': sheets_cred_id}}

    # 4. Push Update
    # For PUT we need to send name, nodes, connections, settings
    payload = {
        "name": wf['name'],
        "nodes": nodes,
        "connections": wf['connections'],
        "settings": wf['settings']
    }
    
    # Clean settings as per internal API rules
    allowed_settings = ["errorWorkflow", "timezone", "saveExecutionProgress", "saveManualExecutions", "saveDataErrorExecution", "saveDataSuccessExecution", "executionTimeout", "callerPolicy"]
    payload['settings'] = {k: v for k, v in wf['settings'].items() if k in allowed_settings}

    update_res = requests.put(f"{N8N_BASE_URL}/workflows/{PLAYGROUND_WF_ID}", headers=HEADERS, json=payload)
    if update_res.status_code == 200:
        print("Workflow Optimized Successfully!")
    else:
        print(f"Error updating workflow: {update_res.text}")

if __name__ == "__main__":
    optimize()
