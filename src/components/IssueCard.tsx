
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Bot } from 'lucide-react';

export interface Issue {
  id: number;
  title: string;
  body: string;
  number: number;
  html_url: string;
  user: {
    login: string;
    avatar_url: string;
  };
  created_at: string;
}

interface IssueCardProps {
  issue: Issue;
  onAskBot: (issue: Issue) => void;
  isProcessing?: boolean;
}

const IssueCard = ({ issue, onAskBot, isProcessing = false }: IssueCardProps) => {
  const [expanded, setExpanded] = useState(false);

  // Format the date
  const formattedDate = new Date(issue.created_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });

  // Truncate the body text if it's too long
  const truncatedBody = issue.body 
    ? issue.body.length > 150 
      ? `${issue.body.substring(0, 150)}...` 
      : issue.body
    : 'No description provided.';

  return (
    <div 
      className={`github-card cursor-pointer transition-all duration-300 ${expanded ? 'scale-[1.02]' : ''}`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between">
        <div className="flex-grow">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">{issue.title}</h3>
          <div className="flex items-center text-sm text-gray-500 mb-3">
            <span>#{issue.number}</span>
            <span className="mx-2">•</span>
            <span>Opened on {formattedDate}</span>
            <span className="mx-2">•</span>
            <span>by {issue.user.login}</span>
          </div>
          <div className="text-gray-700">
            {expanded ? issue.body || 'No description provided.' : truncatedBody}
          </div>
        </div>
        <div className="ml-4" onClick={(e) => e.stopPropagation()}>
          <Button
            className="github-button whitespace-nowrap flex items-center"
            onClick={() => onAskBot(issue)}
            disabled={isProcessing}
          >
            <Bot className="mr-2 h-4 w-4" />
            {isProcessing ? 'Processing...' : 'Ask Bot to Resolve'}
          </Button>
        </div>
      </div>
      
      {expanded && (
        <div className="mt-4 pt-3 border-t border-gray-100">
          <a 
            href={issue.html_url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-primary hover:underline text-sm"
            onClick={(e) => e.stopPropagation()}
          >
            View on GitHub →
          </a>
        </div>
      )}
    </div>
  );
};

export default IssueCard;
