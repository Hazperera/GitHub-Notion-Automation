import requests
import json
import os
from notion_client import Client
from dotenv import load_dotenv

# load environment variables
load_dotenv()

# environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
ORGANIZATION_NAME = os.getenv('ORGANIZATION_NAME')

# GitHub API, URL, headers
GITHUB_API_URL = "https://api.github.com"
TOKEN = GITHUB_TOKEN
ORGANIZATION = ORGANIZATION_NAME
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Notion API
DATABASE_ID = NOTION_DATABASE_ID
INTEGRATION_TOKEN = NOTION_TOKEN

# save repository data
OUTPUT_FILE = f'{ORGANIZATION}_github_org_repos.json'

#extract existing repositories from Notion
def get_existing_repositories_from_notion():
    notion = Client(auth=INTEGRATION_TOKEN)
    existing_repos = []
    has_more = True
    start_cursor = None
    while has_more:
        response = notion.databases.query(database_id=DATABASE_ID, start_cursor=start_cursor)
        has_more = response['has_more']
        start_cursor = response.get('next_cursor', None)
        for page in response['results']:
            name_property = page['properties'].get('RepositoryName', {}).get('title')
            if name_property:
                if name_property and 'plain_text' in name_property[0]:
                    repo_name = name_property[0]['plain_text']
                    existing_repos.append(repo_name)
                else:
                    print("No plain_text found in title for page:", page['id'])
            else:
                print("No 'name' title property found for page:", page['id'])
    return existing_repos

#get repositories (with pagination)
def get_org_repositories():
    repos = []
    page = 1
    per_page = 100
    while True:
        url = f"{GITHUB_API_URL}/orgs/{ORGANIZATION}/repos?page={page}&per_page={per_page}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break
        data = response.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos

#get repository admins
def get_repo_admins(repo_name):
    url = f"{GITHUB_API_URL}/repos/{ORGANIZATION}/{repo_name}/collaborators"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        collaborators = response.json()
        admins = [collab['login'] for collab in collaborators if collab.get('permissions', {}).get('admin', False)]
        return admins if admins else ["No Admin"]
    elif response.status_code == 403:
        print(f"Error fetching collaborators for {repo_name}: 403 (Forbidden)")
        return ["Access Denied: Insufficient permissions (403)"]
    else:
        print(f"Error fetching collaborators for {repo_name}: {response.status_code}")
        return [f"Failed to fetch admins: Error {response.status_code}"]

#get repository groups
def get_repo_teams(repo_name):
    url = f"{GITHUB_API_URL}/repos/{ORGANIZATION}/{repo_name}/teams"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        teams = response.json()
        team_names = [team['name'] for team in teams]
        return team_names if team_names else ["No Group"]
    elif response.status_code == 404:
        print(f"Error fetching teams for {repo_name}: 404 (Not Found)")
        return ["No Groups found (404)"]
    else:
        print(f"Error fetching teams for {repo_name}: {response.status_code}")
        return [f"Failed to fetch Groups: Error {response.status_code}"]

#extract repository information
def extract_repo_info(repo):
    admin_list = get_repo_admins(repo.get("name"))
    group_list = get_repo_teams(repo.get("name"))
    return {
        "RepositoryName": repo.get("name"),
        "LicenseInformation": repo.get("license", {}).get("name") if repo.get("license") else "No License",
        "Visibility": repo.get("visibility", "private"),
        "Admin": admin_list,
        "Group": group_list
    }

#resume from the last saved point
def load_existing_data():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as file:
            try:
                data = json.load(file)
                return data
            except json.JSONDecodeError:
                return []
    return []

#save repository information incrementally
def save_repository_info(repo_info_list):
    with open(OUTPUT_FILE, 'w') as file:
        json.dump(repo_info_list, file, indent=4)

#upload new repositories to Notion
def upload_to_notion(new_repo_info_list, existing_repos_in_notion):
    notion = Client(auth=INTEGRATION_TOKEN)
    for repo_info in new_repo_info_list:
        repo_name = repo_info["RepositoryName"]
        if repo_name in existing_repos_in_notion:
            print(f"Skipping {repo_info['RepositoryName']} as it already exists in Notion.")
            continue
        try:
            print("Attempting to upload:", repo_info['RepositoryName'])
            response = notion.pages.create(parent={"database_id": DATABASE_ID}, properties={
                "RepositoryName": {"title": [{"text": {"content": repo_info["RepositoryName"]}}]},
                "LicenseInformation": {"rich_text": [{"text": {"content": repo_info["LicenseInformation"]}}]},
                "Visibility": {"rich_text": [{"text": {"content": repo_info["Visibility"]}}]},
                "Admin": {"rich_text": [{"text": {"content": ', '.join(repo_info["Admin"])}}]},  # Admin now handled as text
                "Group": {"rich_text": [{"text": {"content": ', '.join(repo_info["Group"])}}]}  # Groups handled as comma-separated string
            })
            print("Uploaded {0} to Notion successfully.".format(repo_info['RepositoryName']))
            print("Response ID:", response.get("id"))
        except Exception as e:
            print("Error while uploading {0} to Notion: {1}".format(repo_info['RepositoryName'], e))
        time.sleep(1)

# fetch, process, and upload repositories
def get_org_repository_info():
    existing_repos_in_notion = get_existing_repositories_from_notion()
    print(f"Existing repositories in Notion: {existing_repos_in_notion}")
    github_repos = get_org_repositories()
    print(f"Total GitHub repositories fetched: {len(github_repos)}")

    existing_data = load_existing_data()
    processed_names = {repo["RepositoryName"] for repo in existing_data}  # Keep exact names
    repo_info_list = existing_data[:]
    new_repos = []

    for repo in github_repos:
        repo_info = extract_repo_info(repo)
        repo_name = repo_info["RepositoryName"]
        if repo_name not in processed_names and repo_name not in existing_repos_in_notion:
            repo_info_list.append(repo_info)
            new_repos.append(repo_info)
            save_repository_info(repo_info_list)
            print(f"Processed: {repo_info['RepositoryName']}")

    print(json.dumps(new_repos, indent=4))
    return new_repos

# main function
def run_update_process():
    new_repo_info_list = get_org_repository_info()
    print("Organization repository information saved to", OUTPUT_FILE)
    existing_repos_in_notion = get_existing_repositories_from_notion()
    upload_to_notion(new_repo_info_list, existing_repos_in_notion)

if __name__ == "__main__":
    run_update_process()
