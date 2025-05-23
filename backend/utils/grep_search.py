import re
import os
from github import Github, Auth, RateLimitExceededException, UnknownObjectException, GithubException
from dotenv import load_dotenv

# # --- Constants ---
MAX_RESULTS_CAP = 50
load_dotenv()
# # --- GitHub Initialization (reuse from your previous code) ---
# REPO_OWNER = "unslothai"  # Example
# REPO_NAME = "unsloth"     # Example
access_token = os.getenv("github_pat_1")
# # access_token = None # Set your token here if not using environment variables
# # access_token = "YOUR_GITHUB_PAT_HERE" # Or paste your token here

if access_token:
    print("Using provided access token for authentication.")
    auth = Auth.Token(access_token)
    g = Github(auth=auth)
else:
    print("Proceeding without authentication (rate limits may apply).")
    g = Github()

# --- grep_search Function ---

def grep_search_github(
    github_client: Github,
    repo_owner: str,
    repo_name: str,
    search_path: str,
    query: str,
    match_per_line: bool,
    includes: list[str],
    case_insensitive: bool,
    max_results: int = MAX_RESULTS_CAP
) -> list:
    """
    Performs a grep-like search within a GitHub repository using the Search API.

    Args:
        github_client: Authenticated PyGithub client instance.
        repo_owner: The owner of the repository.
        repo_name: The name of the repository.
        search_path: The directory or file path to search within (relative to repo root).
        query: The search term or pattern.
        match_per_line: If True, return line details; otherwise, return filenames only.
        includes: List of file patterns/names to include (e.g., ["*.py", "README.md"]).
        case_insensitive: If True, performs a case-insensitive search (API default).
                         If False, attempts post-fetch filtering for exact case.
        max_results: The maximum number of results to return (applied to lines or files).

    Returns:
        A list of dictionaries (for match_per_line=True) or strings (for match_per_line=False).
        Returns an empty list if errors occur or no matches are found.

    Limitations:
        - Searches the default branch primarily.
        - True case-sensitivity (CaseInsensitive=False) relies on post-filtering.
        - Complex 'includes' patterns might not translate perfectly.
        - MatchPerLine=True can be slow and API-intensive.
    """
    results = []
    repo_full_name = f"{repo_owner}/{repo_name}"
    print(f"--- Starting grep_search ---")
    print(f"Repo: {repo_full_name}, Path: '{search_path}', Query: '{query}'")
    print(f"MatchPerLine: {match_per_line}, CaseInsensitive: {case_insensitive}, Includes: {includes}")

    try:
        repo = github_client.get_repo(repo_full_name) # Verify repo exists

        # Construct the search query for search_code
        search_qualifiers = [
            query, # The core search term
            f"repo:{repo_full_name}",
        ]
        if search_path and search_path != "/": # Add path qualifier if not root
             search_qualifiers.append(f"path:{search_path.strip('/')}")

        # Add include qualifiers (simplistic approach)
        for include_pattern in includes:
            if include_pattern.startswith("*."):
                # Treat as extension
                ext = include_pattern[2:]
                if ext:
                    search_qualifiers.append(f"extension:{ext}")
            elif include_pattern:
                # Treat as filename
                 search_qualifiers.append(f"filename:{include_pattern}")

        final_query = " ".join(search_qualifiers)
        print(f"Constructed Search API Query: {final_query}")

        # Execute the search
        # Note: search_code returns ContentFile objects representing *files* containing the query
        found_files = github_client.search_code(query=final_query)

        processed_files = set() # Keep track of files processed if MatchPerLine=False
        match_count = 0

        # Process search results
        for file_match in found_files:
            if match_count >= max_results:
                print(f"Reached max results limit ({max_results}). Stopping.")
                break

            file_path = file_match.path

            if not match_per_line:
                # --- Filenames only ---
                if file_path not in processed_files:
                    print(f"Found match in file: {file_path}")
                    results.append({"Filename": file_path}) # Return dict consistent with schema idea
                    processed_files.add(file_path)
                    match_count += 1
            else:
                # --- Line numbers and content ---
                # This requires fetching the file content - potentially slow!
                print(f"Fetching content for potential match: {file_path}")
                try:
                    # Need the actual Repository object to get contents easily by path
                    content_item = repo.get_contents(file_path)
                    if content_item.type != 'file':
                        continue # Skip directories returned by search (shouldn't happen often)

                    # Decode content (handle potential errors)
                    try:
                        file_content = content_item.decoded_content.decode('utf-8')
                    except (UnicodeDecodeError, AttributeError):
                         print(f"Warning: Could not decode content for {file_path}. Skipping.")
                         continue # Skip files we can't decode

                    lines = file_content.splitlines()
                    search_flags = re.IGNORECASE if case_insensitive else 0

                    for line_num, line_content in enumerate(lines, 1):
                         # Perform the actual line match here
                         # Use regex search for flexibility, though simple string find could also work
                         match = None
                         try:
                            # Use re.search to find the pattern anywhere in the line
                            match = re.search(re.escape(query), line_content, search_flags)
                         except re.error:
                             # Fallback to simple string find if query is not a valid regex part
                              if case_insensitive:
                                  if query.lower() in line_content.lower():
                                      match = True # Indicate a match was found
                              else:
                                  if query in line_content:
                                       match = True # Indicate a match was found


                         if match:
                            if match_count < max_results:
                                print(f"  Match found: {file_path}:L{line_num}")
                                results.append({
                                    "Filename": file_path,
                                    "LineNumber": line_num,
                                    "LineContent": line_content.strip() # Remove leading/trailing whitespace
                                })
                                match_count += 1
                            else:
                                print(f"Reached max results limit ({max_results}) while scanning {file_path}. Stopping.")
                                break # Stop scanning this file
                    if match_count >= max_results:
                         break # Stop iterating through files if max results hit

                except RateLimitExceededException:
                    print("Error: GitHub API rate limit exceeded.")
                    raise # Re-raise to stop execution
                except UnknownObjectException:
                    print(f"Warning: Could not fetch content for {file_path} (possibly removed after indexing). Skipping.")
                except GithubException as e:
                    print(f"Warning: GitHub API error fetching content for {file_path}: {e}. Skipping.")
                except Exception as e:
                    print(f"Warning: Unexpected error processing file {file_path}: {e}. Skipping.")


    except RateLimitExceededException:
        print("Error: GitHub API rate limit exceeded during initial search.")
    except UnknownObjectException:
         print(f"Error: Repository '{repo_full_name}' not found or initial search failed.")
    except GithubException as e:
         print(f"Error: GitHub API error during search: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print(f"--- grep_search finished. Found {len(results)} results. ---")
    # Ensure output format matches expectation (list of dicts even for filenames only)
    if not match_per_line and results:
        # Convert simple list of filenames to list of dicts
        return [{"Filename": fname_dict["Filename"]} for fname_dict in results]
    elif match_per_line:
         return results # Already list of dicts
    else: # No results or error
        return []


# # --- Example Usage ---
# def grep_search_github_main():
#     """
#     Example usage of grep_search_github. This can be called from another script.
#     """
#     # Example 1: Find filenames containing 'import torch' in python files under 'unsloth' dir
#     print("\n--- Example 1: Find filenames containing 'import torch' in python files under 'unsloth' dir ---")
#     results = grep_search_github(
#         github_client=g,
#         repo_owner=REPO_OWNER,
#         repo_name=REPO_NAME,
#         search_path="unsloth",
#         query="import torch",
#         match_per_line=False,
#         includes=["*.py"],     # Only look in python files
#         case_insensitive=True
#     )
#     print("Results (Filenames):")
#     for res in results1:
#         print(res)

#     # Example 2: Find exact lines containing 'LlamaForCausalLM' (case-sensitive) in any file
#     # Note: This will be slower and use more API calls
#     print("\nExample 2: Line details (Case-Sensitive)")
#     results2 = grep_search_github(
#         github_client=g,
#         repo_owner=REPO_OWNER,
#         repo_name=REPO_NAME,
#         search_path="", # Search whole repo (root)
#         query="LlamaForCausalLM",
#         match_per_line=True,
#         includes=[], # Search all indexed file types
#         case_insensitive=False # Try for case-sensitive match
#     )
#     print("\nResults (Line Details):")
#     for res in results2:
#         print(f"- {res['Filename']}:{res['LineNumber']} | {res['LineContent']}")

#     # Example 3: Find lines containing 'gradient_checkpointing' (case-insensitive) in specific file
#     print("\nExample 3: Line details in specific file")
#     results3 = grep_search_github(
#         github_client=g,
#         repo_owner=REPO_OWNER,
#         repo_name=REPO_NAME,
#         search_path="unsloth/models/loader.py", # Specify a single file path
#         query="gradient_checkpointing",
#         match_per_line=True,
#         includes=[], # Includes likely ignored when search_path is a file
#         case_insensitive=True
#     )
#     print("\nResults (Line Details):")
#     for res in results3:
#          print(f"- {res['Filename']}:{res['LineNumber']} | {res['LineContent']}")