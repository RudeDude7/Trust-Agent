import React, { useState, useRef, useEffect } from 'react';
import { sendChatMessage } from '../api';
import { Terminal, Send, MessageSquare } from 'lucide-react';
import clsx from 'clsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);

    try {
      const res = await sendChatMessage(sessionId, userMsg);
      setMessages(prev => [...prev, { role: 'agent', content: res.response }]);
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
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth">
        {messages.map((msg, idx) => (
          <div key={idx} className={clsx("flex flex-col max-w-[85%]", msg.role === 'user' ? "ml-auto" : "mr-auto")}>
            <span className={clsx("text-[10px] font-mono mb-1 tracking-widest uppercase", msg.role === 'user' ? "text-slate-500 text-right" : "text-cyan-500/50")}>
              {msg.role}
            </span>
            <div className={clsx(
              "p-3 rounded-xl text-sm leading-relaxed font-sans",
              msg.role === 'user' 
                ? "bg-cyan-700 text-white border border-cyan-600 rounded-br-none ml-auto text-right" 
                : "bg-slate-800 text-slate-200 border border-slate-700/50 rounded-bl-none shadow-sm"
            )}>
              {msg.role === 'agent' ? (
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({node, ...props}) => <p className="mb-2 last:mb-0" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc ml-4 mb-2 space-y-1" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal ml-4 mb-2 space-y-1" {...props} />,
                    strong: ({node, ...props}) => <strong className="font-semibold text-cyan-300" {...props} />,
                    a: ({node, ...props}) => <a className="text-cyan-400 hover:underline" {...props} />
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
             <span className="text-[10px] font-mono mb-1 tracking-widest uppercase text-cyan-500/50">agent is typing...</span>
             <div className="p-4 bg-slate-800 border border-slate-700/50 rounded-xl rounded-bl-none flex items-center shadow-sm w-fit">
                <div className="flex space-x-1.5 items-center justify-center">
                  <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
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
            disabled={isLoading}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={isLoading ? "Agent is typing..." : "Query analysis data..."}
            className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 font-mono disabled:opacity-50 disabled:cursor-not-allowed"
            autoFocus
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="bg-cyan-600 hover:bg-cyan-500 text-white p-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            <Send size={18} className={clsx(isLoading ? "opacity-50" : "")} />
          </button>
        </div>
      </div>
      
    </div>
  );
};
