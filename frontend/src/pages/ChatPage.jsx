import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { Send, Sparkles, RotateCcw } from 'lucide-react';
import { sendChatMessage, fetchChatHistory } from '../api';

const SAMPLE_QUERIES = [
  'Explain the architecture of this codebase',
  'Show the database models and relationships',
  'Where are the API routes registered?',
  'How are background tasks executed?',
  'What design patterns are used?',
];

export default function ChatPage() {
  const { activeRepoId, activeRepo } = useOutletContext();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  // Set welcome message when repo changes
  useEffect(() => {
    if (!activeRepoId) {
      setMessages([{
        role: 'assistant',
        content: 'Welcome to **RepoIntel**! Select a repository from the sidebar to start exploring its codebase with AI-powered semantic search.',
      }]);
      return;
    }

    const loadHistory = async () => {
      try {
        const data = await fetchChatHistory(activeRepoId);
        if (data.messages?.length > 0) {
          setMessages(data.messages);
        } else {
          setMessages([{
            role: 'assistant',
            content: `Connected to **${activeRepo?.name || 'repository'}**. Ask me anything about the codebase — architecture, design patterns, specific functions, or implementation details.`,
          }]);
        }
      } catch {
        setMessages([{
          role: 'assistant',
          content: `Ready to explore **${activeRepo?.name || 'repository'}**. What would you like to know?`,
        }]);
      }
    };
    loadHistory();
  }, [activeRepoId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (e) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { role: 'user', content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput('');
    setLoading(true);

    try {
      const data = await sendChatMessage(
        updated.filter(m => m.role !== 'system'),
        activeRepoId || 'default_session',
        activeRepoId || undefined,
      );
      if (data.messages?.length > 0) {
        setMessages([...updated, data.messages[data.messages.length - 1]]);
      }
    } catch (err) {
      setMessages([...updated, {
        role: 'assistant',
        content: `⚠️ Error: ${err.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSampleQuery = (query) => {
    if (loading) return;
    setInput(query);
  };

  return (
    <div className="chat-page">
      <div className="chat-page-header">
        <div className="chat-title-group">
          <h2>Intelligence Chat</h2>
          <span className="context-badge">
            {activeRepo ? activeRepo.name : 'No repository selected'}
          </span>
        </div>
        <button
          className="icon-btn"
          onClick={() => setMessages([])}
          title="Clear conversation"
        >
          <RotateCcw size={16} />
        </button>
      </div>

      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`msg ${msg.role}`}>
            {msg.role === 'assistant' && (
              <div className="msg-avatar">
                <Sparkles size={14} />
              </div>
            )}
            <div className={`msg-bubble ${msg.role}`}>
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          </div>
        ))}

        {loading && (
          <div className="msg assistant">
            <div className="msg-avatar">
              <Sparkles size={14} />
            </div>
            <div className="msg-bubble assistant loading-bubble">
              <div className="typing-dots">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Sample queries */}
      <div className="sample-queries">
        {SAMPLE_QUERIES.map((q, idx) => (
          <button
            key={idx}
            className="sample-chip"
            onClick={() => handleSampleQuery(q)}
            disabled={loading}
          >
            {q}
          </button>
        ))}
      </div>

      <form className="chat-input-bar" onSubmit={handleSend}>
        <input
          type="text"
          className="chat-input"
          placeholder={activeRepoId ? 'Ask about this repository...' : 'Select a repository first...'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading || !activeRepoId}
        />
        <button
          type="submit"
          className="send-btn"
          disabled={loading || !input.trim()}
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
