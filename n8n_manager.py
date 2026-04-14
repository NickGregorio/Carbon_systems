import requests
import json
import sys
import os

# Configuration
N8N_BASE_URL = "http://n8n-zmtggl3trsftwkofhzm3vhs6.34.29.252.42.sslip.io/api/v1"
# This is the new public-api token provided by the user
N8N_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhNDFmYTNmMi0zZmFkLTQwNmMtYjI5YS02Yzk4NGZlM2NiZTMiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiYTVlODI1NzQtNGI4MC00YzhmLWE3MWMtMzQ1ODU2MTgxZjJhIiwiaWF0IjoxNzc2MTM5MDg4fQ.ELz-3sL4yvwB3Vtq1ddhK9W3HAh3T8tGq16294uVMA4"

HEADERS = {
    "X-N8N-API-KEY": N8N_TOKEN,
    "Content-Type": "application/json"
}

def get_workflow(workflow_id):
    """Fetch a workflow by ID."""
    url = f"{N8N_BASE_URL}/workflows/{workflow_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error fetching workflow: {response.text}")
    response.raise_for_status()
    return response.json()

def create_workflow(name, nodes, connections, settings=None):
    """Create a new workflow."""
    url = f"{N8N_BASE_URL}/workflows"
    
    # Filter settings to only include allowed properties
    allowed_settings = [
        "errorWorkflow", "timezone", "saveExecutionProgress", 
        "saveManualExecutions", "saveDataErrorExecution", 
        "saveDataSuccessExecution", "executionTimeout", "callerPolicy"
    ]
    clean_settings = {}
    if settings:
        clean_settings = {k: v for k, v in settings.items() if k in allowed_settings}

    payload = {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "settings": clean_settings
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code != 201:
        print(f"Error creating workflow: {response.text}")
    response.raise_for_status()
    return response.json()

def update_workflow(workflow_id, data):
    """Update an existing workflow."""
    # n8n PUT /workflows/:id requires the full object but some fields like id/createdAt should be careful
    url = f"{N8N_BASE_URL}/workflows/{workflow_id}"
    response = requests.put(url, headers=HEADERS, json=data)
    response.raise_for_status()
    return response.json()

def list_workflows():
    """List all workflows."""
    url = f"{N8N_BASE_URL}/workflows"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python n8n_manager.py [list|get|copy] [id] [new_name]")
        sys.exit(1)

    cmd = sys.argv[1]
    
    if cmd == "list":
        result = list_workflows()
        print(json.dumps(result, indent=2))
    
    elif cmd == "get":
        wf_id = sys.argv[2]
        result = get_workflow(wf_id)
        print(json.dumps(result, indent=2))
        
    elif cmd == "copy":
        wf_id = sys.argv[2]
        new_name = sys.argv[3] if len(sys.argv) > 3 else "Copy of Workflow"
        
        # Get original
        original = get_workflow(wf_id)
        
        # Create new (only sending nodes and connections)
        result = create_workflow(
            new_name, 
            original.get('nodes', []), 
            original.get('connections', {}),
            original.get('settings', {})
        )
        print(f"Workflow copied successfully. New ID: {result.get('id')}")
        print(json.dumps(result, indent=2))
