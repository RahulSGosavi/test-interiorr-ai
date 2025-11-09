import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { filesAPI, pricingAIAPI } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ArrowLeft, Send, Brain, FileText, Loader2 } from 'lucide-react';
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
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" onClick={() => navigate(`/file/${fileId}`)} data-testid="back-button">
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl">
                  <Brain className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold" className="font-semibold" data-testid="page-title">
                    Pricing AI Assistant
                  </h1>
                  <p className="text-sm text-gray-500">{file?.name}</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">AI Model:</span>
              <Select value={provider} onValueChange={setProvider}>
                <SelectTrigger className="w-40" data-testid="provider-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gemini" data-testid="provider-gemini">Gemini 2.0</SelectItem>
                  <SelectItem value="openai" data-testid="provider-openai">GPT-4o</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 flex gap-6 min-h-0 overflow-hidden">
          {/* Sidebar */}
          <div className="w-80 flex-shrink-0 hidden lg:block overflow-y-auto">
            <Card className="sticky top-24">
              <CardHeader>
                <CardTitle className="text-lg">File Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm text-gray-500">File Name</p>
                  <p className="font-medium text-sm break-words" data-testid="sidebar-file-name">{file?.name}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Type</p>
                  <p className="font-medium text-sm" data-testid="sidebar-file-type">{file?.file_type?.toUpperCase()}</p>
                </div>
                {file?.meta?.sheet_count && (
                  <div>
                    <p className="text-sm text-gray-500">Sheets</p>
                    <p className="font-medium text-sm" data-testid="sidebar-sheet-count">{file.meta.sheet_count}</p>
                  </div>
                )}
                {file?.meta?.page_count && (
                  <div>
                    <p className="text-sm text-gray-500">Pages</p>
                    <p className="font-medium text-sm" data-testid="sidebar-page-count">{file.meta.page_count}</p>
                  </div>
                )}

                <div className="pt-4 border-t">
                  <p className="text-sm font-medium mb-2">Suggested Questions:</p>
                  <div className="space-y-2">
                    {suggestedQuestions.map((q, idx) => (
                      <button
                        key={idx}
                        onClick={() => setQuestion(q)}
                        className="w-full text-left text-xs p-2 rounded bg-gray-50 hover:bg-gray-100 transition"
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
              <CardContent className="flex-1 flex flex-col p-4 sm:p-6 min-h-0 overflow-hidden">
                {/* Messages */}
                <div className="flex-1 overflow-y-auto mb-4 space-y-4 min-h-0" data-testid="conversation-container">
                  {conversation.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center" data-testid="empty-conversation">
                      <Brain className="w-16 h-16 text-gray-300 mb-4" />
                      <h3 className="text-xl font-semibold mb-2">Ask me anything about this file</h3>
                      <p className="text-gray-500 max-w-md">
                        I can help you analyze costs, find specific data, calculate totals, and answer questions
                        about cabinet codes, prices, and materials.
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
                          className={`max-w-2xl rounded-2xl px-4 py-3 ${
                            msg.role === 'user'
                              ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                              : 'bg-gray-100 text-gray-900'
                          }`}
                        >
                          <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                          {msg.table && msg.table.length > 0 && (
                            <div className="mt-3 overflow-x-auto" data-testid={`message-table-${idx}`}>
                              <table className="min-w-full text-xs">
                                <thead>
                                  <tr className="border-b">
                                    {Object.keys(msg.table[0]).map((key) => (
                                      <th key={key} className="px-2 py-1 text-left">
                                        {key}
                                      </th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {msg.table.map((row, rowIdx) => (
                                    <tr key={rowIdx} className="border-b">
                                      {Object.values(row).map((val, colIdx) => (
                                        <td key={colIdx} className="px-2 py-1">
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
                      <div className="bg-gray-100 rounded-2xl px-4 py-3">
                        <Loader2 className="w-5 h-5 animate-spin text-gray-600" />
                      </div>
                    </div>
                  )}
                </div>

                {/* Input */}
                <form onSubmit={handleAskQuestion} className="flex gap-2">
                  <Input
                    placeholder="Ask about costs, codes, totals, or any data in the file..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    disabled={loading}
                    className="flex-1 h-12"
                    data-testid="question-input"
                  />
                  <Button
                    type="submit"
                    disabled={loading || !question.trim()}
                    className="h-12 px-6 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
                    data-testid="send-question-button"
                  >
                    <Send className="w-4 h-4" />
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