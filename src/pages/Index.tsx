
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchGitHubIssues, askBotToResolve } from '@/services/githubService';
import SearchBar from '@/components/SearchBar';
import IssueCard, { Issue } from '@/components/IssueCard';
import { toast } from '@/components/ui/sonner';

const Index = () => {
  const navigate = useNavigate();
  const [issues, setIssues] = useState<Issue[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [processingIssueId, setProcessingIssueId] = useState<number | null>(null);

  const handleSearch = async (repoUrl: string) => {
    setIsLoading(true);
    try {
      const fetchedIssues = await fetchGitHubIssues(repoUrl);
      setIssues(fetchedIssues);
      
      if (fetchedIssues.length === 0) {
        toast.info('No open issues found in this repository');
      } else {
        toast.success(`Found ${fetchedIssues.length} issues`);
      }
    } catch (error) {
      console.error('Error fetching issues:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to fetch issues');
      setIssues([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAskBot = async (issue: Issue) => {
    setProcessingIssueId(issue.id);
    try {
      const result = await askBotToResolve(issue);
      if (result.success && result.clientId) {
        // Navigate to the chat page with the issue data and clientId for WebSocket connection
        navigate('/chat', { 
          state: { 
            issue, 
            clientId: result.clientId 
          } 
        });
        toast.success(result.message);
      } else {
        toast.error(result.message || 'Failed to process request');
      }
    } catch (error) {
      console.error('Error asking bot:', error);
      toast.error('Failed to process request');
    } finally {
      setProcessingIssueId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="github-header">
        <div className="github-container">
          <h1 className="text-2xl font-bold text-center text-gray-900">
            GitHub Issue Explorer
          </h1>
        </div>
      </header>
      
      <main className="github-container py-8">
        <SearchBar onSearch={handleSearch} isLoading={isLoading} />
        
        {isLoading ? (
          <div className="flex justify-center my-16">
            <div className="animate-pulse text-gray-500">Loading issues...</div>
          </div>
        ) : (
          <div className="space-y-4">
            {issues.length > 0 ? (
              issues.map((issue) => (
                <IssueCard 
                  key={issue.id}
                  issue={issue}
                  onAskBot={handleAskBot}
                  isProcessing={processingIssueId === issue.id}
                />
              ))
            ) : (
              <div className="text-center bg-white p-8 rounded-md border border-gray-200">
                <p className="text-gray-500">
                  {issues.length === 0 && isLoading === false 
                    ? "Search for a GitHub repository to view its issues"
                    : "No open issues found in this repository"}
                </p>
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="py-6 border-t border-gray-200">
        <div className="github-container">
          <p className="text-center text-gray-500 text-sm">
            GitHub Issue Explorer - Built with React
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
