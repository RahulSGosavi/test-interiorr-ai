import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { filesAPI, messagesAPI } from '@/lib/api';
import useStore from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ArrowLeft, Send, MessageSquare, Home, Menu } from 'lucide-react';
import { motion } from 'framer-motion';

const DiscussionPage = () => {
  const { fileId } = useParams();
  const navigate = useNavigate();
  const { user } = useStore();
  const [file, setFile] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadFile();
    loadMessages();
    // Poll for new messages every 3 seconds
    const interval = setInterval(loadMessages, 3000);
    return () => clearInterval(interval);
  }, [fileId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadFile = async () => {
    try {
      const response = await filesAPI.getOne(fileId);
      setFile(response.data);
    } catch (error) {
      toast.error('Failed to load file');
    }
  };

  const loadMessages = async () => {
    try {
      const response = await messagesAPI.getAll(fileId);
      setMessages(response.data);
    } catch (error) {
      console.error('Failed to load messages');
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim()) return;

    setSending(true);
    try {
      await messagesAPI.create(fileId, { text: newMessage });
      setNewMessage('');
      loadMessages();
    } catch (error) {
      toast.error('Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const getInitials = (name) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <div className="min-h-screen h-screen w-full overflow-hidden flex flex-col" style={{ background: 'linear-gradient(to bottom right, #f8fafc, #e0f2fe)' }}>
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 flex-shrink-0">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-6 py-2 sm:py-3">
          <div className="flex items-center gap-2 sm:gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/")} data-testid="home-button" className="h-7 px-2" title="Go to Home">
              <Home className="w-3.5 h-3.5 mr-1" />
              <span className="hidden sm:inline text-xs">Home</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate(`/file/${fileId}`)} data-testid="menu-button" className="h-7 px-2" title="Go to File Menu">
              <Menu className="w-3.5 h-3.5 mr-1" />
              <span className="hidden sm:inline text-xs">Menu</span>
            </Button>
            <div className="h-4 w-px bg-gray-300 hidden sm:block" />
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-gradient-to-br from-green-500 to-teal-500 rounded-lg">
                <MessageSquare className="w-3.5 h-3.5 text-white" />
              </div>
              <div>
                <h1 className="text-sm sm:text-base font-semibold" data-testid="page-title">
                  Discussion
                </h1>
                <p className="text-[10px] sm:text-xs text-gray-500 truncate max-w-[200px] sm:max-w-none">{file?.name}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-3 sm:px-4 lg:px-6 py-3 sm:py-4 flex flex-col min-h-0 overflow-hidden">
        <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <CardHeader className="flex-shrink-0 p-3 sm:p-4">
            <CardTitle className="text-base sm:text-lg">Team Discussion</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col min-h-0 overflow-hidden p-3 sm:p-4">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto mb-3 space-y-2.5 min-h-0" data-testid="messages-container">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center" data-testid="no-messages">
                  <MessageSquare className="w-10 h-10 sm:w-12 sm:h-12 text-gray-300 mb-2 sm:mb-3" />
                  <h3 className="text-sm sm:text-base font-semibold mb-1">Start the conversation</h3>
                  <p className="text-xs sm:text-sm text-gray-500">Share your thoughts, questions, or feedback with the team</p>
                </div>
              ) : (
                messages.map((msg, idx) => {
                  const isOwnMessage = msg.author_id === user?.id;
                  return (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3 }}
                      className={`flex gap-3 ${
                        isOwnMessage ? 'flex-row-reverse' : 'flex-row'
                      }`}
                      data-testid={`message-${idx}`}
                    >
                      <Avatar className="w-7 h-7 sm:w-8 sm:h-8 flex-shrink-0">
                        <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-500 text-white text-[10px] sm:text-xs">
                          {getInitials(msg.author_name)}
                        </AvatarFallback>
                      </Avatar>
                      <div
                        className={`flex flex-col max-w-[70%] sm:max-w-md ${
                          isOwnMessage ? 'items-end' : 'items-start'
                        }`}
                      >
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span className="text-[11px] sm:text-xs font-medium" data-testid={`message-author-${idx}`}>{msg.author_name}</span>
                          <span className="text-[9px] sm:text-[10px] text-gray-500" data-testid={`message-time-${idx}`}>
                            {new Date(msg.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                        <div
                          className={`rounded-xl px-2.5 py-1.5 sm:px-3 sm:py-2 ${
                            isOwnMessage
                              ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                              : 'bg-gray-100 text-gray-900'
                          }`}
                        >
                          <p className="text-[11px] sm:text-xs whitespace-pre-wrap" data-testid={`message-text-${idx}`}>{msg.text}</p>
                        </div>
                      </div>
                    </motion.div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSendMessage} className="flex gap-1.5 sm:gap-2">
              <Input
                placeholder="Type your message..."
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                disabled={sending}
                className="flex-1 h-8 sm:h-9 text-xs sm:text-sm"
                data-testid="message-input"
              />
              <Button
                type="submit"
                disabled={sending || !newMessage.trim()}
                className="h-8 sm:h-9 px-3 sm:px-4 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700"
                data-testid="send-message-button"
              >
                <Send className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default DiscussionPage;