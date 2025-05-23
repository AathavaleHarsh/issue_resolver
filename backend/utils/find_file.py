#!/usr/bin/env python3
"""
find_file_by_name.py - Search for files in GitHub repositories by name pattern.

This module provides functionality to search for files in public GitHub repositories
using the GitHub API. It allows searching by file name pattern, file type, and depth.
"""

from typing import List, Optional, Dict, Any, Union
from github import Github, Auth, GithubException
import re
import argparse
from pathlib import Path


def find_files_by_name(
    repo_owner: str,
    repo_name: str,
    pattern: str = "*",
    search_path: str = "",
    file_type: str = "any",
    max_depth: Optional[int] = None,
    github_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search for files in a GitHub repository by name pattern.

    Args:
        repo_owner: Owner of the GitHub repository
        repo_name: Name of the GitHub repository
        pattern: Glob-style pattern to match file names against (default: "*")
        search_path: Directory path within the repository to start search from (default: "")
        file_type: Type filter - "file", "directory", or "any" (default: "any")
        max_depth: Maximum depth to search (None for unlimited)
        github_token: GitHub access token for higher rate limits (optional)

    Returns:
        List of dictionaries containing file/directory information

    Raises:
        ValueError: If invalid arguments are provided
        GithubException: For GitHub API related errors
    """
    # Input validation
    if file_type.lower() not in ("file", "directory", "any"):
        raise ValueError("file_type must be 'file', 'directory', or 'any'")
    
    if max_depth is not None and max_depth < 0:
        raise ValueError("max_depth must be None or a non-negative integer")

    # Convert glob pattern to regex
    def glob_to_regex(pat: str) -> str:
        """Convert a glob pattern to a regex pattern."""
        regex = []
        i, n = 0, len(pat)
        
        while i < n:
            c = pat[i]
            i += 1
            
            if c == '*':
                regex.append('.*')
            elif c == '?':
                regex.append('.')
            elif c == '[':
                j = i
                if j < n and pat[j] == '!':
                    j += 1
                if j < n and pat[j] == ']':
                    j += 1
                while j < n and pat[j] != ']':
                    j += 1
                if j >= n:
                    regex.append('\\[')
                else:
                    stuff = pat[i:j].replace('\\', '\\\\')
                    i = j + 1
                    if stuff[0] == '!':
                        stuff = '^' + stuff[1:]
                    elif stuff[0] == '^':
                        stuff = '\\' + stuff
                    regex.append(f'[{stuff}]')
            else:
                regex.append(re.escape(c))
        
        return f'^{"".join(regex)}$'
    
    pattern_re = re.compile(glob_to_regex(pattern), re.IGNORECASE)
    results = []

    # Initialize GitHub client
    auth = Auth.Token(github_token) if github_token else None
    g = Github(auth=auth)
    
    try:
        # Get the repository
        repo = g.get_repo(f"{repo_owner}/{repo_name}")
        
        # Start from the root if no path is specified
        if not search_path:
            contents = repo.get_contents("")
        else:
            try:
                contents = repo.get_contents(search_path)
                if isinstance(contents, list):
                    pass  # It's a directory
                else:
                    contents = [contents]  # It's a single file
            except GithubException as e:
                if e.status == 404:
                    return []  # Path not found
                raise
        
        # Process the contents
        while contents:
            content = contents.pop(0)
            
            # Skip .git directory
            if ".git" in content.path.split('/'):
                continue
                
            # Calculate depth
            depth = content.path.count('/') - search_path.count('/') if search_path else content.path.count('/')
            if max_depth is not None and depth > max_depth:
                continue
            
            # Check if it's a directory
            if content.type == "dir":
                if file_type.lower() in ("directory", "any") and pattern_re.match(Path(content.name).name):
                    results.append({
                        "path": content.path,
                        "type": "directory",
                        "size": 0,
                        "url": content.html_url
                    })
                
                # Add directory contents to the queue
                try:
                    dir_contents = repo.get_contents(content.path)
                    if isinstance(dir_contents, list):
                        contents.extend(dir_contents)
                except GithubException:
                    continue  # Skip directories we can't access
            
            # Check if it's a file
            elif content.type == "file":
                if file_type.lower() in ("file", "any") and pattern_re.match(Path(content.name).name):
                    results.append({
                        "path": content.path,
                        "type": "file",
                        "size": content.size,
                        "url": content.html_url,
                        "download_url": content.download_url
                    })
    
    except GithubException as e:
        if e.status == 403 and "rate limit" in str(e).lower():
            rate_limit = g.get_rate_limit()
            reset_time = rate_limit.core.reset
            raise GithubException(
                status=403,
                data={"message": f"GitHub API rate limit exceeded. Resets at: {reset_time}"}
            ) from e
        raise
    
    return results


def main():
    """Command-line interface for find_files_by_name."""
    parser = argparse.ArgumentParser(description="Search for files in a GitHub repository by name pattern.")
    parser.add_argument("repo_owner", help="Owner of the GitHub repository")
    parser.add_argument("repo_name", help="Name of the GitHub repository")
    parser.add_argument("-p", "--pattern", default="*", help="Pattern to match file names against (glob format)")
    parser.add_argument("--path", default="", help="Directory path within the repository to start search from")
    parser.add_argument("--type", choices=["file", "directory", "any"], default="any", 
                        help="Type filter: file, directory, or any")
    parser.add_argument("--max-depth", type=int, help="Maximum depth to search")
    parser.add_argument("--token", help="GitHub access token for higher rate limits")
    
    args = parser.parse_args()
    
    try:
        results = find_files_by_name(
            repo_owner=args.repo_owner,
            repo_name=args.repo_name,
            pattern=args.pattern,
            search_path=args.path,
            file_type=args.type,
            max_depth=args.max_depth,
            github_token=args.token
        )
        
        if not results:
            print("No matching files or directories found.")
            return
        
        print(f"Found {len(results)} matching items:")
        for item in results:
            print(f"{item['type'].upper()}: {item['path']} (Size: {item.get('size', 'N/A')} bytes)")
            print(f"  URL: {item['url']}")
            if 'download_url' in item:
                print(f"  Download: {item['download_url']}")
    
    except Exception as e:
        print(f"Error: {str(e)}")
        if hasattr(e, 'data') and 'message' in e.data:
            print(f"Details: {e.data['message']}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
