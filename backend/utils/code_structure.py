import ast
import base64
from github import Github
from github import Auth
import os
from typing import Dict, List, Optional, Union, Any

def view_code_structure(file_path: str, element_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Provides the structure of a code file or the definition of a specific code element.
    
    Args:
        file_path: Path to the file on GitHub (format: 'owner/repo/path/to/file.py')
        element_name: Optional name of a specific element to view (e.g., 'MyClass.my_function')
    
    Returns:
        Dictionary containing structured representation of code elements or specific element details
    """
    try:
        # Parse the GitHub file path
        parts = file_path.split('/')
        if len(parts) < 3:
            return {"error": "Invalid file path format. Expected 'owner/repo/path/to/file.py'"}
        
        owner = parts[0]
        repo_name = parts[1]
        file_path_in_repo = '/'.join(parts[2:])
        
        # Initialize GitHub API client
        # Try to get token from environment variable first
        access_token = os.getenv("GITHUB_TOKEN")
        
        if access_token:
            auth = Auth.Token(access_token)
            g = Github(auth=auth)
        else:
            # Without a token, you'll be subject to stricter rate limits
            g = Github()
        
        # Get repository and file content
        try:
            repo = g.get_repo(f"{owner}/{repo_name}")
            file_content = repo.get_contents(file_path_in_repo)
            
            # Decode content
            if hasattr(file_content, 'content'):
                content = base64.b64decode(file_content.content).decode('utf-8')
            else:
                return {"error": "Could not retrieve file content"}
                
            # Parse the code structure
            return _analyze_code_structure(content, element_name)
            
        except Exception as e:
            return {"error": f"GitHub API error: {str(e)}"}
        
    finally:
        # Close GitHub connection if needed
        try:
            if 'g' in locals():
                pass  # Modern PyGithub handles connections automatically
        except:
            pass

def _analyze_code_structure(code_content: str, element_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyzes Python code structure using the AST module.
    
    Args:
        code_content: String containing Python code
        element_name: Optional name of a specific element to view
    
    Returns:
        Dictionary containing code structure information
    """
    try:
        # Parse the code into an AST
        tree = ast.parse(code_content)
        
        # Initialize structure containers
        imports = []
        classes = []
        functions = []
        global_variables = []
        
        # Extract structure information
        for node in ast.iter_child_nodes(tree):
            # Handle imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(_extract_import_info(node))
            
            # Handle classes
            elif isinstance(node, ast.ClassDef):
                class_info = _extract_class_info(node)
                classes.append(class_info)
                
                # If looking for a specific element in this class
                if element_name and element_name.startswith(f"{node.name}."):
                    target_element = element_name.split('.', 1)[1]
                    for method in class_info.get('methods', []):
                        if method['name'] == target_element:
                            return {"element": method}
            
            # Handle functions
            elif isinstance(node, ast.FunctionDef):
                function_info = _extract_function_info(node)
                functions.append(function_info)
                
                # If looking for this specific function
                if element_name and element_name == node.name:
                    return {"element": function_info}
            
            # Handle global variables
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        value = "<complex value>"
                        if isinstance(node.value, ast.Constant):
                            value = node.value.value
                        elif isinstance(node.value, ast.Name):
                            value = f"<reference to {node.value.id}>"
                        global_variables.append({
                            "name": target.id,
                            "value": value
                        })
        
        # If looking for a specific element but not found
        if element_name:
            return {"error": f"Element '{element_name}' not found in the file"}
        
        # Return complete structure
        return {
            "imports": imports,
            "classes": classes,
            "functions": functions,
            "global_variables": global_variables
        }
        
    except SyntaxError as e:
        return {"error": f"Syntax error in code: {str(e)}"}
    except Exception as e:
        return {"error": f"Error analyzing code structure: {str(e)}"}

def _extract_import_info(node: Union[ast.Import, ast.ImportFrom]) -> Dict[str, Any]:
    """Extract information about import statements"""
    if isinstance(node, ast.Import):
        return {
            "type": "import",
            "names": [name.name for name in node.names]
        }
    else:  # ImportFrom
        module = node.module or ''
        return {
            "type": "import_from",
            "module": module,
            "names": [name.name for name in node.names]
        }

def _extract_function_info(node: ast.FunctionDef) -> Dict[str, Any]:
    """Extract information about a function definition"""
    # Get docstring if available
    docstring = ast.get_docstring(node) or ""
    
    # Get parameters
    params = []
    for arg in node.args.args:
        params.append(arg.arg)
    
    # Get function body as source code
    body_lines = []
    for body_node in node.body:
        if not isinstance(body_node, ast.Expr) or not isinstance(body_node.value, ast.Constant):
            # Skip the docstring node
            start_line = body_node.lineno
            end_line = body_node.end_lineno if hasattr(body_node, 'end_lineno') else start_line
            body_lines.append(f"Lines {start_line}-{end_line}")
    
    return {
        "type": "function",
        "name": node.name,
        "params": params,
        "docstring": docstring,
        "decorators": [d.id for d in node.decorator_list if isinstance(d, ast.Name)],
        "line_range": (node.lineno, getattr(node, 'end_lineno', node.lineno)),
        "body": body_lines
    }

def _extract_class_info(node: ast.ClassDef) -> Dict[str, Any]:
    """Extract information about a class definition"""
    # Get docstring if available
    docstring = ast.get_docstring(node) or ""
    
    # Get base classes
    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(f"{base.value.id}.{base.attr}" if isinstance(base.value, ast.Name) else "<complex>")
    
    # Get methods and attributes
    methods = []
    attributes = []
    
    for item in node.body:
        if isinstance(item, ast.FunctionDef):
            methods.append(_extract_function_info(item))
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    value = "<complex value>"
                    if isinstance(item.value, ast.Constant):
                        value = item.value.value
                    attributes.append({
                        "name": target.id,
                        "value": value
                    })
    
    return {
        "type": "class",
        "name": node.name,
        "bases": bases,
        "docstring": docstring,
        "methods": methods,
        "attributes": attributes,
        "line_range": (node.lineno, getattr(node, 'end_lineno', node.lineno))
    }
