import os
import json
from datetime import datetime
from pathlib import Path
import argparse
from github import Github, Auth, GithubException
from urllib.parse import urlparse
from typing import Union, Dict, List, Optional
import time # Added for rate limit handling


def is_github_repo_url(repo_url: str) -> bool:
    """Check if the given URL is a GitHub repository URL."""
    parsed = urlparse(repo_url)
    return 'github.com' in parsed.netloc and len(parsed.path.strip('/').split('/')) >= 2


def get_github_repo_contents(repo_url: str, path: str = "", recursive: bool = True,
                             token: Optional[str] = None, show_hidden_files: bool = False,
                             max_retries: int = 3, retry_delay: int = 5) -> List[Dict]:
    """
    List contents of a GitHub repository.

    Args:
        repo_url: GitHub repository URL (e.g., 'https://github.com/username/repo')
        path: Path within the repository (default: root)
        recursive: Whether to list contents recursively
        token: GitHub personal access token (optional, for private repos)
        show_hidden_files: Whether to show hidden files (starting with '.')
        max_retries: Maximum number of retries for API calls.
        retry_delay: Delay in seconds between retries (base for exponential backoff).

    Returns:
        List of dictionaries containing file/directory information
    """
    g = None
    try:
        if token:
            auth = Auth.Token(token)
            g = Github(auth=auth)
        else:
            g = Github()
    except Exception as e:
        return [{"error": f"Failed to initialize GitHub client: {str(e)}"}]

    parsed_url = urlparse(repo_url)
    path_parts = parsed_url.path.strip('/').split('/')
    if not ('github.com' in parsed_url.netloc and len(path_parts) >= 2):
        return [{"error": "Invalid GitHub repository URL format"}]

    owner, repo_name_full = path_parts[0], path_parts[1]
    repo_name = repo_name_full.replace('.git', '')

    current_attempt = 0
    while current_attempt <= max_retries:
        try:
            if g is None: # Should not happen if initial client setup was successful
                 if token: g = Github(auth=Auth.Token(token))
                 else: g = Github()
            
            repo = g.get_repo(f"{owner}/{repo_name}")
            contents_data = repo.get_contents(path)
            results = []

            for content_item in contents_data:
                if not show_hidden_files and content_item.name.startswith('.'):
                    continue

                item_info = {
                    "name": content_item.name,
                    "path": content_item.path,
                    "type": "directory" if content_item.type == "dir" else "file",
                    "size": content_item.size if content_item.type == "file" else 0,
                    "modified": content_item.last_modified if hasattr(content_item, 'last_modified') else None,
                    "url": content_item.html_url
                }

                if content_item.type == "dir" and recursive:
                    children_contents = get_github_repo_contents(
                        repo_url, content_item.path, recursive, token,
                        show_hidden_files, max_retries, retry_delay
                    )
                    if children_contents and isinstance(children_contents, list) and \
                       len(children_contents) > 0 and isinstance(children_contents[0], dict) and \
                       "error" in children_contents[0]:
                        item_info["children_error"] = children_contents[0]["error"]
                        item_info["children"] = []
                        item_info["children_count"] = 0
                    else:
                        item_info["children"] = children_contents
                        item_info["children_count"] = len(children_contents) if isinstance(children_contents, list) else 0
                results.append(item_info)
            return results

        except GithubException as e:
            is_rate_limit = e.status == 403 or e.status == 429
            is_not_found = e.status == 404

            if is_not_found:
                return [{"error": f"Path '{path}' not found in repository (Status {e.status}). Error: {str(e)}"}]

            if current_attempt < max_retries:
                actual_delay = retry_delay * (2 ** current_attempt)
                error_type = "Rate limit exceeded" if is_rate_limit else "GitHub API error"
                print(f"{error_type} (Status {e.status}) for path '{path}'. Retrying in {actual_delay}s... (Attempt {current_attempt + 1}/{max_retries + 1})")
                time.sleep(actual_delay)
                current_attempt += 1
                # Re-initialize client on retries for robustness
                try:
                    if token: g = Github(auth=Auth.Token(token))
                    else: g = Github()
                except Exception as client_init_e:
                     return [{"error": f"Failed to re-initialize GitHub client during retry: {str(client_init_e)}"}]
            else:
                error_type = "Rate limit exceeded" if is_rate_limit else "GitHub API error"
                return [{"error": f"{error_type} (Status {e.status}) after {max_retries + 1} attempts for path '{path}'. Original error: {str(e)}"}]
        except Exception as e: # Catch other non-GithubException errors (e.g., network issues)
            if current_attempt < max_retries:
                actual_delay = retry_delay * (2 ** current_attempt)
                print(f"An unexpected error occurred for path '{path}': {str(e)}. Retrying in {actual_delay}s... (Attempt {current_attempt + 1}/{max_retries + 1})")
                time.sleep(actual_delay)
                current_attempt += 1
            else:
                return [{"error": f"An unexpected error occurred after {max_retries + 1} attempts for path '{path}'. Original error: {str(e)}"}]

    return [{"error": f"Failed to get contents for path '{path}' after {max_retries + 1} attempts."}]


def list_directory_contents(directory_path: str, recursive: bool = False, 
                          show_hidden_files: bool = False, github_token: Optional[str] = None) -> Union[Dict, List[Dict]]:
    """
    Lists files and subdirectories within a given path, which can be either
    a local directory or a GitHub repository URL.
    
    Args:
        directory_path (str): Local directory path or GitHub repository URL
        recursive (bool): Whether to list contents recursively
        show_hidden_files (bool): Whether to show hidden files (starting with '.')
        github_token (str, optional): GitHub personal access token for private repositories
        
    Returns:
        Union[Dict, List[Dict]]: List of dictionaries containing file/directory information,
                               or error dictionary if an error occurs
    """
    # Convert to absolute path if relative
    if not os.path.isabs(directory_path):
        directory_path = os.path.abspath(directory_path)
    
    # Check if path exists and is a directory
    if not os.path.exists(directory_path):
        return {"error": f"Path does not exist: {directory_path}"}
    
    if not os.path.isdir(directory_path):
        return {"error": f"Path is not a directory: {directory_path}"}
    
    results = []
    
    try:
        # Get all items in the directory
        if recursive:
            for root, dirs, files in os.walk(directory_path):
                # Skip hidden directories if not showing hidden files
                if not show_hidden_files:
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                # Process directories
                for dir_name in dirs:
                    if not show_hidden_files and dir_name.startswith('.'):
                        continue
                        
                    dir_path = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(dir_path, directory_path)
                    
                    # Get directory stats
                    stats = os.stat(dir_path)
                    modified_time = datetime.fromtimestamp(stats.st_mtime).isoformat()
                    
                    # Count children
                    children_count = len(os.listdir(dir_path))
                    
                    results.append({
                        "name": dir_name,
                        "path": rel_path,
                        "type": "directory",
                        "size": 0,  # Directories don't have a size
                        "modified": modified_time,
                        "children_count": children_count
                    })
                
                # Process files
                for file_name in files:
                    if not show_hidden_files and file_name.startswith('.'):
                        continue
                        
                    file_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(file_path, directory_path)
                    
                    # Get file stats
                    stats = os.stat(file_path)
                    size = stats.st_size
                    modified_time = datetime.fromtimestamp(stats.st_mtime).isoformat()
                    
                    results.append({
                        "name": file_name,
                        "path": rel_path,
                        "type": "file",
                        "size": size,
                        "modified": modified_time
                    })
        else:
            # Non-recursive listing
            for item_name in os.listdir(directory_path):
                if not show_hidden_files and item_name.startswith('.'):
                    continue
                    
                item_path = os.path.join(directory_path, item_name)
                
                # Get item stats
                stats = os.stat(item_path)
                modified_time = datetime.fromtimestamp(stats.st_mtime).isoformat()
                
                if os.path.isdir(item_path):
                    # Count children
                    children_count = len(os.listdir(item_path))
                    
                    results.append({
                        "name": item_name,
                        "path": item_name,
                        "type": "directory",
                        "size": 0,  # Directories don't have a size
                        "modified": modified_time,
                        "children_count": children_count
                    })
                else:
                    size = stats.st_size
                    
                    results.append({
                        "name": item_name,
                        "path": item_name,
                        "type": "file",
                        "size": size,
                        "modified": modified_time
                    })
        
        return results
    
    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="List directory contents with metadata")
    parser.add_argument("directory_path", help="Path to the directory or GitHub repository URL to list")
    # Default to recursive listing. 'recursive' will be True by default.
    parser.set_defaults(recursive=True)
    # Add an option to disable recursion if explicitly requested.
    parser.add_argument("--no-recursion", "-nr", dest="recursive", action="store_false",
                        help="Disable recursive listing (default is to recurse)")
    parser.add_argument("-a", "--all", action="store_true", help="Show hidden files")
    parser.add_argument("--github-token", help="GitHub personal access token (for private repositories)", default=None)
    
    args = parser.parse_args()
    
    if is_github_repo_url(args.directory_path):
        results = get_github_repo_contents(
            args.directory_path,
            recursive=args.recursive,
            show_hidden_files=args.all,
            token=args.github_token
        )
    else:
        results = list_directory_contents(
            args.directory_path,
            recursive=args.recursive,
            show_hidden_files=args.all,
            github_token=args.github_token
        )
    
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
