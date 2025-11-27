import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { filesAPI, pricingAIAPI } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Send, Bot, User, FileSpreadsheet, Loader2, Home, Menu, X } from 'lucide-react';

const PricingAIPage = () => {
  const { fileId } = useParams();
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [question, setQuestion] = useState('');
  const [provider, setProvider] = useState('gemini');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadFile();
  }, [fileId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const loadFile = async () => {
    try {
      const res = await filesAPI.getOne(fileId);
      setFile(res.data);
    } catch {
      toast.error('Failed to load file');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    const userMsg = { role: 'user', content: question };
    setMessages(prev => [...prev, userMsg]);
    setQuestion('');
    setLoading(true);

    try {
      const res = await pricingAIAPI.query({
        file_id: fileId,
        question,
        provider,
      });
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.response,
        table: res.data.table
      }]);
    } catch {
      toast.error('Failed to get response');
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const suggestions = [
    'What is the price of W3630 BUTT?',
    'Show all base cabinet prices',
    'What is the highest priced item?',
    'List all SKUs',
  ];

  return (
    <div className="h-screen w-screen flex flex-col bg-gray-50 overflow-hidden">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/')} className="text-gray-600">
            <Home className="w-4 h-4" />
          </Button>
          <div className="hidden sm:block h-5 w-px bg-gray-300" />
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-sm font-semibold text-gray-900">Pricing AI</h1>
              <p className="text-xs text-gray-500 truncate max-w-[200px]">{file?.name}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={provider} onValueChange={setProvider}>
            <SelectTrigger className="w-24 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="gemini">Gemini</SelectItem>
              <SelectItem value="openai">GPT-4</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="ghost" size="sm" className="lg:hidden" onClick={() => setSidebarOpen(true)}>
            <Menu className="w-4 h-4" />
          </Button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - Desktop */}
        <aside className="hidden lg:block w-64 bg-white border-r border-gray-200 p-4 overflow-y-auto">
          <SidebarContent file={file} suggestions={suggestions} onSelect={setQuestion} />
        </aside>

        {/* Sidebar - Mobile */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div className="absolute inset-0 bg-black/30" onClick={() => setSidebarOpen(false)} />
            <aside className="absolute left-0 top-0 bottom-0 w-72 bg-white p-4 overflow-y-auto">
              <div className="flex justify-between items-center mb-4">
                <span className="font-semibold">Info</span>
                <Button variant="ghost" size="sm" onClick={() => setSidebarOpen(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <SidebarContent file={file} suggestions={suggestions} onSelect={(q) => { setQuestion(q); setSidebarOpen(false); }} />
            </aside>
          </div>
        )}

        {/* Chat Area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center px-4">
                <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-4">
                  <Bot className="w-8 h-8 text-blue-600" />
                </div>
                <h2 className="text-lg font-semibold text-gray-900 mb-2">Pricing AI Assistant</h2>
                <p className="text-sm text-gray-500 mb-6 max-w-sm">
                  Ask questions about your pricing data. I'll find the exact prices from your file.
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {suggestions.slice(0, 3).map((s, i) => (
                    <button
                      key={i}
                      onClick={() => setQuestion(s)}
                      className="text-xs px-3 py-2 bg-white border border-gray-200 rounded-full hover:border-blue-400 hover:text-blue-600 transition"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'assistant' && (
                    <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
                      <Bot className="w-4 h-4 text-white" />
                    </div>
                  )}
                  <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user' 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-white border border-gray-200 text-gray-800'
                  }`}>
                    <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                    {msg.table && msg.table.length > 0 && (
                      <div className="mt-3 overflow-x-auto">
                        <table className="text-xs w-full">
                          <thead>
                            <tr className="border-b">
                              {Object.keys(msg.table[0]).map(k => (
                                <th key={k} className="px-2 py-1 text-left font-medium">{k}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {msg.table.map((row, ri) => (
                              <tr key={ri} className="border-b last:border-0">
                                {Object.values(row).map((v, ci) => (
                                  <td key={ci} className="px-2 py-1">{v}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center flex-shrink-0">
                      <User className="w-4 h-4 text-gray-600" />
                    </div>
                  )}
                </div>
              ))
            )}
            {loading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3">
                  <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 bg-white p-4">
            <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-2">
              <Textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
                placeholder="Ask about pricing..."
                disabled={loading}
                className="flex-1 min-h-[44px] max-h-[120px] resize-none text-sm"
                rows={1}
              />
              <Button type="submit" disabled={loading || !question.trim()} className="h-11 w-11 bg-blue-600 hover:bg-blue-700">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </Button>
            </form>
          </div>
        </main>
      </div>
    </div>
  );
};

const SidebarContent = ({ file, suggestions, onSelect }) => (
  <>
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <FileSpreadsheet className="w-4 h-4 text-blue-600" />
        <span className="text-sm font-medium">File Info</span>
      </div>
      <div className="space-y-2 text-xs">
        <div className="p-2 bg-gray-50 rounded-lg">
          <span className="text-gray-500">Name</span>
          <p className="font-medium truncate">{file?.name}</p>
        </div>
        <div className="p-2 bg-gray-50 rounded-lg">
          <span className="text-gray-500">Type</span>
          <p className="font-medium">{file?.file_type?.toUpperCase()}</p>
        </div>
      </div>
    </div>
    <div>
      <p className="text-xs font-medium text-gray-500 mb-2 uppercase">Suggestions</p>
      <div className="space-y-2">
        {suggestions.map((s, i) => (
          <button
            key={i}
            onClick={() => onSelect(s)}
            className="w-full text-left text-xs p-2 bg-gray-50 hover:bg-blue-50 rounded-lg transition"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  </>
);

export default PricingAIPage;

