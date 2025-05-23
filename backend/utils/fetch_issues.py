import re
import os
import logging
from dotenv import load_dotenv
from github import Github, Auth, RateLimitExceededException, UnknownObjectException, GithubException


logger = logging.getLogger("app_logger")

# --- Configuration ---
# Replace with the owner and repository name you're interested in
REPO_OWNER = "unslothai"
REPO_NAME = "unsloth"
load_dotenv()


access_token = os.getenv("GITHUB_TOKEN_3") # Set your token here if not using environment variables

# --- Initialize GitHub API Client ---
if access_token:
    logger.info("Using provided access token for authentication.")
    auth = Auth.Token(access_token)
    g = Github(auth=auth)
else:
    # Without a token, you'll be subject to stricter rate limits
    logger.warning("Proceeding without authentication (rate limits may apply).")
    g = Github()

def fetch_issues(owner, repo_name, max_issues_to_print=10):
    """
    Fetch and return issues from the specified repository.
    Args:
        owner: Repository owner (str)
        repo_name: Repository name (str)
        max_issues_to_print: Maximum number of issues to return (default 10).
    Returns:
        List of dictionaries, where each dictionary represents an issue
        and conforms to the IssueDetail model structure.
    """
    logger.info(f"fetch_issues called for repository: {owner}/{repo_name} (max_issues_to_print={max_issues_to_print})")
    try:
        repo_full_name = f"{owner}/{repo_name}"
        repo = g.get_repo(repo_full_name)
        issues_paginator = repo.get_issues(state='all') # Changed variable name for clarity
        logger.info(f"Found {issues_paginator.totalCount} total issues in {repo_full_name}.")
        
        formatted_issues_list = []
        for count, issue in enumerate(issues_paginator):
            if count >= max_issues_to_print:
                logger.info(f"Stopping after collecting {max_issues_to_print} issues.")
                break
            
            logger.debug(f"Processing issue #{issue.number}: {issue.title}")
            
            # Handle potential None for issue.body
            description = issue.body if issue.body is not None else ""

            # Handle potential None for issue.user
            creator_name = issue.user.login if issue.user else "N/A"

            issue_data = {
                "title": issue.title,
                "description": description,
                "creator_name": creator_name,
                "status": issue.state,  # 'state' in PyGithub issue maps to 'status'
                "url": issue.html_url # 'html_url' in PyGithub issue maps to 'url'
            }
            formatted_issues_list.append(issue_data)
            
        if not formatted_issues_list: # Check if the list is empty
            logger.info("No issues found or collected matching the criteria.")
            
        logger.info(f"Returning {len(formatted_issues_list)} issues from fetch_issues.")
        return formatted_issues_list
    except RateLimitExceededException:
        logger.error(f"GitHub API rate limit exceeded for {owner}/{repo_name}.")
        # Consider re-raising or returning a specific error structure
        # For now, returning empty list similar to other errors
        return []
    except UnknownObjectException:
        logger.error(f"Repository {owner}/{repo_name} not found or access denied.")
        return []
    except GithubException as e: # Catch other GitHub specific exceptions
        logger.error(f"A GitHub API error occurred for {owner}/{repo_name}: {e}")
        return []
    except Exception as e: # General exception catch
        logger.error(f"An unexpected error occurred while fetching issues for {owner}/{repo_name}: {e}", exc_info=True)
        # It's often good to re-raise unexpected errors or handle them specifically
        # For now, returning empty to align with previous error handling pattern
        return []

