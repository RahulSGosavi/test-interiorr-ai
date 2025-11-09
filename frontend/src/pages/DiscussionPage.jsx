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
    <div className="h-screen w-screen overflow-hidden flex flex-col fixed inset-0 bg-gradient-to-br from-slate-50 via-blue-50 to-teal-50">
      {/* Modern Glass Header */}
      <header className="backdrop-blur-xl bg-white/80 border-b border-white/20 shadow-lg flex-shrink-0">
        <div className="w-full px-2 sm:px-4 lg:px-6 py-1.5 sm:py-2.5 lg:py-3">
          <div className="flex items-center gap-1 sm:gap-2 lg:gap-3">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => navigate("/")} 
              className="h-7 sm:h-8 lg:h-9 px-1.5 sm:px-2.5 lg:px-3 hover:bg-white/60 transition-all duration-200 hover:scale-105"
            >
              <Home className="w-3 h-3 sm:w-3.5 sm:h-3.5 lg:w-4 lg:h-4 sm:mr-1" />
              <span className="hidden sm:inline text-[10px] sm:text-xs lg:text-sm font-medium">Home</span>
            </Button>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => navigate(`/file/${fileId}`)} 
              className="h-7 sm:h-8 lg:h-9 px-1.5 sm:px-2.5 lg:px-3 hover:bg-white/60 transition-all duration-200 hover:scale-105"
            >
              <Menu className="w-3 h-3 sm:w-3.5 sm:h-3.5 lg:w-4 lg:h-4 sm:mr-1" />
              <span className="hidden sm:inline text-[10px] sm:text-xs lg:text-sm font-medium">Menu</span>
            </Button>
            <div className="h-4 sm:h-5 lg:h-6 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block" />
            <div className="flex items-center gap-1.5 sm:gap-2 lg:gap-3 min-w-0 flex-1">
              <div className="p-1 sm:p-1.5 lg:p-2 bg-gradient-to-br from-green-500 to-teal-500 rounded-lg sm:rounded-xl shadow-md sm:shadow-lg shadow-green-500/20 sm:shadow-green-500/30">
                <MessageSquare className="w-3 h-3 sm:w-4 sm:h-4 lg:w-5 lg:h-5 text-white" />
              </div>
              <div className="min-w-0">
                <h1 className="text-[11px] sm:text-sm lg:text-lg font-bold bg-gradient-to-r from-green-600 to-teal-600 bg-clip-text text-transparent">
                  Discussion
                </h1>
                <p className="text-[9px] sm:text-[10px] lg:text-xs text-gray-500 truncate max-w-[80px] sm:max-w-[150px] lg:max-w-none">{file?.name}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content with 3D Chat */}
      <main className="flex-1 w-full px-2 sm:px-4 lg:px-6 py-2 sm:py-4 lg:py-6 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden max-w-5xl w-full mx-auto perspective-1000">
          {/* 3D Chat Container */}
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-white/70 backdrop-blur-xl rounded-xl sm:rounded-2xl lg:rounded-3xl border border-white/20 shadow-xl sm:shadow-2xl transform-gpu transition-all duration-300 hover:shadow-green-500/20">
            {/* Chat Header */}
            <div className="flex-shrink-0 px-2.5 sm:px-4 lg:px-6 py-2 sm:py-3 lg:py-4 border-b border-gray-100/50 bg-gradient-to-r from-green-50/50 to-teal-50/50">
              <h2 className="text-xs sm:text-sm lg:text-base font-semibold text-gray-800">Team Discussion</h2>
            </div>
            
            {/* Messages Container */}
            <div className="flex-1 flex flex-col min-h-0 overflow-hidden p-2 sm:p-3 lg:p-4">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto mb-2 sm:mb-3 space-y-2 sm:space-y-2.5 lg:space-y-3 min-h-0 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent" data-testid="messages-container">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center px-3 sm:px-4" data-testid="no-messages">
                  <div className="p-3 sm:p-4 bg-gradient-to-br from-green-100 to-teal-100 rounded-xl sm:rounded-2xl mb-3 sm:mb-4 shadow-md sm:shadow-lg">
                    <MessageSquare className="w-8 h-8 sm:w-12 sm:h-12 lg:w-16 lg:h-16 text-green-600" />
                  </div>
                  <h3 className="text-sm sm:text-base lg:text-lg font-bold text-gray-800 mb-1.5 sm:mb-2">Start the conversation</h3>
                  <p className="text-xs sm:text-sm text-gray-500">Share your thoughts, questions, or feedback with the team</p>
                </div>
              ) : (
                messages.map((msg, idx) => {
                  const isOwnMessage = msg.author_id === user?.id;
                  return (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 20, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ duration: 0.4, ease: "easeOut" }}
                      className={`flex gap-2 sm:gap-3 lg:gap-4 ${
                        isOwnMessage ? 'flex-row-reverse' : 'flex-row'
                      }`}
                      data-testid={`message-${idx}`}
                    >
                      <Avatar className="w-7 h-7 sm:w-8 sm:h-8 lg:w-10 lg:h-10 flex-shrink-0 ring-1 sm:ring-2 ring-white shadow-md sm:shadow-lg">
                        <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-500 text-white text-[10px] sm:text-xs lg:text-sm font-semibold">
                          {getInitials(msg.author_name)}
                        </AvatarFallback>
                      </Avatar>
                      <div
                        className={`flex flex-col max-w-[70%] sm:max-w-[75%] lg:max-w-md ${
                          isOwnMessage ? 'items-end' : 'items-start'
                        }`}
                      >
                        <div className="flex items-center gap-1 sm:gap-1.5 lg:gap-2 mb-0.5 sm:mb-1">
                          <span className="text-[10px] sm:text-xs lg:text-sm font-semibold text-gray-700" data-testid={`message-author-${idx}`}>
                            {msg.author_name}
                          </span>
                          <span className="text-[8px] sm:text-[9px] lg:text-[10px] text-gray-400" data-testid={`message-time-${idx}`}>
                            {new Date(msg.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                          </span>
                        </div>
                        <div
                          className={`rounded-xl sm:rounded-2xl px-3 py-2 sm:px-4 sm:py-2.5 lg:px-5 lg:py-3 shadow-md sm:shadow-lg transform transition-all duration-200 hover:scale-[1.02] ${
                            isOwnMessage
                              ? 'bg-gradient-to-br from-blue-500 via-blue-600 to-purple-600 text-white shadow-blue-500/30'
                              : 'bg-white text-gray-800 shadow-gray-200/50 border border-gray-100'
                          }`}
                        >
                          <p className="text-xs sm:text-sm lg:text-base leading-relaxed whitespace-pre-wrap break-words" data-testid={`message-text-${idx}`}>
                            {msg.text}
                          </p>
                        </div>
                      </div>
                    </motion.div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Modern Input */}
            <form onSubmit={handleSendMessage} className="flex gap-1.5 sm:gap-2 lg:gap-3 flex-shrink-0">
              <Input
                placeholder="Type your message..."
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                disabled={sending}
                className="flex-1 h-9 sm:h-10 lg:h-12 text-xs sm:text-sm lg:text-base px-3 sm:px-4 lg:px-5 rounded-lg sm:rounded-xl bg-white/80 backdrop-blur-sm border-gray-200 focus:border-green-500 focus:ring-2 focus:ring-green-500/20 shadow-sm transition-all"
                data-testid="message-input"
              />
              <Button
                type="submit"
                disabled={sending || !newMessage.trim()}
                className="h-9 w-9 sm:h-10 sm:w-10 lg:h-12 lg:w-12 p-0 rounded-lg sm:rounded-xl bg-gradient-to-br from-green-500 to-teal-500 hover:from-green-600 hover:to-teal-600 shadow-md sm:shadow-lg shadow-green-500/30 transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100"
                data-testid="send-message-button"
              >
                <Send className="w-3.5 h-3.5 sm:w-4 sm:h-4 lg:w-5 lg:h-5" />
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