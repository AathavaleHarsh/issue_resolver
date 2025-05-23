import { Issue } from '@/components/IssueCard';
import { processIssueWithAgent } from './apiService';

// Extract owner and repo from GitHub URL
const extractRepoInfo = (url: string): { owner: string, repo: string } | null => {
  try {
    // Handle URLs with or without protocol
    const normalizedUrl = url.includes('github.com') 
      ? url 
      : `https://github.com/${url}`;
      
    const urlObj = new URL(normalizedUrl);
    const pathParts = urlObj.pathname.split('/').filter(Boolean);
    
    // Always take the first two parts as owner and repo
    // no matter if there's /issues or other parts following
    if (pathParts.length >= 2) {
      console.log(`Parsed GitHub URL: owner=${pathParts[0]}, repo=${pathParts[1]}`);
      return {
        owner: pathParts[0],
        repo: pathParts[1]
      };
    }
    console.error('Invalid GitHub URL format (needs owner/repo):', url);
    return null;
  } catch (error) {
    console.error('Failed to parse GitHub URL:', error);
    return null;
  }
};

// Fetch issues from YOUR BACKEND API
export const fetchGitHubIssues = async (repoUrl: string): Promise<Issue[]> => {
  console.log('fetchGitHubIssues called with URL:', repoUrl);
  
  // Make sure we have a properly formatted URL with protocol
  let formattedUrl = repoUrl;
  if (!formattedUrl.startsWith('http')) {
    formattedUrl = `https://${formattedUrl}`;
  }
  console.log('Formatted URL:', formattedUrl);
  
  // Still use extractRepoInfo for frontend validation
  const repoInfo = extractRepoInfo(formattedUrl);
  console.log('Extracted repo info:', repoInfo);
  
  if (!repoInfo) {
    const error = new Error('Invalid GitHub repository URL format');
    console.error(error);
    throw error;
  }

  // Construct a clean GitHub repo URL using the extracted info
  const cleanRepoUrl = `https://github.com/${repoInfo.owner}/${repoInfo.repo}`;
  console.log('Clean repo URL for API request:', cleanRepoUrl);

  // Get the base URL from environment variable
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const backendApiUrl = `${apiBaseUrl}/fetch-issues/`; 
  console.log('Sending request to:', backendApiUrl);
  
  try {
    console.log('Request payload:', { repo_url: cleanRepoUrl });
    
    const response = await fetch(backendApiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      mode: 'cors',
      credentials: 'omit', // Change to omit credentials for cross-container requests
      body: JSON.stringify({ repo_url: cleanRepoUrl }), // Send clean URL without /issues
    });
    
    console.log('Response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Error response text:', errorText);
      
      let errorMessage;
      try {
        const errorData = JSON.parse(errorText);
        console.error('Parsed error data:', errorData);
        errorMessage = errorData.detail || `API error: ${response.status}`;
      } catch (parseError) {
        console.error('Failed to parse error JSON:', parseError);
        errorMessage = `Backend API error: ${response.status} - ${errorText.substring(0, 100)}`;
      }
      
      console.error('Throwing error:', errorMessage);
      throw new Error(errorMessage);
    }
    
    const data = await response.json();
    console.log('API response data:', data);
    
    // Transform the backend response (IssueDetail) to match the frontend Issue interface
    if (data && data.issues && Array.isArray(data.issues)) {
      // Map each backend issue to the frontend Issue format
      const adaptedIssues = data.issues.map((backendIssue: any, index: number) => {
        console.log('Processing backend issue:', backendIssue);
        
        // Create an adapted issue that matches the frontend Issue interface
        return {
          id: index + 1, // Generate a synthetic ID
          number: index + 1, // Generate a synthetic number
          title: backendIssue.title || 'Untitled Issue',
          body: backendIssue.description || '',
          html_url: backendIssue.url,
          created_at: new Date().toISOString(), // Use current date as fallback
          user: {
            login: backendIssue.creator_name || 'Unknown User',
            avatar_url: 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png' // Default GitHub avatar
          }
        };
      });
      
      console.log('Adapted issues for frontend:', adaptedIssues);
      return adaptedIssues;
    } else {
      console.error('Invalid response structure from API:', data);
      return []; // Return empty array if response structure is invalid
    }

  } catch (error) {
    console.error('Error fetching GitHub issues from backend:', error);
    // Re-throw the error so the component calling this service can handle it
    if (error instanceof Error) {
        throw error;
    } else {
        throw new Error('An unknown error occurred while fetching issues from the backend.');
    }
  }
};

// Send issue to backend for resolution by the agent
export const askBotToResolve = async (issue: Issue): Promise<{ success: boolean, message: string, clientId?: string }> => {
  console.log('Asking bot to resolve issue:', issue);
  
  try {
    // Call the processIssueWithAgent function from apiService
    const response = await processIssueWithAgent(issue);
    
    return {
      success: true,
      message: `Bot is analyzing issue #${issue.number}: ${issue.title}`,
      clientId: response.client_id // Pass the client_id received from backend
    };
  } catch (error) {
    console.error('Error processing issue with agent:', error);
    return {
      success: false,
      message: error instanceof Error ? error.message : 'An unknown error occurred while processing the issue'
    };
  }
};
