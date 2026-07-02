import React, { useState, useRef, useEffect } from 'react';
import { sendChatMessage } from '../api';
import { Terminal, Send, Loader2, MessageSquare } from 'lucide-react';
import clsx from 'clsx';

interface ChatProps {
  sessionId: string;
}

interface Message {
  role: 'user' | 'agent';
  content: string;
}

export const Chat: React.FC<ChatProps> = ({ sessionId }) => {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'agent', content: 'Agent connected. Analysis context loaded. What would you like to know about this vendor?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isOpen]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);

    try {
      const res = await sendChatMessage(sessionId, userMsg);
      setMessages(prev => [...prev, { role: 'agent', content: res.response }]);
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'agent', content: `[ERROR]: ${err.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-cyan-600 hover:bg-cyan-500 text-white p-4 rounded-full shadow-2xl transition-transform hover:scale-110 flex items-center gap-2"
      >
        <MessageSquare size={24} />
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 w-96 max-h-[600px] h-[70vh] flex flex-col bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom-8">
      
      {/* Header */}
      <div className="bg-slate-800 p-4 border-b border-slate-700 flex justify-between items-center cursor-pointer" onClick={() => setIsOpen(false)}>
        <h3 className="font-mono text-cyan-400 font-bold flex items-center gap-2 text-sm">
          <Terminal size={16} />
          ASK TRUST AGENT
        </h3>
        <button className="text-slate-500 hover:text-slate-300 transition-colors">
          &times;
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={clsx("flex flex-col max-w-[85%]", msg.role === 'user' ? "ml-auto" : "mr-auto")}>
            <span className={clsx("text-[10px] font-mono mb-1 tracking-widest uppercase", msg.role === 'user' ? "text-slate-500 text-right" : "text-cyan-500/50")}>
              {msg.role}
            </span>
            <div className={clsx(
              "p-3 rounded-xl text-sm leading-relaxed whitespace-pre-wrap font-mono",
              msg.role === 'user' 
                ? "bg-slate-800 text-slate-200 border border-slate-700/50 rounded-br-none" 
                : "bg-cyan-900/20 text-cyan-50 border border-cyan-800/30 rounded-bl-none"
            )}>
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex flex-col max-w-[85%] mr-auto">
             <span className="text-[10px] font-mono mb-1 tracking-widest uppercase text-cyan-500/50">agent</span>
             <div className="p-3 bg-cyan-900/20 text-cyan-400 border border-cyan-800/30 rounded-xl rounded-bl-none flex items-center gap-2">
                <Loader2 className="animate-spin" size={16} /> processing...
             </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 bg-slate-800 border-t border-slate-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Query analysis data..."
            className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
            autoFocus
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="bg-cyan-600 hover:bg-cyan-500 text-white p-2 rounded-lg transition-colors disabled:opacity-50"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
      
    </div>
  );
};
