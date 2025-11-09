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
        <div className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-6 py-1.5 sm:py-2">
          <div className="flex items-center gap-1.5 sm:gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/")} data-testid="home-button" className="h-6 sm:h-7 px-1.5 sm:px-2" title="Go to Home">
              <Home className="w-3 h-3 sm:w-3.5 sm:h-3.5 sm:mr-1" />
              <span className="hidden sm:inline text-xs">Home</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate(`/file/${fileId}`)} data-testid="menu-button" className="h-6 sm:h-7 px-1.5 sm:px-2" title="Go to File Menu">
              <Menu className="w-3 h-3 sm:w-3.5 sm:h-3.5 sm:mr-1" />
              <span className="hidden sm:inline text-xs">Menu</span>
            </Button>
            <div className="h-3 w-px bg-gray-300 hidden sm:block" />
            <div className="flex items-center gap-1.5 sm:gap-2">
              <div className="p-1 sm:p-1.5 bg-gradient-to-br from-green-500 to-teal-500 rounded-lg">
                <MessageSquare className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-white" />
              </div>
              <div className="min-w-0">
                <h1 className="text-xs sm:text-sm font-semibold truncate" data-testid="page-title">
                  Discussion
                </h1>
                <p className="text-[9px] sm:text-[10px] text-gray-500 truncate max-w-[120px] sm:max-w-[200px]">{file?.name}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-2 sm:px-4 lg:px-6 py-2 sm:py-3 flex flex-col min-h-0 overflow-hidden">
        <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <CardHeader className="flex-shrink-0 p-2 sm:p-3">
            <CardTitle className="text-sm sm:text-base">Team Discussion</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col min-h-0 overflow-hidden p-2 sm:p-3">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto mb-2 space-y-2 min-h-0" data-testid="messages-container">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center px-2" data-testid="no-messages">
                  <MessageSquare className="w-8 h-8 sm:w-10 sm:h-10 text-gray-300 mb-1.5 sm:mb-2" />
                  <h3 className="text-xs sm:text-sm font-semibold mb-0.5 sm:mb-1">Start the conversation</h3>
                  <p className="text-[10px] sm:text-xs text-gray-500">Share your thoughts with the team</p>
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
                      className={`flex gap-2 sm:gap-3 ${
                        isOwnMessage ? 'flex-row-reverse' : 'flex-row'
                      }`}
                      data-testid={`message-${idx}`}
                    >
                      <Avatar className="w-6 h-6 sm:w-7 sm:h-7 flex-shrink-0">
                        <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-500 text-white text-[9px] sm:text-[10px]">
                          {getInitials(msg.author_name)}
                        </AvatarFallback>
                      </Avatar>
                      <div
                        className={`flex flex-col max-w-[75%] sm:max-w-[70%] ${
                          isOwnMessage ? 'items-end' : 'items-start'
                        }`}
                      >
                        <div className="flex items-center gap-1 mb-0.5">
                          <span className="text-[10px] sm:text-[11px] font-medium" data-testid={`message-author-${idx}`}>{msg.author_name}</span>
                          <span className="text-[8px] sm:text-[9px] text-gray-500" data-testid={`message-time-${idx}`}>
                            {new Date(msg.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                        <div
                          className={`rounded-lg px-2 py-1 sm:px-2.5 sm:py-1.5 ${
                            isOwnMessage
                              ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                              : 'bg-gray-100 text-gray-900'
                          }`}
                        >
                          <p className="text-[10px] sm:text-[11px] whitespace-pre-wrap break-words" data-testid={`message-text-${idx}`}>{msg.text}</p>
                        </div>
                      </div>
                    </motion.div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSendMessage} className="flex gap-1.5 sm:gap-2 flex-shrink-0">
              <Input
                placeholder="Type your message..."
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                disabled={sending}
                className="flex-1 h-7 sm:h-8 text-[11px] sm:text-xs px-2"
                data-testid="message-input"
              />
              <Button
                type="submit"
                disabled={sending || !newMessage.trim()}
                className="h-7 sm:h-8 px-2 sm:px-3 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700"
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