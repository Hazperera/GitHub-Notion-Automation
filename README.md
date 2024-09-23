<<<<<<< HEAD
# GitHub-Notion-Automation
This project automates fetching repository data from GitHub and updating it in a Notion database. It supports incremental updates, only adding new repositories without overwriting or deleting existing data.
=======
# GitHub to Notion Automation 

This project automates fetching repository data from GitHub and updating it in a Notion database. It supports incremental updates, only adding new repositories without overwriting or deleting existing data.

## Features

- Fetches repository data from a specified GitHub organization.
- Updates a Notion database with repository details.
- Supports incremental updates to avoid duplication.
- Designed for local development with `.env` file management.
- Uses Poetry for dependency management.

## Prerequisites

- Python 3.8+
- **Poetry** for dependency management. If not installed, use the official installer script:
  ```bash
  curl -sSL https://install.python-poetry.org | python3 -
  ```

- A Notion integration with API access.
- A GitHub API token with read access to the organization's repositories.

## Setup
1. Clone the Repository
   ```bash
   git clone https://github.com/NethermindEth/github-notion-integration.git
   cd github-notion-integration
   ```

 2. Create a ```.env File``` in the project directory's root to store your API tokens and Notion database ID.
    ```bash
    GITHUB_TOKEN=your_github_api_token_here
    NOTION_TOKEN=your_notion_integration_token_here
    NOTION_DATABASE_ID=your_notion_database_id_here
    ```
 3. Install Dependencies (use poetry to install the dependencies specified in the pyproject.toml file).
    ```bash
    poetry install
    ```
- This will install all required packages, including ```requests```, ```notion-client```, and ```python-dotenv```.

 4. Activate the virtual environment*
    ```bash
    poetry shell
    ```

5. Run the Scripts

- This script fetches all repositories from the specified GitHub organization, checks for any new repositories that aren’t already in the Notion database, and
  adds them to the database. If the database is empty, it will perform a full update.
  
    ```bash
    python github_to_notion_sync.py
    ```
- *Alternatively, if you don’t want to activate the shell, you can run the script directly with;

    ```bash
    poetry run python github_to_notion_sync.py
    ```


>>>>>>> d89eebd (update structure)
