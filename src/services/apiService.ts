import { Issue } from '@/components/IssueCard';

// Base URL for API requests
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';

// Interface for backend response
interface ProcessIssueResponse {
  message: string;
  client_id: string;
}

// Interface for WebSocket message
interface WebSocketMessage {
  content: string;
  timestamp: Date;
  isAgent: boolean;
}

/**
 * Sends an issue to the backend for processing by the agent
 * @param issue The GitHub issue to process
 * @returns A promise containing the client_id for WebSocket connection and success message
 */
export const processIssueWithAgent = async (issue: Issue): Promise<ProcessIssueResponse> => {
  const endpoint = `${API_BASE_URL}/process-issue/`;
  
  // Convert the frontend Issue to the backend's expected IssueDetail format
  const issueDetail = {
    title: issue.title,
    description: issue.body,
    creator_name: issue.user?.login || 'Unknown',
    status: 'open', // Assuming all issues are open
    url: issue.html_url
  };
  
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ 
        issue: issueDetail
      }),
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage;
      
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || `API error: ${response.status}`;
      } catch (parseError) {
        errorMessage = `Backend API error: ${response.status} - ${errorText.substring(0, 100)}`;
      }
      
      throw new Error(errorMessage);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error processing issue with agent:', error);
    throw error;
  }
};

/**
 * Creates a WebSocket connection to receive real-time agent logs
 * @param clientId The client_id received from processIssueWithAgent
 * @param onMessage Callback function for handling incoming messages
 * @returns The WebSocket instance
 */
export const createAgentWebSocket = (
  clientId: string,
  onMessage: (message: WebSocketMessage) => void
): WebSocket => {
  // Construct the WebSocket URL
  // If it starts with '/', convert to a proper WebSocket URL using the current host
  let wsUrl: string;
  if (WS_BASE_URL.startsWith('/')) {
    // Use current protocol and host, but switch to ws:// or wss://
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host; // includes host:port
    wsUrl = `${protocol}//${host}${WS_BASE_URL}/issue-logs/${clientId}`;
  } else {
    // Use the provided WebSocket URL directly
    wsUrl = `${WS_BASE_URL}/issue-logs/${clientId}`;
  }
  
  console.log('Connecting to WebSocket URL:', wsUrl);
  const socket = new WebSocket(wsUrl);
  
  socket.onopen = () => {
    console.log(`WebSocket connection established for client: ${clientId}`);
  };
  
  socket.onmessage = (event) => {
    const text = event.data;
    // Handle the structured message type
    // In this case we're getting plain text messages from the backend
    // Prefix AGENT: is already added by the backend
    
    const message: WebSocketMessage = {
      content: text,
      timestamp: new Date(),
      isAgent: text.startsWith('AGENT:')
    };
    
    onMessage(message);
  };
  
  socket.onerror = (error) => {
    console.error('WebSocket error:', error);
    onMessage({
      content: 'Error: Connection to agent failed. Please try again.',
      timestamp: new Date(),
      isAgent: true
    });
  };
  
  socket.onclose = (event) => {
    console.log(`WebSocket closed with code: ${event.code}, reason: ${event.reason}`);
    // Optionally notify the user that the connection has closed
    if (event.code !== 1000) { // 1000 is normal closure
      onMessage({
        content: 'Connection to agent closed. The analysis may be complete.',
        timestamp: new Date(),
        isAgent: true
      });
    }
  };
  
  return socket;
};
