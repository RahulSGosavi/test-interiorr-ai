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
    <div className="min-h-screen h-screen w-full overflow-hidden flex flex-col" style={{ background: 'linear-gradient(to bottom right, #f8fafc, #e0f2fe)' }}>
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 flex-shrink-0">
        <div className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-6 py-1.5 sm:py-2">
          <div className="flex items-center justify-between gap-1.5 sm:gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 sm:gap-3 min-w-0">
              <Button variant="ghost" size="sm" onClick={() => navigate("/")} data-testid="home-button" className="h-6 sm:h-7 px-1.5 sm:px-2" title="Go to Home">
                <Home className="w-3 h-3 sm:w-3.5 sm:h-3.5 sm:mr-1" />
                <span className="hidden sm:inline text-xs">Home</span>
              </Button>
              <Button variant="ghost" size="sm" onClick={() => navigate(`/file/${fileId}`)} data-testid="menu-button" className="h-6 sm:h-7 px-1.5 sm:px-2" title="Go to File Menu">
                <Menu className="w-3 h-3 sm:w-3.5 sm:h-3.5 sm:mr-1" />
                <span className="hidden sm:inline text-xs">Menu</span>
              </Button>
              <div className="h-3 w-px bg-gray-300 hidden sm:block" />
              <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                <div className="p-1 sm:p-1.5 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex-shrink-0">
                  <Brain className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-white" />
                </div>
                <div className="min-w-0">
                  <h1 className="text-xs sm:text-sm font-semibold truncate" data-testid="page-title">
                    Pricing AI
                  </h1>
                  <p className="text-[9px] sm:text-[10px] text-gray-500 truncate max-w-[100px] sm:max-w-[150px]">{file?.name}</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1 sm:gap-1.5">
              <span className="text-[9px] sm:text-[10px] text-gray-500 hidden sm:inline">AI:</span>
              <Select value={provider} onValueChange={setProvider}>
                <SelectTrigger className="w-20 sm:w-28 h-6 sm:h-7 text-[9px] sm:text-[10px]" data-testid="provider-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gemini" data-testid="provider-gemini" className="text-[10px] sm:text-xs">Gemini</SelectItem>
                  <SelectItem value="openai" data-testid="provider-openai" className="text-[10px] sm:text-xs">GPT-4o</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-2 sm:px-4 lg:px-6 py-2 sm:py-3 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 flex gap-2 sm:gap-3 min-h-0 overflow-hidden">
          {/* Sidebar */}
          <div className="w-48 flex-shrink-0 hidden lg:block overflow-y-auto">
            <Card className="sticky top-16">
              <CardHeader className="p-2">
                <CardTitle className="text-xs">File Info</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-2 pt-0">
                <div>
                  <p className="text-[10px] text-gray-500">File Name</p>
                  <p className="font-medium text-[11px] break-words" data-testid="sidebar-file-name">{file?.name}</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-500">Type</p>
                  <p className="font-medium text-[11px]" data-testid="sidebar-file-type">{file?.file_type?.toUpperCase()}</p>
                </div>
                {file?.meta?.sheet_count && (
                  <div>
                    <p className="text-[10px] text-gray-500">Sheets</p>
                    <p className="font-medium text-[11px]" data-testid="sidebar-sheet-count">{file.meta.sheet_count}</p>
                  </div>
                )}
                {file?.meta?.page_count && (
                  <div>
                    <p className="text-[10px] text-gray-500">Pages</p>
                    <p className="font-medium text-[11px]" data-testid="sidebar-page-count">{file.meta.page_count}</p>
                  </div>
                )}

                <div className="pt-2.5 border-t">
                  <p className="text-[10px] font-medium mb-1.5">Suggested Questions:</p>
                  <div className="space-y-1.5">
                    {suggestedQuestions.map((q, idx) => (
                      <button
                        key={idx}
                        onClick={() => setQuestion(q)}
                        className="w-full text-left text-[9px] p-1.5 rounded bg-gray-50 hover:bg-gray-100 transition"
                        data-testid={`suggested-question-${idx}`}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Chat Area */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
              <CardContent className="flex-1 flex flex-col p-2 sm:p-3 min-h-0 overflow-hidden">
                {/* Messages */}
                <div className="flex-1 overflow-y-auto mb-2 space-y-2 min-h-0" data-testid="conversation-container">
                  {conversation.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center px-2" data-testid="empty-conversation">
                      <Brain className="w-8 h-8 sm:w-10 sm:h-10 text-gray-300 mb-1.5 sm:mb-2" />
                      <h3 className="text-xs sm:text-sm font-semibold mb-0.5 sm:mb-1">Ask me anything</h3>
                      <p className="text-[10px] sm:text-[11px] text-gray-500 max-w-md px-2">
                        Analyze costs, find data, calculate totals
                      </p>
                    </div>
                  ) : (
                    conversation.map((msg, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3 }}
                        className={`flex ${
                          msg.role === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                        data-testid={`message-${idx}`}
                      >
                        <div
                          className={`max-w-full sm:max-w-2xl rounded-lg px-2 py-1.5 sm:px-2.5 sm:py-2 ${
                            msg.role === 'user'
                              ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                              : 'bg-gray-100 text-gray-900'
                          }`}
                        >
                          <p className="text-[10px] sm:text-[11px] whitespace-pre-wrap break-words">{msg.content}</p>
                          {msg.table && msg.table.length > 0 && (
                            <div className="mt-1.5 overflow-x-auto" data-testid={`message-table-${idx}`}>
                              <table className="min-w-full text-[8px] sm:text-[9px]">
                                <thead>
                                  <tr className="border-b">
                                    {Object.keys(msg.table[0]).map((key) => (
                                      <th key={key} className="px-1 py-0.5 text-left">
                                        {key}
                                      </th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {msg.table.map((row, rowIdx) => (
                                    <tr key={rowIdx} className="border-b">
                                      {Object.values(row).map((val, colIdx) => (
                                        <td key={colIdx} className="px-1 py-0.5">
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
                            <p className="text-[8px] sm:text-[9px] mt-1 opacity-70">Powered by {msg.provider}</p>
                          )}
                        </div>
                      </motion.div>
                    ))
                  )}
                  {loading && (
                    <div className="flex justify-start" data-testid="loading-indicator">
                      <div className="bg-gray-100 rounded-lg px-2 py-1.5 sm:px-2.5 sm:py-2">
                        <Loader2 className="w-3 h-3 sm:w-3.5 sm:h-3.5 animate-spin text-gray-600" />
                      </div>
                    </div>
                  )}
                </div>

                {/* Input */}
                <form onSubmit={handleAskQuestion} className="flex gap-1.5 sm:gap-2 flex-shrink-0">
                  <Input
                    placeholder="Ask about costs..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    disabled={loading}
                    className="flex-1 h-7 sm:h-8 text-[11px] sm:text-xs px-2"
                    data-testid="question-input"
                  />
                  <Button
                    type="submit"
                    disabled={loading || !question.trim()}
                    className="h-7 sm:h-8 px-2 sm:px-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
                    data-testid="send-question-button"
                  >
                    <Send className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
};

export default PricingAIPage;