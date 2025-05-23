import ast
import base64
from github import Github, Auth, RateLimitExceededException, UnknownObjectException, GithubException

def get_code_dependencies(repo_owner: str, repo_name: str, file_path: str, github_token: str = None):
    """
    Analyzes a Python file from a public GitHub repository to identify its direct import dependencies.

    :param repo_owner: The owner of the repository (e.g., 'octocat').
    :param repo_name: The name of the repository (e.g., 'Hello-World').
    :param file_path: The path to the Python file within the repository (e.g., 'src/main.py').
    :param github_token: Optional. A GitHub personal access token for authenticated requests.
                         Recommended for avoiding rate limits.
    :return: A list of identified direct import dependencies (module names).
    :raises: RateLimitExceededException, UnknownObjectException, GithubException, ValueError
    """
    try:
        if github_token:
            auth = Auth.Token(github_token)
            g = Github(auth=auth)
        else:
            g = Github() # For public repositories, no token is strictly needed but rate limits are lower

        repo = g.get_repo(f"{repo_owner}/{repo_name}")
        contents = repo.get_contents(file_path)

        if contents.type != "file":
            raise ValueError(f"Path '{file_path}' does not point to a file.")

        if not file_path.endswith(".py"):
            print(f"Warning: File '{file_path}' does not have a .py extension. Attempting to parse as Python.")

        # Content is base64 encoded by the GitHub API
        try:
            decoded_content = base64.b64decode(contents.content).decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError(f"Could not decode file content for '{file_path}'. Ensure it is UTF-8 encoded.")
        
        dependencies = set()
        try:
            tree = ast.parse(decoded_content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dependencies.add(alias.name.split('.')[0]) # Get the top-level module
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        dependencies.add(node.module.split('.')[0]) # Get the top-level module
        except SyntaxError:
            raise ValueError(f"Could not parse Python code in '{file_path}'. It might contain syntax errors or not be a Python file.")

        return sorted(list(dependencies))

    except RateLimitExceededException:
        print("GitHub API rate limit exceeded. Please try again later or use a GitHub token.")
        raise
    except UnknownObjectException:
        print(f"Error: Repository '{repo_owner}/{repo_name}' or file '{file_path}' not found.")
        raise
    except GithubException as e:
        print(f"An error occurred with the GitHub API: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise

if __name__ == '__main__':
    # Example usage (requires a public repo and file for testing without a token)
    # To test, replace with a valid public repository and file path.
    # For private repos or higher rate limits, set a GITHUB_TOKEN environment variable or pass it directly.
    # import os
    # token = os.getenv("GITHUB_TOKEN")

    print("Example: Analyzing 'requests/api.py' from 'psf/requests' repository")
    try:
        # A well-known public repository and file
        deps = get_code_dependencies('psf', 'requests', 'requests/api.py') 
        print(f"Dependencies: {deps}")
    except Exception as e:
        print(f"Example failed: {e}")

    print("\nExample: Analyzing a non-existent file")
    try:
        deps = get_code_dependencies('psf', 'requests', 'non_existent_file.py')
        print(f"Dependencies: {deps}")
    except Exception as e:
        print(f"Example failed as expected: {e}")

    print("\nExample: Analyzing a non-Python file (e.g., README.md)")
    try:
        # Example of trying to parse a non-Python file
        deps = get_code_dependencies('psf', 'requests', 'README.md')
        print(f"Dependencies for README.md: {deps}")
    except ValueError as e:
        print(f"Example failed as expected: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during README.md test: {e}")
