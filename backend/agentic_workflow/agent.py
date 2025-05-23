# agent/workflow.py

import os
import sys
import json
import inspect
from pathlib import Path
from typing import Dict, Any, Callable, Awaitable, List, Optional
from dotenv import load_dotenv
import logging
import logging.config
import asyncio
from openai import OpenAI, APIError

# Add the project root to the Python path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# --- Logging Setup ---
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "level": "DEBUG",
            "formatter": "standard",
            "class": "logging.FileHandler",
            "filename": "logs.log", # Consider making this configurable
            "mode": "a",
        },
    },
    "loggers": {
        "app_logger": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    }
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("app_logger")

# --- Environment Variables & OpenAI Client Setup ---
dotenv_path = Path(project_root) / '.env'
load_dotenv(dotenv_path=dotenv_path)

api_key = os.getenv("OPENROUTER_API_KEY_1")
client: Optional[OpenAI] = None
if not api_key:
    logger.critical("OPENROUTER_API_KEY_1 environment variable not set.")
else:
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        logger.info("OpenAI client initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize OpenAI client: {e}", exc_info=True)

# --- Tool Function Imports ---
try:
    from utils.grep_search import grep_search_github
    from utils.find_file import find_files_by_name as find_file_func # Renamed to avoid name collision
    from utils.get_depen import get_code_dependencies
    from utils.get_hirar import get_call_hierarchy
    from utils.list_directory_contents import list_directory_contents
    from utils.code_structure import view_code_structure
    # Ensure all functions referenced in tools.json are imported here
except ImportError as e:
    logger.error(f"Error importing one or more utility functions: {e}", exc_info=True)
    # Define placeholders if an import fails, so the script can load but tools might not work
    grep_search_github = None
    find_file_func = None
    get_code_dependencies = None
    get_call_hierarchy = None
    list_directory_contents = None
    view_code_structure = None

# --- System Prompt Loading ---
SYSTEM_PROMPT = "You are a helpful AI assistant."
try:
    system_prompt_path = Path(project_root) / 'utils' / 'system_prompt.txt'
    with open(system_prompt_path, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read()
    logger.info(f"System prompt loaded successfully from {system_prompt_path}")
except FileNotFoundError:
    logger.warning(f"System prompt file not found at {system_prompt_path}. Using default prompt.")
except Exception as e:
    logger.error(f"Error loading system prompt: {e}", exc_info=True)

# --- Tool Configuration Loading ---
TOOL_SCHEMAS: List[Dict[str, Any]] = []
TOOL_FUNCTIONS: Dict[str, Callable[..., Any]] = {}

def _extract_json_from_schema_string(schema_str: str) -> Optional[Dict[str, Any]]:
    try:
        # Check if the schema is wrapped in XML-like tags
        import re
        # Look for content between XML-like tags
        xml_pattern = r'<([^>]+)>\s*({[\s\S]*?})\s*</([^>]+)>'
        xml_match = re.search(xml_pattern, schema_str)
        
        if xml_match:
            # Extract the JSON content from between the tags
            json_str = xml_match.group(2)
            logger.debug(f"Extracted JSON from XML-like tags: {json_str[:50]}...")
        else:
            # Fall back to regular JSON extraction
            start_index = schema_str.find('{')
            end_index = schema_str.rfind('}')
            if start_index != -1 and end_index != -1 and end_index > start_index:
                json_str = schema_str[start_index : end_index + 1]
                logger.debug(f"Extracted JSON using bracket search: {json_str[:50]}...")
            else:
                logger.warning(f"Could not find valid JSON delimiters '{{' and '}}' in schema string: {schema_str[:100]}...")
                return None
        
        # Parse the extracted JSON string
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSONDecodeError parsing schema string: {schema_str[:100]}... Error: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error extracting JSON schema: {e}", exc_info=True)
        return None

def load_tool_configurations():
    global TOOL_SCHEMAS, TOOL_FUNCTIONS
    tools_json_path = Path(project_root) / 'utils' / 'tools.json'

    # Map tool names from tools.json to actual Python functions
    available_python_functions = {
        'grep_search': grep_search_github,
        'find_file': find_file_func,
        'list_dir': list_directory_contents,
        'get_code_dependencies': get_code_dependencies,
        'get_call_hierarchy': get_call_hierarchy,
        'view_code_structure': view_code_structure
    }

    try:
        with open(tools_json_path, 'r', encoding='utf-8') as f:
            tools_data_from_json = json.load(f)
        
        loaded_schemas = []
        loaded_functions = {}

        for tool_name, tool_info in tools_data_from_json.items():
            if not isinstance(tool_info, dict) or 'schema' not in tool_info:
                logger.warning(f"Tool '{tool_name}' in tools.json is malformed or missing 'schema'. Skipping.")
                continue

            parameter_schema = _extract_json_from_schema_string(tool_info['schema'])
            if not parameter_schema:
                logger.warning(f"Could not parse parameters for tool '{tool_name}'. Skipping.")
                continue
            
            openapi_tool_schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_info.get("description", f"Execute {tool_name}"),
                    "parameters": parameter_schema
                }
            }
            loaded_schemas.append(openapi_tool_schema)

            if tool_name in available_python_functions:
                func_ref = available_python_functions[tool_name]
                if func_ref is not None:
                    loaded_functions[tool_name] = func_ref
                else:
                    logger.warning(f"Python function for tool '{tool_name}' is None (likely import error). Tool will not be callable.")
            else:
                logger.warning(f"Python function for tool '{tool_name}' not found in available_python_functions. Tool will not be callable.")

        TOOL_SCHEMAS = loaded_schemas
        TOOL_FUNCTIONS = loaded_functions
        
        if TOOL_SCHEMAS:
            logger.info(f"Successfully loaded {len(TOOL_SCHEMAS)} tool schemas.")
        else:
            logger.warning("No tool schemas were loaded. Agent may not use tools effectively.")
        if TOOL_FUNCTIONS:
            logger.info(f"Successfully mapped {len(TOOL_FUNCTIONS)} tool functions.")
        else:
            logger.warning("No tool functions were mapped. Agent will not be able to execute tools.")

    except FileNotFoundError:
        logger.error(f"tools.json not found at {tools_json_path}. No tools will be loaded.")
    except json.JSONDecodeError:
        logger.error(f"Error decoding {tools_json_path}. Ensure it is valid JSON.", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred loading tool configurations: {e}", exc_info=True)

load_tool_configurations() # Load at module import

# Debug log to verify tool loading
logger.debug(f"TOOL_SCHEMAS loaded: {len(TOOL_SCHEMAS)} schemas")
for idx, schema in enumerate(TOOL_SCHEMAS):
    logger.debug(f"  Tool {idx+1}: {schema.get('function', {}).get('name', 'unknown')}")
logger.debug(f"TOOL_FUNCTIONS loaded: {list(TOOL_FUNCTIONS.keys())}")

# --- Type Hint for Async Logging Callback ---
AsyncLogCallback = Callable[[str], Awaitable[None]]

# --- Main Agent Processing Function ---
async def process_issue_with_agent(
    issue_data: Dict[str, Any],
    log_callback: AsyncLogCallback
):
    """
    Processes a single GitHub issue using the OpenAI agentic workflow.

    Args:
        issue_data: A dictionary containing the details of the issue (title, description, etc.).
        log_callback: An async function to call for sending log messages back.
    """
    if not client:
        await log_callback("OpenAI client not initialized. Cannot process issue.")
        logger.error("Attempted to process issue, but OpenAI client is not initialized.")
        return {"error": "OpenAI client not initialized", "status": "client_error"}

    await log_callback(f"--- Agent Initializing for: {issue_data.get('title', 'N/A')} ---")
    logger.info(f"Starting agent processing for issue: {issue_data.get('title', 'N/A')}")

    initial_user_message = (
        f"Please analyze the following GitHub issue and propose a solution or next steps. "
        f"Consider using available tools if they can help gather more context or information.\n\n"
        f"Title: {issue_data.get('title', 'N/A')}\n"
        f"Repository: {issue_data.get('repo_owner', 'N/A')}/{issue_data.get('repo_name', 'N/A')}\n"
        f"Issue Number: {issue_data.get('issue_number', 'N/A')}\n"
        f"Labels: {', '.join(issue_data.get('labels', []))}\n"
        f"Creator: {issue_data.get('creator_name', 'N/A')}\n"
        f"Status: {issue_data.get('status', 'N/A')}\n"
        f"URL: {issue_data.get('url', 'N/A')}\n"
        f"Description:\n{issue_data.get('description', 'No description provided.')}"
    )

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": initial_user_message}
    ]

    await log_callback("Prepared initial prompt for LLM.")
    logger.debug(f"Initial LLM User Message:\n{initial_user_message}")
    await log_callback(f"Initial Message (Preview): {initial_user_message[:150]}...")

    MAX_ITERATIONS = 7 # Allow a few tool uses and responses
    iteration_count = 0

    while iteration_count < MAX_ITERATIONS:
        iteration_count += 1
        await log_callback(f"--- Agent Iteration {iteration_count}/{MAX_ITERATIONS} ---")
        logger.info(f"Agent Iteration {iteration_count}/{MAX_ITERATIONS}")

        try:
            await log_callback("Sending request to LLM...")
            logger.info("Sending request to OpenAI API...")
            
            completion_params = {
                "model": "meta-llama/llama-3.3-70b-instruct:free",  # Using the model from your .env
                "messages": messages,
                "temperature": 0.5,  # Slightly lower for more deterministic tool use
                "max_tokens": 2000,  # Set a safe limit within your 4000 token budget
            }
            if TOOL_SCHEMAS: # Only pass tools if they are loaded
                completion_params["tools"] = TOOL_SCHEMAS
                completion_params["tool_choice"] = "auto"
            else:
                logger.warning("No tools loaded/configured; LLM will not use tools.")
                await log_callback("Warning: No tools configured for LLM.")

            response = await asyncio.to_thread(
                client.chat.completions.create, **completion_params
            )
            
            await log_callback("Received response from LLM.")
            logger.info("Received response from OpenAI API.")

            response_message = response.choices[0].message
            messages.append(response_message) # Add assistant's response (with or without tool calls)

            tool_calls = response_message.tool_calls

            if tool_calls:
                logger.info(f"LLM requested {len(tool_calls)} tool_call(s).")
                await log_callback(f"LLM requested {len(tool_calls)} tool(s). Executing...")

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args_str = tool_call.function.arguments
                    tool_call_id = tool_call.id

                    await log_callback(f"Tool Call ID: {tool_call_id}, Name: {function_name}, Args: {function_args_str}")
                    logger.info(f"Tool Call ID: {tool_call_id}, Name: {function_name}, Args: {function_args_str}")

                    try:
                        function_args = json.loads(function_args_str)
                    except json.JSONDecodeError as e:
                        error_msg = f"Error parsing JSON arguments for {function_name}: {e}. Args: {function_args_str}"
                        logger.error(error_msg, exc_info=True)
                        await log_callback(f"Error: Could not parse arguments for {function_name}.")
                        messages.append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps({"error": "Invalid JSON arguments provided by LLM", "details": str(e)})
                        })
                        continue # Process next tool call or iteration

                    if function_name in TOOL_FUNCTIONS:
                        function_to_call = TOOL_FUNCTIONS[function_name]
                        tool_response_content = ""
                        try:
                            if inspect.iscoroutinefunction(function_to_call):
                                tool_result = await function_to_call(**function_args)
                            else:
                                loop = asyncio.get_running_loop()
                                tool_result = await loop.run_in_executor(None, lambda: function_to_call(**function_args))
                            
                            if not isinstance(tool_result, str):
                                tool_response_content = json.dumps(tool_result, indent=2)
                            else:
                                tool_response_content = tool_result
                            
                            await log_callback(f"Tool {function_name} executed. Response (preview): {tool_response_content[:150]}...")
                            logger.debug(f"Tool {function_name} raw response: {tool_result}")
                            logger.info(f"Tool {function_name} JSON response preview: {tool_response_content[:200]}...")

                        except Exception as e:
                            error_msg = f"Error executing tool {function_name} with args {function_args}: {e}"
                            logger.error(error_msg, exc_info=True)
                            await log_callback(f"Error executing {function_name}: {str(e)[:100]}...")
                            tool_response_content = json.dumps({"error": f"Tool execution failed: {str(e)}"})
                        
                        messages.append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "name": function_name,
                            "content": tool_response_content,
                        })
                    else:
                        error_msg = f"LLM requested unknown tool: '{function_name}'."
                        logger.error(error_msg)
                        await log_callback(f"Error: Tool {function_name} not recognized by agent.")
                        messages.append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps({"error": "Tool not implemented or recognized by the agent."})
                        })
                # After processing all tool calls for this turn, loop back to let the LLM process tool responses.
            
            else: # No tool calls, LLM provided a direct text response
                final_response_text = response_message.content
                if final_response_text:
                    await log_callback(f"LLM Final Response: {final_response_text[:200]}...")
                    logger.info(f"LLM provided final text response for issue: {issue_data.get('title', 'N/A')}")
                    logger.debug(f"LLM Final Response Text:\n{final_response_text}")
                    await log_callback("LLM did not request further tool calls. Task considered complete.")
                    return {"response": final_response_text, "status": "completed", "iterations": iteration_count, "messages": messages}
                else:
                    # This case (no tool_calls and no content) should be rare for well-behaved models
                    await log_callback("LLM response had no content and no tool calls. Ending interaction.")
                    logger.warning("LLM response was empty (no content, no tool_calls).")
                    return {"error": "LLM provided an empty response.", "status": "empty_response", "iterations": iteration_count, "messages": messages}

        except APIError as e:
            error_message = f"OpenAI API Error (Iteration {iteration_count}): Code {e.status_code} - {e.message}"
            logger.critical(error_message, exc_info=True)
            await log_callback(f"Error: OpenAI API call failed: {e.message}")
            return {"error": error_message, "status": "api_error", "iterations": iteration_count, "messages": messages}
        except Exception as e:
            error_message = f"An unexpected error occurred in agent iteration {iteration_count}: {e}"
            logger.critical(error_message, exc_info=True)
            await log_callback(f"Error: An unexpected critical error occurred: {str(e)[:100]}...")
            return {"error": error_message, "status": "unexpected_error", "iterations": iteration_count, "messages": messages}

    # Max iterations reached
    await log_callback(f"Max iterations ({MAX_ITERATIONS}) reached. Ending interaction.")
    logger.warning(f"Max iterations reached for issue: {issue_data.get('title', 'N/A')}")
    last_message_content = messages[-1].get("content") if messages else "No messages recorded."
    return {
        "response": last_message_content,
        "error": "Max iterations reached.", 
        "status": "max_iterations_reached", 
        "iterations": iteration_count,
        "messages": messages
    }

# # --- Test Code ---
# async def test_logger(message: str):
#     """A simple async logger for testing purposes."""
#     timestamp = asyncio.get_running_loop().time() # Get a timestamp for async context
#     print(f"[{timestamp:.2f} Test Log] {message}")
#     logger.info(f"[Test Log Passthrough] {message}") # Also send to main logger

# async def test_agent():
#     """Test the agent with a sample GitHub issue description that might involve tool use."""
#     sample_issue = {
#         "title": "Login button unresponsive after deployment",
#         "repo_owner": "example-corp",
#         "repo_name": "webapp-project",
#         "issue_number": "GH-451",
#         "labels": ["bug", "frontend", "critical"],
#         "creator_name": "jane.doe",
#         "status": "open",
#         "url": "https://github.com/example-corp/webapp-project/issues/451",
#         "description": (
#             "The main login button on the homepage has become unresponsive after the v2.3.1 deployment last night. "
#             "No errors are visible in the browser console immediately. Users clicking it see no action. "
#             "Could be a frontend event handler issue or a problem with the backend auth API not being called. "
#             "Please investigate: \n1. Check the `LoginButton.tsx` component for recent changes. Path: `src/components/auth/LoginButton.tsx`\n"
#             "2. Search for error logs related to `/api/v1/auth/login` on the backend from the last 12 hours.\n"
#             "3. List directory contents of `src/components/auth/` to see related files."
#         )
#     }

#     logger.info("--- Starting Agent Test Scenario --- ")
#     await test_logger("Initiating agent test with a sample issue...")
    
#     if not client:
#         await test_logger("CRITICAL: OpenAI client is not initialized. Test cannot proceed with API calls.")
#         logger.critical("OpenAI client is None in test_agent. Aborting test that requires API interaction.")
#         return

#     if not TOOL_SCHEMAS:
#         await test_logger("Warning: TOOL_SCHEMAS is empty. Agent will not be able to use tools.")
#         logger.warning("TOOL_SCHEMAS is empty during test_agent. This is likely not intended if tools are expected.")
#     if not TOOL_FUNCTIONS:
#         await test_logger("Warning: TOOL_FUNCTIONS is empty. Agent will not be able to execute any tools.")
#         logger.warning("TOOL_FUNCTIONS is empty during test_agent. Tool execution will fail.")

#     await test_logger(f"System Prompt for test: {SYSTEM_PROMPT[:100]}...")
#     await test_logger(f"Number of tool schemas loaded for test: {len(TOOL_SCHEMAS)}")
#     await test_logger(f"Tools available for test: {list(TOOL_FUNCTIONS.keys())}")

#     result = await process_issue_with_agent(sample_issue, test_logger)
#     #         "html_url": "https://github.com/exampleuser"
#     #     },
#     #     "labels": [
#     #         {"name": "enhancement"},
#     #         {"name": "help wanted"}
#     #     ]
#     # }
#     test_issue = {
#     "title": "Error when loading model with custom tokenizer",
#     "number": 123,
#     "html_url": "https://github.com/unslothai/unsloth/issues/123",
#     "body": "Getting an error when trying to load a model with a custom tokenizer. The error occurs in `src/loading.py` around line 42.",
#     "state": "open",
#     "labels": ["bug"]
# }

#     # Run the agent with the test issue
#     print("=== Starting Agent Test ===")
#     print(f"Issue: {test_issue['title']} (#{test_issue['number']})")
#     print("-" * 50)
    
#     await process_issue_with_agent(test_issue, test_logger)
#     print("\\n=== Agent Test Complete ===")

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(test_agent())