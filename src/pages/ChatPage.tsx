import { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Send, Bot, ArrowLeft, ExternalLink, Github, CornerDownLeft } from 'lucide-react';
import { Issue } from '@/components/IssueCard';
import { createAgentWebSocket } from '@/services/apiService';
import { toast } from '@/components/ui/sonner';

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;
}

interface LocationState {
  issue: Issue;
  clientId: string;
}

const ChatPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  // Get issue and clientId from location state
  const state = location.state as LocationState;
  const issue = state?.issue;
  const clientId = state?.clientId;
  
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: issue 
        ? `I'm analyzing issue #${issue.number}: ${issue.title}. How can I help you resolve this?` 
        : "I don't have any issue details. Please go back and select an issue.",
      isUser: false,
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [socket, setSocket] = useState<WebSocket | null>(null);

  const handleSendMessage = () => {
    if (inputValue.trim() === '') return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');

    // Show typing indicator
    setIsTyping(true);

    // Send message to backend via WebSocket if available
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        // Send the user message to the backend
        socket.send(JSON.stringify({
          message: inputValue,
          issueId: issue?.number
        }));
      } catch (error) {
        console.error('Error sending message via WebSocket:', error);
        toast.error('Failed to send message');
        setIsTyping(false);
      }
    } else {
      console.error('WebSocket not connected');
      toast.error('Connection to agent lost. Please try again.');
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleGoBack = () => {
    navigate('/');
  };

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Set up WebSocket connection when component mounts
  useEffect(() => {
    // Only create WebSocket if we have a clientId
    if (clientId) {
      const onMessage = (message: { content: string, timestamp: Date, isAgent: boolean }) => {
        // Turn off typing indicator when we receive a message
        setIsTyping(false);
        
        const botMessage: Message = {
          id: Date.now().toString(),
          content: message.content,
          isUser: !message.isAgent, // Convert isAgent (from backend) to isUser (for frontend)
          timestamp: message.timestamp,
        };
        
        setMessages(prev => [...prev, botMessage]);
      };
      
      // Create the WebSocket connection
      const ws = createAgentWebSocket(clientId, onMessage);
      setSocket(ws);
      
      // Clean up the WebSocket connection when the component unmounts
      return () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    }
  }, [clientId]);

  // Focus input on component mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  if (!issue || !clientId) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <h2 className="text-xl font-semibold mb-4">
            {!issue ? "No issue selected" : "Missing agent connection ID"}
          </h2>
          <p className="text-gray-500 mb-4">
            {!issue 
              ? "Please go back and select an issue to analyze." 
              : "There was a problem connecting to the agent. Please try again."}
          </p>
          <Button onClick={handleGoBack}>Go back to issues</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={handleGoBack}
                className="mr-2"
                aria-label="Go back"
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div className="flex items-center">
                <Bot className="h-5 w-5 text-primary mr-2" />
                <h1 className="text-lg font-semibold text-gray-900 mr-2">Issue Assistant</h1>
                <span className="text-sm text-gray-500">#{issue.number}</span>
              </div>
            </div>
            
            <a 
              href={issue.html_url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-gray-500 hover:text-gray-700 flex items-center"
            >
              <Github className="h-4 w-4 mr-1" />
              <span className="text-sm">View on GitHub</span>
              <ExternalLink className="h-3 w-3 ml-1" />
            </a>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
        {/* Left Sidebar - Issue Details */}
        <aside className="w-full md:w-80 lg:w-96 bg-white border-r border-gray-200 p-4 overflow-y-auto hidden md:block">
          <div className="space-y-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">{issue.title}</h2>
              <div className="flex items-center text-sm text-gray-500 mt-1">
                <span>Opened by {issue.user.login}</span>
                <span className="mx-2">•</span>
                <span>{new Date(issue.created_at).toLocaleDateString()}</span>
              </div>
            </div>
            
            <div className="border-t border-gray-100 pt-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Description</h3>
              <div className="text-sm text-gray-600 whitespace-pre-line">
                {issue.body || 'No description provided.'}
              </div>
            </div>
          </div>
        </aside>

        {/* Chat Area */}
        <main className="flex-1 flex flex-col bg-gray-50 relative">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6">
            <div className="max-w-3xl mx-auto space-y-6">
              {messages.map((message) => (
                <div 
                  key={message.id}
                  className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
                >
                  <div 
                    className={`max-w-[85%] p-4 rounded-2xl shadow-sm ${
                      message.isUser 
                        ? 'bg-primary text-white rounded-br-none' 
                        : 'bg-white text-gray-800 rounded-bl-none'
                    }`}
                  >
                    <div className="whitespace-pre-line">{message.content}</div>
                    <div className="text-xs mt-1 opacity-70 text-right">
                      {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              ))}
              
              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-white text-gray-800 p-4 rounded-2xl rounded-bl-none shadow-sm max-w-[85%]">
                    <div className="flex space-x-2">
                      <div className="w-2 h-2 rounded-full bg-gray-300 animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 rounded-full bg-gray-300 animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 rounded-full bg-gray-300 animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          </div>
          
          {/* Input Area */}
          <div className="border-t border-gray-200 bg-white p-4">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-end space-x-2">
                <div className="flex-1 relative">
                  <textarea
                    ref={inputRef}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type your message..."
                    className="w-full border border-gray-300 rounded-lg px-4 py-3 pr-12 resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                    rows={1}
                    style={{ maxHeight: '150px', minHeight: '44px' }}
                  />
                  <div className="absolute right-3 bottom-3 text-gray-400 text-xs">
                    <CornerDownLeft className="h-4 w-4" />
                  </div>
                </div>
                <Button 
                  onClick={handleSendMessage}
                  className="h-10 px-4 flex items-center justify-center"
                  disabled={!inputValue.trim()}
                >
                  <Send className="h-4 w-4 mr-1" />
                  <span>Send</span>
                </Button>
              </div>
              <div className="text-xs text-gray-500 mt-2 text-center">
                Press Enter to send, Shift+Enter for a new line
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default ChatPage;
