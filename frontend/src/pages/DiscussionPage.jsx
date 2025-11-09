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
    <div className="h-screen w-screen overflow-hidden flex flex-col fixed inset-0" style={{ background: 'linear-gradient(to bottom right, #f8fafc, #e0f2fe)' }}>
      {/* Header */}
      <header className="bg-white border-b border-gray-200 flex-shrink-0">
        <div className="w-full px-2 sm:px-4 py-1 sm:py-1.5">
          <div className="flex items-center gap-1 sm:gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigate("/")} data-testid="home-button" className="h-7 w-7 p-0 sm:h-8 sm:w-auto sm:px-2" title="Go to Home">
              <Home className="w-3.5 h-3.5" />
              <span className="hidden sm:inline ml-1 text-xs">Home</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate(`/file/${fileId}`)} data-testid="menu-button" className="h-7 w-7 p-0 sm:h-8 sm:w-auto sm:px-2" title="Go to File Menu">
              <Menu className="w-3.5 h-3.5" />
              <span className="hidden sm:inline ml-1 text-xs">Menu</span>
            </Button>
            <div className="h-4 w-px bg-gray-300" />
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <div className="p-1 bg-gradient-to-br from-green-500 to-teal-500 rounded flex-shrink-0">
                <MessageSquare className="w-3 h-3 text-white" />
              </div>
              <div className="min-w-0">
                <h1 className="text-xs font-semibold truncate" data-testid="page-title">
                  Discussion
                </h1>
                <p className="text-[8px] text-gray-500 truncate">{file?.name}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 w-full px-2 py-2 flex flex-col min-h-0 overflow-hidden">
        <Card className="flex-1 flex flex-col min-h-0 overflow-hidden max-w-4xl w-full mx-auto">
          <CardHeader className="flex-shrink-0 p-2">
            <CardTitle className="text-xs sm:text-sm">Team Discussion</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col min-h-0 overflow-hidden p-2">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto mb-2 space-y-2 min-h-0" data-testid="messages-container">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center" data-testid="no-messages">
                  <MessageSquare className="w-8 h-8 text-gray-300 mb-1" />
                  <h3 className="text-[11px] font-semibold mb-0.5">Start the conversation</h3>
                  <p className="text-[9px] text-gray-500">Share your thoughts</p>
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
                      <Avatar className="w-5 h-5 flex-shrink-0">
                        <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-500 text-white text-[8px]">
                          {getInitials(msg.author_name)}
                        </AvatarFallback>
                      </Avatar>
                      <div
                        className={`flex flex-col max-w-[80%] ${
                          isOwnMessage ? 'items-end' : 'items-start'
                        }`}
                      >
                        <div className="flex items-center gap-1 mb-0.5">
                          <span className="text-[9px] font-medium" data-testid={`message-author-${idx}`}>{msg.author_name}</span>
                          <span className="text-[7px] text-gray-500" data-testid={`message-time-${idx}`}>
                            {new Date(msg.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                          </span>
                        </div>
                        <div
                          className={`rounded px-1.5 py-1 ${
                            isOwnMessage
                              ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                              : 'bg-gray-100 text-gray-900'
                          }`}
                        >
                          <p className="text-[10px] whitespace-pre-wrap break-words" data-testid={`message-text-${idx}`}>{msg.text}</p>
                        </div>
                      </div>
                    </motion.div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSendMessage} className="flex gap-1.5 flex-shrink-0">
              <Input
                placeholder="Type message..."
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                disabled={sending}
                className="flex-1 h-8 text-[11px] px-2"
                data-testid="message-input"
              />
              <Button
                type="submit"
                disabled={sending || !newMessage.trim()}
                className="h-8 w-8 p-0 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700"
                data-testid="send-message-button"
              >
                <Send className="w-3.5 h-3.5" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default DiscussionPage;