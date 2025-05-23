
import { useState } from 'react';
import { toast } from '@/components/ui/sonner';
import { Button } from '@/components/ui/button';
import { Search } from 'lucide-react';

interface SearchBarProps {
  onSearch: (repoUrl: string) => void;
  isLoading: boolean;
}

const SearchBar = ({ onSearch, isLoading }: SearchBarProps) => {
  const [repoUrl, setRepoUrl] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!repoUrl.trim()) {
      toast.error('Please enter a GitHub repository URL');
      return;
    }

    // Simple URL validation to ensure it's a GitHub repo
    if (!repoUrl.includes('github.com/')) {
      toast.error('Please enter a valid GitHub repository URL');
      return;
    }

    onSearch(repoUrl);
  };

  return (
    <div className="w-full max-w-3xl mx-auto mb-8">
      <form onSubmit={handleSubmit} className="flex">
        <div className="relative flex-grow">
          <input
            type="text"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="Enter GitHub repository URL (e.g., https://github.com/facebook/react)"
            className="github-search"
            disabled={isLoading}
          />
        </div>
        <Button 
          type="submit" 
          className="ml-2 github-button flex items-center"
          disabled={isLoading}
        >
          <Search className="mr-2 h-4 w-4" />
          {isLoading ? 'Searching...' : 'Search'}
        </Button>
      </form>
    </div>
  );
};

export default SearchBar;
