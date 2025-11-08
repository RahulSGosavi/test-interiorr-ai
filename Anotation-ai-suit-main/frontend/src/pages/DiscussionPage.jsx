import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { filesAPI, messagesAPI } from '@/lib/api';
import useStore from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ArrowLeft, Send, MessageSquare } from 'lucide-react';
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
    <div className="min-h-screen flex flex-col" style={{ background: 'linear-gradient(to bottom right, #f8fafc, #e0f2fe)' }}>
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={() => navigate(`/file/${fileId}`)} data-testid="back-button">
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-green-500 to-teal-500 rounded-xl">
                <MessageSquare className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold" className="font-semibold" data-testid="page-title">
                  Discussion
                </h1>
                <p className="text-sm text-gray-500">{file?.name}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col">
        <Card className="flex-1 flex flex-col">
          <CardHeader>
            <CardTitle>Team Discussion</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto mb-4 space-y-4 min-h-[400px]" data-testid="messages-container">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center" data-testid="no-messages">
                  <MessageSquare className="w-16 h-16 text-gray-300 mb-4" />
                  <h3 className="text-xl font-semibold mb-2">Start the conversation</h3>
                  <p className="text-gray-500">Share your thoughts, questions, or feedback with the team</p>
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
                      <Avatar className="w-10 h-10 flex-shrink-0">
                        <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-500 text-white">
                          {getInitials(msg.author_name)}
                        </AvatarFallback>
                      </Avatar>
                      <div
                        className={`flex flex-col max-w-lg ${
                          isOwnMessage ? 'items-end' : 'items-start'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium" data-testid={`message-author-${idx}`}>{msg.author_name}</span>
                          <span className="text-xs text-gray-500" data-testid={`message-time-${idx}`}>
                            {new Date(msg.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                        <div
                          className={`rounded-2xl px-4 py-2 ${
                            isOwnMessage
                              ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                              : 'bg-gray-100 text-gray-900'
                          }`}
                        >
                          <p className="text-sm whitespace-pre-wrap" data-testid={`message-text-${idx}`}>{msg.text}</p>
                        </div>
                      </div>
                    </motion.div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSendMessage} className="flex gap-2">
              <Input
                placeholder="Type your message..."
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                disabled={sending}
                className="flex-1 h-12"
                data-testid="message-input"
              />
              <Button
                type="submit"
                disabled={sending || !newMessage.trim()}
                className="h-12 px-6 bg-gradient-to-r from-green-600 to-teal-600 hover:from-green-700 hover:to-teal-700"
                data-testid="send-message-button"
              >
                <Send className="w-4 h-4" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default DiscussionPage;