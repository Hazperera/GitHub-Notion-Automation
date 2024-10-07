import boto3
import requests
import json
import os
import time
from botocore.exceptions import ClientError
from notion_client import Client


#initialize AWS Secrets Manager
def get_secret():
    secret_name = "github-notion-integration"
    region_name = "us-east-1"

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        print("Couldn't retrieve secret:", e)
        return None
    else:
        if 'SecretString' in get_secret_value_response:
            secret = json.loads(get_secret_value_response['SecretString'])
            return secret
        raise Exception("Secret does not include 'SecretString' key.")

#load secrets & configure tokens
secrets = get_secret()
GITHUB_TOKEN = secrets['GITHUB_TOKEN']
NOTION_TOKEN = secrets['NOTION_TOKEN']
NOTION_DATABASE_ID = secrets['NOTION_DATABASE_ID']
ORGANIZATION = secrets['ORGANIZATION']

#GitHub API, URL, headers
GITHUB_API_URL = "https://api.github.com"
TOKEN = GITHUB_TOKEN
ORGANIZATION = ORGANIZATION
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

#Notion API
DATABASE_ID = NOTION_DATABASE_ID
INTEGRATION_TOKEN = NOTION_TOKEN

#output file
OUTPUT_FILE = f'{ORGANIZATION}_github_org_repos.json'

#extract existing repositories from Notion
def get_existing_repositories_from_notion():
    notion = Client(auth=INTEGRATION_TOKEN)
    existing_repos = []
    notion_repo_pages = {}
    has_more = True
    start_cursor = None
    print("Fetching existing repositories from Notion...")
    while has_more:
        response = notion.databases.query(database_id=DATABASE_ID, start_cursor=start_cursor)
        has_more = response['has_more']
        start_cursor = response.get('next_cursor', None)
        for page in response['results']:
            name_property = page['properties'].get('RepositoryName', {}).get('title')
            if name_property:
                repo_name = name_property[0]['plain_text']
                existing_repos.append(repo_name)
                notion_repo_pages[repo_name] = page['id']
    return existing_repos, notion_repo_pages


#get repositories (with pagination) from GitHub
def get_org_repositories():
    repos = []
    page = 1
    per_page = 100
    print("Fetching repositories from GitHub...")
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
    print(f"Total GitHub repositories fetched: {len(repos)}")
    return repos


#get repository admins from GitHub
def get_repo_admins(repo_name):
    url = f"{GITHUB_API_URL}/repos/{ORGANIZATION}/{repo_name}/collaborators"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        collaborators = response.json()
        admins = [collab['login'] for collab in collaborators if collab.get('permissions', {}).get('admin', False)]
        return admins if admins else ["No Admin"]
    else:
        return [f"Failed to fetch admins: Error {response.status_code}"]


#get repository groups from GitHub
def get_repo_groups(repo_name):
    url = f"{GITHUB_API_URL}/repos/{ORGANIZATION}/{repo_name}/teams"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        teams = response.json()
        team_names = [team['name'] for team in teams]
        return team_names if team_names else ["No Group"]
    else:
        return [f"Failed to fetch groups: Error {response.status_code}"]


#extract repository information
def extract_repo_info(repo):
    admin_list = get_repo_admins(repo.get("name"))
    group_list = get_repo_groups(repo.get("name"))
    return {
        "RepositoryName": repo.get("name"),
        "LicenseInformation": repo.get("license", {}).get("name") if repo.get("license") else "No License",
        "Visibility": repo.get("visibility", "private"),
        "Admin": admin_list,
        "Group": group_list
    }

#save entire repository information to a file (overwrites with the full list)
def save_repository_info(repo_info_list):
    print("Saving entire repository information to file...")
    with open(OUTPUT_FILE, 'w') as file:
        json.dump(repo_info_list, file, indent=4)

#remove repositories from Notion that no longer exist on GitHub
def remove_deleted_repos_from_notion(deleted_repos, notion_repo_pages):
    notion = Client(auth=INTEGRATION_TOKEN)
    for repo_name in deleted_repos:
        notion_page_id = notion_repo_pages.get(repo_name)
        if notion_page_id:
            try:
                print(f"Removing {repo_name} from Notion.")
                notion.pages.update(notion_page_id, archived=True)
            except Exception as e:
                print(f"Error while removing {repo_name} from Notion: {e}")


#upload new repositories to Notion
def upload_to_notion(new_repo_info_list, existing_repos_in_notion):
    notion = Client(auth=INTEGRATION_TOKEN)
    for repo_info in new_repo_info_list:
        repo_name = repo_info["RepositoryName"]
        if repo_name in existing_repos_in_notion:
            print(f"Skipping {repo_name} as it already exists in Notion.")
            continue
        try:
            print(f"Uploading {repo_name} to Notion...")
            notion.pages.create(parent={"database_id": DATABASE_ID}, properties={
                "RepositoryName": {"title": [{"text": {"content": repo_info["RepositoryName"]}}]},
                "LicenseInformation": {"rich_text": [{"text": {"content": repo_info["LicenseInformation"]}}]},
                "Visibility": {"rich_text": [{"text": {"content": repo_info["Visibility"]}}]},
                "Admin": {"rich_text": [{"text": {"content": ', '.join(repo_info["Admin"])}}]},
                "Group": {"rich_text": [{"text": {"content": ', '.join(repo_info["Group"])}}]}
            })
        except Exception as e:
            print(f"Error uploading {repo_name} to Notion: {e}")
        time.sleep(2)


#fetch, process, and upload repositories
def get_org_repository_info():
    existing_repos_in_notion, notion_repo_pages = get_existing_repositories_from_notion()
    github_repos = get_org_repositories()
    repo_info_list = [extract_repo_info(repo) for repo in github_repos]
    save_repository_info(repo_info_list)
    github_repo_names = [repo.get("name") for repo in github_repos]
    deleted_repos = set(existing_repos_in_notion) - set(github_repo_names)

    if deleted_repos:
        print(f"Repositories deleted from GitHub: {deleted_repos}")
        remove_deleted_repos_from_notion(deleted_repos, notion_repo_pages)
    new_repos = [repo for repo in repo_info_list if repo["RepositoryName"] not in existing_repos_in_notion]
    if new_repos:
        print("New repositories added:")
        for repo in new_repos:
            print(f"- {repo['RepositoryName']}")

    return new_repos, deleted_repos


#main function
def run_update_process():
    print("Starting repository update process...")

    #fetch organization repositories from GitHub and Notion, and compare
    new_repo_info_list, deleted_repos = get_org_repository_info()

    #upload new repositories to Notion
    existing_repos_in_notion, _ = get_existing_repositories_from_notion()
    if new_repo_info_list:
        upload_to_notion(new_repo_info_list, existing_repos_in_notion)

    #summary
    print("\nSummary of the run:")
    print(f"- Total new repositories added: {len(new_repo_info_list)}")
    print(f"- Total repositories deleted: {len(deleted_repos)}")

    if deleted_repos:
        print("Repositories deleted from Notion:")
        for repo in deleted_repos:
            print(f"- {repo}")

    print("Repository update process completed.")


if __name__ == "__main__":
    run_update_process()
