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
    <div className="flex flex-col bg-gradient-to-br from-slate-50 via-blue-50 to-teal-50" style={{ height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {/* Compact Header */}
      <header className="backdrop-blur-xl bg-white/80 border-b border-white/20 shadow-lg flex-shrink-0" style={{ minHeight: '44px', maxHeight: '50px' }}>
        <div className="w-full px-2 sm:px-3 py-1.5">
          <div className="flex items-center gap-1 sm:gap-1.5">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => navigate("/")} 
              className="h-7 px-1.5 hover:bg-white/60"
            >
              <Home className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
              <span className="hidden md:inline ml-1 text-[10px] sm:text-xs">Home</span>
            </Button>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => navigate(`/file/${fileId}`)} 
              className="h-7 px-1.5 hover:bg-white/60"
            >
              <Menu className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
              <span className="hidden md:inline ml-1 text-[10px] sm:text-xs">Menu</span>
            </Button>
            <div className="h-4 w-px bg-gray-300 hidden sm:block" />
            <div className="flex items-center gap-1 flex-1 min-w-0">
              <div className="p-1 sm:p-1.5 bg-gradient-to-br from-green-500 to-teal-500 rounded-lg shadow-md">
                <MessageSquare className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-white" />
              </div>
              <div className="min-w-0 flex-1">
                <h1 className="text-[10px] sm:text-xs font-bold bg-gradient-to-r from-green-600 to-teal-600 bg-clip-text text-transparent truncate">
                  Discussion
                </h1>
                <p className="text-[8px] sm:text-[10px] text-gray-500 truncate">{file?.name}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Chat Container - Uses remaining height */}
      <main className="flex-1 w-full px-2 sm:px-3 py-1.5 sm:py-2 overflow-hidden" style={{ minHeight: 0 }}>
        <div className="h-full max-w-4xl mx-auto flex flex-col">
          {/* 3D Glass Chat Card */}
          <div className="flex flex-col bg-white/70 backdrop-blur-xl rounded-xl sm:rounded-2xl border border-white/20 shadow-xl overflow-hidden" style={{ height: '100%' }}>
            {/* Chat Title */}
            <div className="flex-shrink-0 px-2 sm:px-3 py-1.5 sm:py-2 border-b border-gray-100/50 bg-gradient-to-r from-green-50/50 to-teal-50/50">
              <h2 className="text-[10px] sm:text-xs font-semibold text-gray-800">Team Discussion</h2>
            </div>
            
            {/* Messages Area - Scrollable */}
            <div className="flex-1 overflow-y-auto px-2 sm:px-2.5 py-1.5 sm:py-2 space-y-1.5 sm:space-y-2" style={{ minHeight: 0 }} data-testid="messages-container">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="p-3 bg-gradient-to-br from-green-100 to-teal-100 rounded-xl mb-3 shadow-md">
                    <MessageSquare className="w-10 h-10 sm:w-12 sm:h-12 text-green-600" />
                  </div>
                  <h3 className="text-sm sm:text-base font-bold text-gray-800 mb-1">Start the conversation</h3>
                  <p className="text-xs text-gray-500">Share your thoughts</p>
                </div>
              ) : (
                <>
                  {messages.map((msg, idx) => {
                    const isOwnMessage = msg.author_id === user?.id;
                    return (
                      <motion.div
                        key={msg.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3 }}
                        className={`flex gap-2 ${isOwnMessage ? 'flex-row-reverse' : 'flex-row'}`}
                        data-testid={`message-${idx}`}
                      >
                        <Avatar className="w-7 h-7 sm:w-9 sm:h-9 flex-shrink-0 ring-1 ring-white shadow">
                          <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-500 text-white text-[10px] sm:text-xs font-semibold">
                            {getInitials(msg.author_name)}
                          </AvatarFallback>
                        </Avatar>
                        <div className={`flex flex-col max-w-[65%] sm:max-w-[70%] ${isOwnMessage ? 'items-end' : 'items-start'}`}>
                          <div className="flex items-center gap-1 mb-0.5">
                            <span className="text-[9px] sm:text-xs font-semibold text-gray-700" data-testid={`message-author-${idx}`}>
                              {msg.author_name}
                            </span>
                            <span className="text-[8px] sm:text-[9px] text-gray-400" data-testid={`message-time-${idx}`}>
                              {new Date(msg.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                            </span>
                          </div>
                          <div
                            className={`rounded-xl px-2.5 py-1.5 sm:px-3 sm:py-2 shadow-md ${
                              isOwnMessage
                                ? 'bg-gradient-to-br from-blue-500 via-blue-600 to-purple-600 text-white'
                                : 'bg-white text-gray-800 border border-gray-100'
                            }`}
                          >
                            <p className="text-xs sm:text-sm leading-snug whitespace-pre-wrap break-words" data-testid={`message-text-${idx}`}>
                              {msg.text}
                            </p>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Input - Always Visible */}
            <div className="flex-shrink-0 border-t border-gray-100/50 p-1.5 sm:p-2 bg-white/50">
              <form onSubmit={handleSendMessage} className="flex gap-1.5">
                <Input
                  placeholder="Type message..."
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  disabled={sending}
                  className="flex-1 h-8 sm:h-9 text-[11px] sm:text-xs px-2 sm:px-3 rounded-lg bg-white border-gray-200 focus:border-green-500 focus:ring-1 focus:ring-green-500"
                  data-testid="message-input"
                />
                <Button
                  type="submit"
                  disabled={sending || !newMessage.trim()}
                  className="h-8 w-8 sm:h-9 sm:w-9 p-0 rounded-lg bg-gradient-to-br from-green-500 to-teal-500 hover:from-green-600 hover:to-teal-600 shadow-md disabled:opacity-50"
                  data-testid="send-message-button"
                >
                  <Send className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                </Button>
              </form>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default DiscussionPage;