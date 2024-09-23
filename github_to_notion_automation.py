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

# get existing repositories from Notion
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
            name_property = page['properties']['name']['title']
            if name_property:
                repo_name = name_property[0]['plain_text']
                existing_repos.append(repo_name)

    return existing_repos

# get repositories with pagination
def get_org_repositories():
    repos = []
    page = 1
    per_page = 100  # GitHub allows a maximum of 100 items per page

    while True:
        url = f"{GITHUB_API_URL}/orgs/{ORGANIZATION}/repos?page={page}&per_page={per_page}"
        response = requests.get(url, headers=HEADERS)

        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break

        data = response.json()
        if not data:
            break  # No more repos, exit the loop

        repos.extend(data)
        page += 1

    return repos

# extract repository information
def extract_repo_info(repo):
    return {
        "name": repo.get("name"),
        "license": repo.get("license").get("name") if repo.get("license") else None,
        "visibility": repo.get("visibility"),
        "is_admin": repo.get("permissions").get("admin"),
        "group": repo.get("organization")['login'] if repo.get("organization") else None
    }

# resume from the last saved point
def load_existing_data():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as file:
            try:
                data = json.load(file)
                return data
            except json.JSONDecodeError:
                return []
    return []

# save the repository information incrementally
def save_repository_info(repo_info_list):
    with open(OUTPUT_FILE, 'w') as file:
        json.dump(repo_info_list, file, indent=4)

# upload new repositories to Notion
def upload_to_notion(new_repo_info_list):
    notion = Client(auth=INTEGRATION_TOKEN)
    for repo_info in new_repo_info_list:
        try:
            notion.pages.create(parent={"database_id": DATABASE_ID}, properties={
                "name": {"title": [{"text": {"content": repo_info["name"]}}]},
                "license": {"rich_text": [{"text": {"content": repo_info["license"] or ""}}]},
                "visibility": {"select": {"name": repo_info["visibility"]}},
                "is_admin": {"checkbox": repo_info["is_admin"]},
                "group": {"rich_text": [{"text": {"content": repo_info["group"] or ""}}]}
            })
            print(f"Uploaded {repo_info['name']} to Notion")
        except Exception as e:
            print(f"Failed to upload {repo_info['name']} to Notion: {e}")

# fetch, process, and upload repositories with resume functionality
def get_org_repository_info():
    # get existing repositories from Notion
    existing_repos = get_existing_repositories_from_notion()
    print(f"Existing repositories in Notion: {existing_repos}")

    # get repositories from GitHub
    github_repos = get_org_repositories()
    print(f"Total GitHub repositories fetched: {len(github_repos)}")

    # compare and find new repositories
    existing_data = load_existing_data()
    processed_names = {repo["name"] for repo in existing_data}
    repo_info_list = existing_data[:]
    new_repos = []

    for repo in github_repos:
        if repo["name"] not in existing_repos and repo["name"] not in processed_names:  # Skip repos already processed
            try:
                repo_info = extract_repo_info(repo)
                repo_info_list.append(repo_info)
                new_repos.append(repo_info)
                # Save progress after each repository
                save_repository_info(repo_info_list)
                print(f"Processed: {repo_info['name']}")
            except Exception as e:
                print(f"Failed to process {repo['name']}: {e}")
                break

    # upload new repositories to Notion
    if new_repos:
        upload_to_notion(new_repos)

    return repo_info_list

# main function - handle the whole process
def run_update_process():
    repo_info_list = get_org_repository_info()
    print("Organization repository information saved to", OUTPUT_FILE)

if __name__ == "__main__":
    run_update_process()