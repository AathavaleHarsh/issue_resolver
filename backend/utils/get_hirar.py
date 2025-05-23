import os
import ast
import logging
from typing import List, Dict, Optional, Tuple, Union, Literal
from github import Github, Auth, RateLimitExceededException, UnknownObjectException, GithubException

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_call_hierarchy(repo_owner: str, repo_name: str, file_path: str, element_name: str, 
                      direction: Literal['callers', 'callees'], github_token: str = None) -> List[Dict]:
    """
    Shows where a specific function or method is called from (callers) or what functions/methods it calls (callees).
    
    Args:
        repo_owner (str): Owner of the GitHub repository
        repo_name (str): Name of the GitHub repository
        file_path (str): Path to the file containing the target element
        element_name (str): Name of the element to analyze (e.g., "MyClass.my_function")
        direction (str): Direction of analysis - "callers" or "callees"
        github_token (str, optional): GitHub personal access token
    
    Returns:
        List[Dict]: List of calling or called locations with file paths, line numbers, and context
    
    Raises:
        ValueError: If direction is not 'callers' or 'callees'
        GithubException: If there's an issue with the GitHub API
    """
    if direction not in ['callers', 'callees']:
        raise ValueError("Direction must be either 'callers' or 'callees'")
    
    # Initialize GitHub client
    if github_token:
        auth = Auth.Token(github_token)
        g = Github(auth=auth)
    else:
        g = Github()
    
    try:
        # Get repository and target file content
        repo = g.get_repo(f"{repo_owner}/{repo_name}")
        target_file_content = repo.get_contents(file_path).decoded_content.decode('utf-8')
        
        # Parse the target element name
        parts = element_name.split('.')
        class_name = parts[0] if len(parts) > 1 else None
        function_name = parts[-1]
        
        # Parse the target file to get the AST
        target_tree = ast.parse(target_file_content)
        
        # Find the target element in the AST
        target_node = find_element_in_ast(target_tree, class_name, function_name)
        if not target_node:
            return [{'error': f"Element '{element_name}' not found in {file_path}"}]
        
        # Get the repository structure to search for Python files
        all_python_files = get_all_python_files(repo)
        
        results = []
        
        if direction == 'callees':
            # Find all function calls within the target function/method
            callees = find_callees(target_node)
            for callee in callees:
                results.append({
                    'type': 'callee',
                    'name': callee['name'],
                    'file_path': file_path,
                    'line_number': callee['line_number'],
                    'context': callee['context']
                })
        else:  # direction == 'callers'
            # Search all Python files for calls to the target function/method
            for file_info in all_python_files:
                callers = find_callers(repo, file_info['path'], class_name, function_name)
                for caller in callers:
                    results.append({
                        'type': 'caller',
                        'name': caller['name'],
                        'file_path': file_info['path'],
                        'line_number': caller['line_number'],
                        'context': caller['context']
                    })
        
        return results
    
    except RateLimitExceededException:
        return [{'error': 'GitHub API rate limit exceeded. Please use a token or wait.'}]
    except UnknownObjectException:
        return [{'error': f"Repository '{repo_owner}/{repo_name}' or file '{file_path}' not found"}]
    except GithubException as e:
        return [{'error': f"GitHub API error: {str(e)}"}]
    except Exception as e:
        return [{'error': f"Unexpected error: {str(e)}"}]
    finally:
        g.close()


def find_element_in_ast(tree: ast.Module, class_name: Optional[str], function_name: str) -> Optional[Union[ast.FunctionDef, ast.AsyncFunctionDef]]:
    """
    Find a function or method in an AST.
    
    Args:
        tree: The AST of the file
        class_name: Name of the class (None if it's a standalone function)
        function_name: Name of the function or method
    
    Returns:
        The node representing the function or method, or None if not found
    """
    if class_name is None:
        # Look for standalone function
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
                return node
    else:
        # Look for method in class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == function_name:
                        return child
    return None


def find_callees(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> List[Dict]:
    """
    Find all function calls within a function or method.
    
    Args:
        node: The function or method node
    
    Returns:
        List of dictionaries with information about each call
    """
    callees = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = f"{get_attribute_path(func)}"
            else:
                continue
                
            callees.append({
                'name': name,
                'line_number': child.lineno,
                'context': get_line_context(node, child.lineno)
            })
    return callees


def get_attribute_path(node: ast.Attribute) -> str:
    """
    Get the full path of an attribute (e.g., 'obj.attr1.attr2').
    
    Args:
        node: The attribute node
    
    Returns:
        The full attribute path as a string
    """
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    parts.reverse()
    return '.'.join(parts)


def get_line_context(node: ast.AST, line_number: int) -> str:
    """
    Get the context (source code) for a line number within a node.
    This is a placeholder as we don't have direct access to source lines here.
    
    Args:
        node: The AST node
        line_number: The line number
    
    Returns:
        A placeholder string indicating the line number
    """
    return f"Line {line_number}"


def find_callers(repo, file_path: str, class_name: Optional[str], function_name: str) -> List[Dict]:
    """
    Find all calls to a specific function or method in a file.
    
    Args:
        repo: GitHub repository object
        file_path: Path to the file to search in
        class_name: Name of the class (None if it's a standalone function)
        function_name: Name of the function or method
    
    Returns:
        List of dictionaries with information about each caller
    """
    try:
        file_content = repo.get_contents(file_path).decoded_content.decode('utf-8')
        tree = ast.parse(file_content)
        
        callers = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                caller_name = node.name
                caller_class = find_parent_class(tree, node)
                
                # Look for calls to the target function/method in this function
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func = child.func
                        if isinstance(func, ast.Name) and func.id == function_name and class_name is None:
                            # Direct call to standalone function
                            callers.append({
                                'name': f"{caller_class + '.' if caller_class else ''}{caller_name}",
                                'line_number': child.lineno,
                                'context': get_line_context(node, child.lineno)
                            })
                        elif isinstance(func, ast.Attribute) and func.attr == function_name:
                            # Method call or qualified function call
                            if class_name is None or (
                                    isinstance(func.value, ast.Name) and func.value.id == class_name):
                                callers.append({
                                    'name': f"{caller_class + '.' if caller_class else ''}{caller_name}",
                                    'line_number': child.lineno,
                                    'context': get_line_context(node, child.lineno)
                                })
        return callers
    except Exception as e:
        logging.warning(f"Error analyzing file {file_path}: {str(e)}")
        return []


def find_parent_class(tree: ast.Module, node: ast.AST) -> Optional[str]:
    """
    Find the parent class of a node, if any.
    
    Args:
        tree: The AST of the file
        node: The node to find the parent class for
    
    Returns:
        The name of the parent class, or None if the node is not in a class
    """
    for potential_parent in ast.walk(tree):
        if isinstance(potential_parent, ast.ClassDef) and node in potential_parent.body:
            return potential_parent.name
    return None


def get_all_python_files(repo) -> List[Dict]:
    """
    Get all Python files in a repository.
    
    Args:
        repo: GitHub repository object
    
    Returns:
        List of dictionaries with information about each Python file
    """
    python_files = []
    contents = repo.get_contents("")
    
    while contents:
        file_content = contents.pop(0)
        if file_content.type == "dir":
            contents.extend(repo.get_contents(file_content.path))
        elif file_content.path.endswith(".py"):
            python_files.append({
                'path': file_content.path,
                'name': os.path.basename(file_content.path)
            })
    
    return python_files


# Example usage
if __name__ == "__main__":
    # Replace with your values
    sample_result = get_call_hierarchy(
        repo_owner="octocat",
        repo_name="Hello-World",
        file_path="hello.py",
        element_name="HelloWorld.greet",
        direction="callers",
        github_token=None  # Replace with your token for higher rate limits
    )
    
    print(f"Found {len(sample_result)} results:")
    for item in sample_result:
        print(f"- {item}")
