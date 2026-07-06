import React, { useState, useRef, useEffect } from 'react';
import { sendChatMessage } from '../api';
import { Terminal, Send, MessageSquare, X } from 'lucide-react';
import clsx from 'clsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import type { SavedAudit } from '../types';

interface ChatProps {
  activeData: SavedAudit;
  onUpdateHistory?: (newHistory: Message[]) => void;
}

export interface Message {
  role: 'user' | 'agent';
  content: string;
}

export const Chat: React.FC<ChatProps> = ({ activeData, onUpdateHistory }) => {
  const [messages, setMessages] = useState<Message[]>(() => {
    if (activeData.chat_history && activeData.chat_history.length > 0) {
      return activeData.chat_history;
    }
    return [
      { role: 'agent', content: 'Agent connected. Analysis context loaded. What would you like to know about this vendor?' }
    ];
  });
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    // Small delay ensures DOM paints the new message before scrolling
    setTimeout(scrollToBottom, 50);
  }, [messages, isOpen, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg = input;
    setInput('');
    const prevMessages = [...messages, { role: 'user', content: userMsg } as Message];
    setMessages(prevMessages);
    setIsLoading(true);

    try {
      const res = await sendChatMessage(activeData.session_id, userMsg);
      const updatedMessages: Message[] = [...prevMessages, { role: 'agent', content: res.response }];
      setMessages(updatedMessages);
      if (onUpdateHistory) {
        onUpdateHistory(updatedMessages);
      }
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'agent', content: `**[ERROR]:** ${err.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-accent-600 hover:bg-accent-700 text-white p-4 rounded-full shadow-soft-lg transition-transform hover:-translate-y-1 flex items-center gap-2 z-50"
      >
        <MessageSquare size={24} />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 w-96 max-h-[600px] h-[70vh] flex flex-col bg-white border border-stone-200 rounded-3xl shadow-soft-lg overflow-hidden animate-in slide-in-from-bottom-8 z-50">
      
      {/* Header */}
      <div className="bg-stone-50 p-5 border-b border-stone-200 flex justify-between items-center cursor-pointer" onClick={() => setIsOpen(false)}>
        <h3 className="font-heading font-bold text-accent-700 flex items-center gap-2 text-sm">
          <Terminal size={18} />
          Trust Agent
        </h3>
        <button className="text-stone-400 hover:text-stone-700 transition-colors bg-white hover:bg-stone-100 rounded-full p-1 shadow-sm border border-stone-200">
          <X size={14} />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-5 scroll-smooth bg-white custom-scrollbar">
        {messages.map((msg, idx) => (
          <div key={idx} className={clsx("flex flex-col max-w-[85%]", msg.role === 'user' ? "ml-auto" : "mr-auto")}>
            <span className={clsx("text-[10px] font-semibold mb-1 tracking-widest uppercase", msg.role === 'user' ? "text-stone-400 text-right" : "text-accent-500/70")}>
              {msg.role === 'user' ? 'You' : 'Agent'}
            </span>
            <div className={clsx(
              "p-4 rounded-2xl text-sm leading-relaxed font-sans shadow-sm border",
              msg.role === 'user' 
                ? "bg-stone-800 text-white border-stone-900 rounded-br-sm ml-auto text-right" 
                : "bg-stone-50 text-stone-700 border-stone-200 rounded-bl-sm"
            )}>
              {msg.role === 'agent' ? (
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({node, ...props}) => <p className="mb-2 last:mb-0" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc ml-4 mb-2 space-y-1" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal ml-4 mb-2 space-y-1" {...props} />,
                    strong: ({node, ...props}) => <strong className="font-semibold text-accent-700" {...props} />,
                    a: ({node, ...props}) => <a className="text-accent-600 hover:underline font-medium" {...props} />
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              ) : (
                <div className="whitespace-pre-wrap">{msg.content}</div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex flex-col max-w-[85%] mr-auto">
             <span className="text-[10px] font-semibold mb-1 tracking-widest uppercase text-accent-500/70">Agent is typing...</span>
             <div className="p-4 bg-stone-50 border border-stone-200 rounded-2xl rounded-bl-sm flex items-center shadow-sm w-fit">
                <div className="flex space-x-1.5 items-center justify-center">
                  <div className="w-1.5 h-1.5 bg-accent-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-1.5 h-1.5 bg-accent-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-1.5 h-1.5 bg-accent-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
             </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 bg-white border-t border-stone-200">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            disabled={isLoading}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={isLoading ? "Agent is thinking..." : "Ask a question..."}
            className="flex-1 bg-stone-50 border border-stone-200 rounded-xl px-4 py-3 text-sm text-stone-800 focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 font-sans disabled:opacity-50 disabled:cursor-not-allowed shadow-inner"
            autoFocus
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="bg-accent-600 hover:bg-accent-700 text-white p-3 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-sm"
          >
            <Send size={18} className={clsx(isLoading ? "opacity-50" : "ml-0.5")} />
          </button>
        </div>
      </div>
      
    </div>
  );
};
