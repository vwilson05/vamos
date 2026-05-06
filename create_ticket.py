import os
import json
import base64
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_ado_ticket():
    # Get configuration from environment
    org_url = os.getenv("ADO_ORG_URL").rstrip('/')
    project = os.getenv("ADO_PROJECT")
    pat = os.getenv("ADO_PAT")
    user_email = os.getenv("ADO_USER_EMAIL")

    # Set up authentication
    auth_str = f':{pat}'
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {
        'Content-Type': 'application/json-patch+json',
        'Authorization': f'Basic {b64_auth}'
    }

    # Define the work item fields
    title = "PR Review and Deployment Northstrar rules"
    description = "Review PR and deploy to PROD: https://dev.azure.com/HaloMDLLC/Data%20Platform/_git/dbt-halomd/pullrequest/9028 which is for story 29020"

    # Create the work item patch document
    patch_document = [
        {
            "op": "add",
            "path": "/fields/System.Title",
            "value": title
        },
        {
            "op": "add",
            "path": "/fields/System.Description",
            "value": description
        },
        {
            "op": "add",
            "path": "/fields/System.AssignedTo",
            "value": user_email
        },
        {
            "op": "add",
            "path": "/fields/System.Tags",
            "value": "PR Review; Deployment"
        }
    ]

    # Construct the API URL for creating a work item (Task)
    api_url = f"{org_url}/{project}/_apis/wit/workitems/$Task?api-version=7.0"

    try:
        # Make the API request
        response = requests.post(api_url, json=patch_document, headers=headers)
        response.raise_for_status()

        # Parse the response
        work_item = response.json()
        work_item_id = work_item.get('id')

        # Construct the URL to the work item
        work_item_url = f"{org_url}/{project}/_workitems/edit/{work_item_id}"

        print(f"[SUCCESS] Successfully created work item #{work_item_id}")
        print(f"[TITLE] {title}")
        print(f"[ASSIGNED TO] {user_email}")
        print(f"[LINK] {work_item_url}")

        return work_item_url

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error creating work item: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None

if __name__ == "__main__":
    url = create_ado_ticket()
    if url:
        print(f"\n[COMPLETE] Work item created successfully!")