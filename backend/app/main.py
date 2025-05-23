# app.py (Unified Version)

import re
import asyncio
import uuid
import functools # For partial function
import logging
import logging.config
import sys # Needed for stderr logging in background task exception
from typing import List, Optional, Dict, Any

from fastapi import (
    FastAPI,
    HTTPException,
    Body,
    WebSocket,
    WebSocketDisconnect,
    BackgroundTasks,
    Request,
    Response
)

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field

# Clean direct imports for proper agent and utils integration
from utils.fetch_issues import fetch_issues
from agentic_workflow.agent import process_issue_with_agent

# --- Logging Configuration ---
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
            "stream": "ext://sys.stdout",  # Default is stderr
        },
        "file": {
            "level": "DEBUG",
            "formatter": "standard",
            "class": "logging.FileHandler",
            "filename": "logs.log",
            "mode": "a", # Append mode
        },
    },
    "loggers": {
        "app_logger": { # Specific logger for our app
            "handlers": ["console", "file"],
            "level": "DEBUG", # Capture DEBUG level and above
            "propagate": False,
        },
        "uvicorn.access": { # Optional: Configure access logs if needed
             "handlers": ["console", "file"],
             "level": "INFO",
             "propagate": False,
        },
        "uvicorn.error": {
             "handlers": ["console", "file"],
             "level": "INFO",
             "propagate": False,
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("app_logger")

# --- Connection Manager for WebSockets (Keep as before) ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected for client_id: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            # Optionally send a disconnect message before removing
            # try:
            #     await self.active_connections[client_id].send_text("INFO: Server disconnecting.")
            # except Exception:
            #     pass # Ignore errors if client already closed
            del self.active_connections[client_id]
            logger.info(f"WebSocket disconnected for client_id: {client_id}")

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(message)
                # logger.debug(f"Sent to {client_id}: {message[:100]}...") # Optional: log sent messages (can be verbose)
            except WebSocketDisconnect:
                logger.warning(f"Client {client_id} disconnected before message could be sent.")
                self.disconnect(client_id) # Clean up connection state
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id) # Assume connection is broken
        # else:
        #     logger.debug(f"Client {client_id} not connected, message not sent: {message[:100]}...")

manager = ConnectionManager()

# --- Pydantic Models (Keep as before) ---
class RepoURL(BaseModel):
    repo_url: HttpUrl = Field(..., examples=["https://github.com/tiangolo/fastapi"])

class IssueDetail(BaseModel):
    title: str
    description: Optional[str] = None
    creator_name: str
    status: str
    url: str

class IssueListResponse(BaseModel):
    repository: str
    issues: List[IssueDetail]
    count: int

class ProcessIssueRequest(BaseModel):
    issue: IssueDetail

class ProcessIssueResponse(BaseModel):
    message: str
    client_id: str

# --- FastAPI App (Keep as before) ---
app = FastAPI(
    title="GitHub Issue Fetcher & Processor API",
    description="Fetches GitHub issues and provides an endpoint to trigger processing with log streaming via WebSockets.",
    version="1.1.0",
)

# --- Add CORS Middleware ---
# Define allowed origins (adjust as needed for development/production)
origins = [
    "http://localhost:3000",  # React development server
    "http://localhost:5173",  # Common Vite/React port
    "http://localhost:8080",  # Add Vite's default port
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
    "http://frontend",         # Docker service name 
    "http://frontend:80",      # Docker service with port
    "http://frontend:8080",    # Docker service with exposed port
    # Additional origins for Docker environments
    "http://localhost",
    "http://127.0.0.1",
    "*",                      # Allow all origins (widest setting)
    # Add your frontend production domain here if applicable, e.g.:
    # "https://your-frontend-domain.com",
]

# Create the FastAPI app with special CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # List of origins allowed to make requests
    allow_credentials=True, # Allow cookies to be included in requests
    allow_methods=["*"],    # Allow all standard methods (GET, POST, etc.)
    allow_headers=["*"],    # Allow all headers
    expose_headers=["*"],   # Expose all response headers
    max_age=600,           # Cache preflight requests for 10 minutes
)

# --- Helper Function for URL Parsing (Enhanced version from main.py) ---
def parse_github_url(url: str) -> Optional[tuple[str, str]]:
    # First, clean up any trailing /issues or similar paths
    url = re.sub(r"/(issues|pulls|wiki|pulse|graphs|settings)/?.*$", "", str(url).strip())
    
    # Then use the standard pattern to extract owner and repo
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:/|.git)?$", url)
    
    if match:
        owner = match.group(1)
        repo = match.group(2)
        logger.debug(f"Successfully parsed GitHub URL: {url} -> owner={owner}, repo={repo}")
        return owner, repo
    
    logger.warning(f"Failed to parse GitHub URL after cleanup: {url}")
    return None

# --- Modified Background Task Runner ---
async def run_agentic_workflow_background(issue_data_dict: Dict[str, Any], client_id: str):
    """
    Wrapper function to run the agent workflow in the background.
    Creates a logging callback bound to the specific client_id.
    """
    logger.info(f"Background task started for client {client_id} on issue: {issue_data_dict.get('title', 'N/A')[:30]}...")

    # Create a logging callback function specific to this client_id
    # This function will be passed to the agent workflow.
    async def agent_log_callback(message: str):
        # Prepend "AGENT:" to distinguish logs from this source
        log_message = f"AGENT Client {client_id}: {message}" 
        logger.info(log_message) # Log to file/console first
        await manager.send_personal_message(f"AGENT: {message}", client_id) # Then send to WebSocket
        
    try:
        # Call the actual agent processing function from agent/workflow.py
        await process_issue_with_agent(
            issue_data=issue_data_dict,
            log_callback=agent_log_callback
        )
        # Optionally send a final "complete" message
        await manager.send_personal_message("INFO: Processing complete.", client_id)
        logger.info(f"Background task completed successfully for client {client_id}.")

    except Exception as e:
        # Log any unexpected errors during agent execution
        error_msg = f"ERROR: Unhandled exception in background agent task for {client_id}: {e}"
        logger.error(error_msg, exc_info=True) # Include stack trace in log
        try:
            # Attempt to notify the client about the failure
            await manager.send_personal_message(error_msg, client_id)
        except Exception as send_e:
            logger.error(f"Could not send error message to client {client_id}: {send_e}")
    finally:
        # Optional: You might want to automatically close the WebSocket connection
        # from the server side when the task finishes or errors out.
        # Be cautious with this, the client might want to stay connected.
        # if client_id in manager.active_connections:
        #     logger.info(f"Closing WebSocket connection for client {client_id} after task completion/error.")
        #     await manager.active_connections[client_id].close()
        #     manager.disconnect(client_id) # Ensure cleanup
        pass # Decide on connection closing strategy


# --- API Endpoints ---

# Add OPTIONS route handler to properly handle preflight requests
@app.options("/fetch-issues/")
async def options_fetch_issues(request: Request):
    # This handler will be triggered for OPTIONS requests before the actual POST
    # and will return a proper CORS response without validating request body
    logger.info(f"Handling OPTIONS preflight request for /fetch-issues/")
    return Response(
        content="",
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",  # Or specific origins
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "600",  # Cache preflight for 10 minutes
        },
    )

@app.post("/fetch-issues/", response_model=IssueListResponse, tags=["GitHub Issues"])
async def get_github_issues(payload: RepoURL = Body(...)):
    # (Keep implementation as before)
    logger.info(f"Received request for URL: {payload.repo_url}")
    parsed_url = parse_github_url(str(payload.repo_url))
    if not parsed_url:
        logger.warning(f"Invalid GitHub URL received: {payload.repo_url}")
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub repository URL format.",
        )
    owner, repo_name = parsed_url
    logger.info(f"Parsed owner: {owner}, repo: {repo_name}")
    try:
        issues_list: List[Dict[str, Any]] = fetch_issues(owner, repo_name, max_issues_to_print=10)
        logger.info(f"Successfully fetched {len(issues_list)} issues for {owner}/{repo_name}")
        return IssueListResponse(
            repository=f"{owner}/{repo_name}",
            issues=issues_list,
            count=len(issues_list)
        )
    except Exception as e:
        logger.error(f"Failed to fetch issues for {owner}/{repo_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch issues from GitHub: {e}"
        )
@app.post("/process-issue/", response_model=ProcessIssueResponse, tags=["Agentic Workflow"])
async def process_single_issue(
    payload: ProcessIssueRequest,
    background_tasks: BackgroundTasks # Inject BackgroundTasks
):
    """
    Receives issue details, starts the agentic workflow in the background,
    and returns a client_id for WebSocket log streaming.
    """
    issue_data = payload.issue
    # Convert Pydantic model to dict for easier passing if needed,
    # though passing the model instance directly often works too.
    issue_data_dict = issue_data.model_dump()

    logger.info(f"Received request to process issue: {issue_data.title[:50]}...")

    client_id = str(uuid.uuid4())

    # Add the *wrapper* background task function
    background_tasks.add_task(
        run_agentic_workflow_background, # Call the wrapper
        issue_data_dict,                 # Pass the issue data as dict
        client_id                        # Pass the unique client ID
    )

    logger.info(f"Agentic workflow scheduled for issue '{issue_data.title[:30]}' with client_id: {client_id}")

    return ProcessIssueResponse(
        message="Issue processing started in the background. Connect WebSocket for logs.",
        client_id=client_id
    )

# --- WebSocket Endpoint (Keep as before) ---
@app.websocket("/ws/issue-logs/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for clients to connect and receive logs
    for a specific processing task identified by client_id.
    """
    await manager.connect(websocket, client_id)
    try:
        # Keep the connection alive. Messages are pushed by the background task.
        while True:
            # Keep connection open by periodically checking or sleeping
            # This also allows detecting disconnects faster potentially
            await asyncio.sleep(1)
            # Check if connection still exists in manager, otherwise break
            if client_id not in manager.active_connections:
                 logger.info(f"WebSocket {client_id} no longer managed, closing server-side loop.")
                 break
            # Optional: Implement a simple ping/pong mechanism if needed
            # try:
            #     await websocket.send_text("PING")
            #     # If pong is needed, wait for client response with timeout
            # except Exception:
            #     break # Assume disconnected


    except WebSocketDisconnect:
        logger.warning(f"WebSocket {client_id} disconnected (client-side).")
    except Exception as e:
        logger.error(f"WebSocket Error for {client_id}: {e}")
    finally:
        # Ensure cleanup happens regardless of how the loop exits
        manager.disconnect(client_id)


@app.get("/", tags=["General"])
async def read_root():
     # (Keep implementation as before)
    return {"message": "Welcome to the GitHub Issue Fetcher & Processor API. Use /docs for details."}
