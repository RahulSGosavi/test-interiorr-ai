import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { filesAPI, pricingAIAPI } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ArrowLeft, Send, Brain, FileText, Loader2, Home, Menu } from 'lucide-react';
import { motion } from 'framer-motion';

const PricingAIPage = () => {
  const { fileId } = useParams();
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [question, setQuestion] = useState('');
  const [provider, setProvider] = useState('gemini');
  const [conversation, setConversation] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadFile();
  }, [fileId]);

  const loadFile = async () => {
    try {
      const response = await filesAPI.getOne(fileId);
      setFile(response.data);
    } catch (error) {
      toast.error('Failed to load file');
    }
  };

  const handleAskQuestion = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    const userMessage = { role: 'user', content: question };
    setConversation((prev) => [...prev, userMessage]);
    setQuestion('');
    setLoading(true);

    try {
      const response = await pricingAIAPI.query({
        file_id: fileId,
        question,
        provider,
      });

      const aiMessage = {
        role: 'assistant',
        content: response.data.response,
        table: response.data.table,
        provider: response.data.provider,
      };
      setConversation((prev) => [...prev, aiMessage]);
    } catch (error) {
      toast.error('Failed to get AI response');
      setConversation((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const suggestedQuestions = [
    'What is the total cost of all items?',
    'List all unique cabinet codes',
    'What is the highest priced item?',
    'Show me items with cost over $10,000',
    'Summarize the pricing by category',
  ];

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col fixed inset-0 bg-gradient-to-br from-slate-50 via-purple-50 to-pink-50">
      {/* Modern Glass Header */}
      <header className="backdrop-blur-xl bg-white/80 border-b border-white/20 shadow-lg flex-shrink-0">
        <div className="w-full px-3 sm:px-6 py-2 sm:py-3">
          <div className="flex items-center justify-between gap-2 sm:gap-3">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => navigate("/")} 
                className="h-8 sm:h-9 px-3 hover:bg-white/60 transition-all duration-200 hover:scale-105"
              >
                <Home className="w-4 h-4 sm:mr-1.5" />
                <span className="hidden sm:inline text-sm font-medium">Home</span>
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => navigate(`/file/${fileId}`)} 
                className="h-8 sm:h-9 px-3 hover:bg-white/60 transition-all duration-200 hover:scale-105"
              >
                <Menu className="w-4 h-4 sm:mr-1.5" />
                <span className="hidden sm:inline text-sm font-medium">Menu</span>
              </Button>
              <div className="h-6 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block" />
              <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                <div className="p-2 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl shadow-lg shadow-purple-500/30">
                  <Brain className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                </div>
                <div className="min-w-0">
                  <h1 className="text-sm sm:text-lg font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                    Pricing AI
                  </h1>
                  <p className="text-xs text-gray-500 truncate">{file?.name}</p>
                </div>
              </div>
            </div>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger className="w-24 sm:w-32 h-8 sm:h-9 text-xs sm:text-sm shadow-sm hover:shadow-md transition-all" data-testid="provider-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gemini" className="text-xs sm:text-sm">Gemini 2.0</SelectItem>
                <SelectItem value="openai" className="text-xs sm:text-sm">GPT-4o</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </header>

      {/* Main Content with 3D Chat */}
      <main className="flex-1 w-full px-3 sm:px-6 py-3 sm:py-6 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 flex gap-3 sm:gap-4 min-h-0 overflow-hidden max-w-7xl w-full mx-auto">
          {/* Modern Sidebar - Hidden on Mobile */}
          <div className="w-64 flex-shrink-0 hidden lg:block overflow-y-auto">
            <div className="bg-white/70 backdrop-blur-xl rounded-2xl border border-white/20 shadow-xl p-4 sticky top-0">
              <h3 className="text-sm font-bold text-gray-800 mb-3">File Information</h3>
              <div className="space-y-2.5 text-sm">
                <div>
                  <p className="text-xs text-gray-500 mb-1">File Name</p>
                  <p className="font-semibold text-xs break-words text-gray-800">{file?.name}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Type</p>
                  <p className="font-semibold text-xs text-gray-800">{file?.file_type?.toUpperCase()}</p>
                </div>
                {file?.meta?.sheet_count && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Sheets</p>
                    <p className="font-semibold text-xs text-gray-800">{file.meta.sheet_count}</p>
                  </div>
                )}
                {file?.meta?.page_count && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Pages</p>
                    <p className="font-semibold text-xs text-gray-800">{file.meta.page_count}</p>
                  </div>
                )}
              </div>

              <div className="mt-4 pt-4 border-t border-gray-200">
                <p className="text-xs font-bold text-gray-700 mb-2">💡 Suggested Questions</p>
                <div className="space-y-2">
                  {suggestedQuestions.map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => setQuestion(q)}
                      className="w-full text-left text-[11px] p-2 rounded-lg bg-gradient-to-br from-purple-50 to-pink-50 hover:from-purple-100 hover:to-pink-100 border border-purple-100 transition-all duration-200 hover:scale-[1.02] hover:shadow-md text-gray-700"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* 3D Chat Area */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            {/* 3D Glass Chat Container */}
            <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-white/70 backdrop-blur-xl rounded-2xl sm:rounded-3xl border border-white/20 shadow-2xl transform-gpu transition-all duration-300 hover:shadow-purple-500/20">
              {/* Chat Header */}
              <div className="flex-shrink-0 px-4 sm:px-6 py-3 sm:py-4 border-b border-gray-100/50 bg-gradient-to-r from-purple-50/50 to-pink-50/50">
                <h2 className="text-sm sm:text-base font-semibold text-gray-800">AI Assistant</h2>
              </div>
              
              {/* Messages Container */}
              <div className="flex-1 flex flex-col min-h-0 overflow-hidden p-3 sm:p-4">
                {/* Messages */}
                <div className="flex-1 overflow-y-auto mb-3 space-y-3 min-h-0 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent" data-testid="conversation-container">
                  {conversation.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center px-4" data-testid="empty-conversation">
                      <div className="p-4 bg-gradient-to-br from-purple-100 to-pink-100 rounded-2xl mb-4 shadow-lg">
                        <Brain className="w-12 h-12 sm:w-16 sm:h-16 text-purple-600" />
                      </div>
                      <h3 className="text-base sm:text-lg font-bold text-gray-800 mb-2">Ask me anything</h3>
                      <p className="text-sm text-gray-500">I can help analyze costs, find data, and calculate totals</p>
                    </div>
                  ) : (
                    conversation.map((msg, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, y: 20, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={{ duration: 0.4, ease: "easeOut" }}
                        className={`flex ${
                          msg.role === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                        data-testid={`message-${idx}`}
                      >
                        <div
                          className={`max-w-[80%] sm:max-w-2xl rounded-2xl px-4 py-2.5 sm:px-5 sm:py-3 shadow-lg transform transition-all duration-200 hover:scale-[1.02] ${
                            msg.role === 'user'
                              ? 'bg-gradient-to-br from-purple-500 via-purple-600 to-pink-600 text-white shadow-purple-500/30'
                              : 'bg-white text-gray-800 shadow-gray-200/50 border border-gray-100'
                          }`}
                        >
                          <p className="text-sm sm:text-base leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
                          {msg.table && msg.table.length > 0 && (
                            <div className="mt-3 overflow-x-auto bg-black/5 rounded-lg p-2" data-testid={`message-table-${idx}`}>
                              <table className="min-w-full text-xs">
                                <thead>
                                  <tr className="border-b border-gray-300">
                                    {Object.keys(msg.table[0]).map((key) => (
                                      <th key={key} className="px-2 py-1.5 text-left font-semibold">
                                        {key}
                                      </th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {msg.table.map((row, rowIdx) => (
                                    <tr key={rowIdx} className="border-b border-gray-200/50">
                                      {Object.values(row).map((val, colIdx) => (
                                        <td key={colIdx} className="px-2 py-1.5">
                                          {val}
                                        </td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                          {msg.provider && (
                            <p className="text-xs mt-2 opacity-70">Powered by {msg.provider}</p>
                          )}
                        </div>
                      </motion.div>
                    ))
                  )}
                  {loading && (
                    <div className="flex justify-start" data-testid="loading-indicator">
                      <div className="bg-white rounded-2xl px-5 py-3 shadow-lg border border-gray-100">
                        <Loader2 className="w-5 h-5 sm:w-6 sm:h-6 animate-spin text-purple-600" />
                      </div>
                    </div>
                  )}
                </div>

                {/* Modern Input */}
                <form onSubmit={handleAskQuestion} className="flex gap-2 sm:gap-3 flex-shrink-0">
                  <Input
                    placeholder="Ask about costs, codes, totals..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    disabled={loading}
                    className="flex-1 h-11 sm:h-12 text-sm sm:text-base px-4 sm:px-5 rounded-xl bg-white/80 backdrop-blur-sm border-gray-200 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 shadow-sm transition-all"
                    data-testid="question-input"
                  />
                  <Button
                    type="submit"
                    disabled={loading || !question.trim()}
                    className="h-11 sm:h-12 w-11 sm:w-12 p-0 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 shadow-lg shadow-purple-500/30 transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100"
                    data-testid="send-question-button"
                  >
                    <Send className="w-4 h-4 sm:w-5 sm:h-5" />
                  </Button>
                </form>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default PricingAIPage;