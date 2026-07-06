import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

const API_BASE = 'http://localhost:8000/api/v1';

export default function App() {
  // Repositories State
  const [repos, setRepos] = useState([]);
  const [activeRepoId, setActiveRepoId] = useState('');
  const [newRepoName, setNewRepoName] = useState('');
  const [newRepoPath, setNewRepoPath] = useState('');
  const [newRepoBranch, setNewRepoBranch] = useState('main');

  const messagesEndRef = React.useRef(null);

  // Chat State
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', content: 'Welcome to RepoIntel! Select a repository to begin exploring, searching, and generating PR reviews or architectural documentation.' }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [loadingChat, setLoadingChat] = useState(false);
  const [selectedJobResult, setSelectedJobResult] = useState(null);

  // Background Jobs State
  const [jobs, setJobs] = useState([]);
  const [jobPayloadDiff, setJobPayloadDiff] = useState('');
  const [jobPayloadIssue, setJobPayloadIssue] = useState('');

  // Fetch Repositories list
  const fetchRepos = async () => {
    try {
      const res = await fetch(`${API_BASE}/repositories/`);
      const data = await res.json();
      setRepos(data);
      if (data.length > 0 && !activeRepoId) {
        setActiveRepoId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch repositories:', err);
    }
  };

  useEffect(() => {
    fetchRepos();
  }, []);

  // Poll repository list if there is any repository currently indexing
  useEffect(() => {
    const hasIndexing = repos.some(r => r.status === 'indexing');
    if (!hasIndexing) return;

    const interval = setInterval(() => {
      fetchRepos();
    }, 2000);

    return () => clearInterval(interval);
  }, [repos]);

  // Fetch messages when active repository changes to maintain separate chats
  useEffect(() => {
    if (!activeRepoId) return;

    const fetchChatHistory = async () => {
      try {
        const res = await fetch(`${API_BASE}/chatbot/messages?session_id=${activeRepoId}`);
        const data = await res.json();
        if (data.messages && data.messages.length > 0) {
          setChatMessages(data.messages);
        } else {
          const activeRepo = repos.find(r => r.id === activeRepoId);
          setChatMessages([
            {
              role: 'assistant',
              content: `Welcome to RepoIntel! You are now chatting with context from the "${activeRepo ? activeRepo.name : 'selected'}" repository. Ask any question about its codebase!`
            }
          ]);
        }
      } catch (err) {
        console.error('Failed to fetch chat history:', err);
      }
    };

    fetchChatHistory();
  }, [activeRepoId, repos]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, loadingChat]);

  // Poll active jobs status to retrieve reports when they complete
  useEffect(() => {
    const activeJobs = jobs.filter(j => j.status === 'pending' || j.status === 'running');
    if (activeJobs.length === 0) return;

    const interval = setInterval(async () => {
      try {
        const updatedJobs = await Promise.all(
          jobs.map(async (job) => {
            if (job.status === 'pending' || job.status === 'running') {
              const res = await fetch(`${API_BASE}/jobs/${job.id || job.job_id}`);
              if (res.ok) {
                return await res.json();
              }
            }
            return job;
          })
        );
        // Compare values to avoid infinite render loop
        const hasChanges = JSON.stringify(updatedJobs) !== JSON.stringify(jobs);
        if (hasChanges) {
          setJobs(updatedJobs);
        }
      } catch (err) {
        console.error('Failed to poll jobs:', err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [jobs]);

  // Register a new repository
  const handleRegisterRepo = async (e) => {
    e.preventDefault();
    if (!newRepoName || !newRepoPath) return;

    try {
      const res = await fetch(`${API_BASE}/repositories/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newRepoName,
          clone_url: newRepoPath,
          branch: newRepoBranch,
        }),
      });
      const newRepo = await res.json();
      setRepos([...repos, newRepo]);
      setActiveRepoId(newRepo.id);
      setNewRepoName('');
      setNewRepoPath('');
    } catch (err) {
      console.error('Failed to register repository:', err);
    }
  };

  // Trigger codebase indexing
  const handleIndexRepo = async (repoId) => {
    try {
      await fetch(`${API_BASE}/repositories/${repoId}/index`, {
        method: 'POST',
      });
      alert('Indexing started in the background!');
      fetchRepos();
    } catch (err) {
      console.error('Failed to trigger indexing:', err);
    }
  };

  // Delete repository
  const handleDeleteRepo = async (repoId, e) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this repository?')) return;
    try {
      await fetch(`${API_BASE}/repositories/${repoId}`, {
        method: 'DELETE',
      });
      fetchRepos();
      if (activeRepoId === repoId) {
        setActiveRepoId('');
      }
    } catch (err) {
      console.error('Failed to delete repository:', err);
    }
  };

  // Submit RAG query
  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || loadingChat) return;

    const userMsg = { role: 'user', content: chatInput };
    const updatedMessages = [...chatMessages, userMsg];
    setChatMessages(updatedMessages);
    setChatInput('');
    setLoadingChat(true);

    try {
      // Map API request payload
      // Exclude greeting assistant message to send clean conversation history
      const res = await fetch(`${API_BASE}/chatbot/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: updatedMessages.filter(m => m.role !== 'system'),
          session_id: activeRepoId || 'default_session',
          repository_id: activeRepoId || undefined,
        }),
      });
      
      const data = await res.json();
      if (data.messages && data.messages.length > 0) {
        setChatMessages([...updatedMessages, data.messages[data.messages.length - 1]]);
      }
    } catch (err) {
      console.error('Chat request failed:', err);
      setChatMessages([
        ...updatedMessages,
        { role: 'assistant', content: `Error generating response: ${err.message}` }
      ]);
    } finally {
      setLoadingChat(false);
    }
  };

  // Trigger Asynchronous Jobs
  const triggerPRReview = async () => {
    if (!activeRepoId || !jobPayloadDiff) return;
    try {
      const res = await fetch(`${API_BASE}/jobs/pr-review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository_id: activeRepoId,
          diff: jobPayloadDiff,
        }),
      });
      const job = await res.json();
      setJobs([job, ...jobs]);
      setJobPayloadDiff('');
    } catch (err) {
      console.error('Failed to queue PR review:', err);
    }
  };

  const triggerDocGeneration = async () => {
    if (!activeRepoId) return;
    try {
      const res = await fetch(`${API_BASE}/jobs/documentation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository_id: activeRepoId,
        }),
      });
      const job = await res.json();
      setJobs([job, ...jobs]);
    } catch (err) {
      console.error('Failed to queue docs build:', err);
    }
  };

  const triggerIssueResolution = async () => {
    if (!activeRepoId || !jobPayloadIssue) return;
    try {
      const res = await fetch(`${API_BASE}/jobs/issues`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository_id: activeRepoId,
          issue_text: jobPayloadIssue,
        }),
      });
      const job = await res.json();
      setJobs([job, ...jobs]);
      setJobPayloadIssue('');
    } catch (err) {
      console.error('Failed to queue issue resolver:', err);
    }
  };

  const handleCancelJob = async (jobId) => {
    try {
      await fetch(`${API_BASE}/jobs/${jobId}`, {
        method: 'DELETE',
      });
      setJobs(jobs.filter(job => (job.id || job.job_id) !== jobId));
    } catch (err) {
      console.error('Failed to cancel job:', err);
    }
  };

  return (
    <div className="app-container">
      {/* 1. Left Sidebar: Workspace Repos & Registration */}
      <div className="sidebar glass-panel">
        <div className="brand">
          <div className="brand-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span>RepoIntel</span>
        </div>

        <div className="repos-container">
          <h3 className="section-header">Workspace Repositories</h3>
          {repos.length === 0 ? (
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>No repositories indexed.</p>
          ) : (
            repos.map((repo) => (
              <div
                key={repo.id}
                className={`repo-card ${repo.id === activeRepoId ? 'active' : ''}`}
                onClick={() => !loadingChat && setActiveRepoId(repo.id)}
                style={{ position: 'relative', cursor: loadingChat ? 'not-allowed' : 'pointer' }}
              >
                <button
                  style={{
                    position: 'absolute',
                    top: '8px',
                    right: '8px',
                    background: 'transparent',
                    border: 'none',
                    color: 'rgba(255,255,255,0.4)',
                    cursor: loadingChat ? 'not-allowed' : 'pointer',
                    fontSize: '12px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => !loadingChat && (e.target.style.color = '#ff6b6b')}
                  onMouseLeave={(e) => !loadingChat && (e.target.style.color = 'rgba(255,255,255,0.4)')}
                  onClick={(e) => !loadingChat && handleDeleteRepo(repo.id, e)}
                  title="Delete repository"
                  disabled={loadingChat}
                >
                  ✕
                </button>
                <div className="repo-name" style={{ paddingRight: '20px' }}>{repo.name}</div>
                <div className="repo-desc">{repo.clone_url}</div>
                <div className="repo-meta">
                  <span>Branch: {repo.branch}</span>
                  <span style={{ textTransform: 'capitalize' }}>Status: {repo.status}</span>
                </div>
                {repo.status === 'indexing' && (
                  <div className="progress-bar-container">
                    <div className="progress-bar-fill" style={{ width: '45%' }}></div>
                  </div>
                )}
                 {repo.status === 'pending' && (
                  <button
                    className="primary-btn"
                    style={{ marginTop: '8px', padding: '4px 8px', fontSize: '10px' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!loadingChat) handleIndexRepo(repo.id);
                    }}
                    disabled={loadingChat}
                  >
                    Index Now
                  </button>
                )}
              </div>
            ))
          )}
        </div>

        {/* Repository Registration Form */}
        <form className="repo-register-form" onSubmit={(e) => !loadingChat && handleRegisterRepo(e)}>
          <h3 className="section-header">Register Repository</h3>
          <input
            className="input-field"
            type="text"
            placeholder="Display Name"
            value={newRepoName}
            onChange={(e) => setNewRepoName(e.target.value)}
            disabled={loadingChat}
          />
          <input
            className="input-field"
            type="text"
            placeholder="Local path or Clone URL"
            value={newRepoPath}
            onChange={(e) => setNewRepoPath(e.target.value)}
            disabled={loadingChat}
          />
          <input
            className="input-field"
            type="text"
            placeholder="Branch"
            value={newRepoBranch}
            onChange={(e) => setNewRepoBranch(e.target.value)}
            disabled={loadingChat}
          />
          <button className="primary-btn" type="submit" disabled={loadingChat}>Add Workspace</button>
        </form>
      </div>

      {/* 2. Middle Panel: RAG Intelligence Chat */}
      <div className="chat-console glass-panel">
        <div className="chat-header">
          <h3>Intelligence Chat</h3>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Active context: {repos.find(r => r.id === activeRepoId)?.name || 'None'}
          </span>
        </div>

        <div className="chat-messages">
          {chatMessages.map((msg, idx) => (
            <div key={idx} className={`message-bubble ${msg.role}`}>
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          ))}
          {loadingChat && (
            <div className="message-bubble assistant" style={{ fontStyle: 'italic' }}>
              Thinking and retrieving repository context...
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Clickable Sample Queries */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', padding: '10px 16px', borderTop: '1px solid rgba(255,255,255,0.05)', background: 'rgba(0,0,0,0.05)' }}>
          {[
            "Explain database models and relationships",
            "Show how JWT authentication is implemented",
            "Find where API routes are registered",
            "How are background agent tasks executed?",
            "Where is the main application entry point?"
          ].map((q, idx) => (
            <button
              key={idx}
              type="button"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px',
                color: 'rgba(255,255,255,0.7)',
                fontSize: '11px',
                padding: '4px 10px',
                cursor: loadingChat ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => !loadingChat && (e.target.style.background = 'rgba(255,255,255,0.12)')}
              onMouseLeave={(e) => !loadingChat && (e.target.style.background = 'rgba(255,255,255,0.04)')}
              onClick={() => {
                if (!loadingChat) {
                  setChatInput(q);
                }
              }}
              disabled={loadingChat}
            >
              {q}
            </button>
          ))}
        </div>

        <form className="chat-input-area" onSubmit={handleSendChat}>
          <input
            className="input-field"
            type="text"
            placeholder="Ask a question about this repository codebase..."
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            disabled={loadingChat}
          />
          <button className="primary-btn" type="submit" disabled={loadingChat}>Ask Agent</button>
        </form>
      </div>

      {/* 3. Right Panel: PR Reviews & Diagnostic Jobs */}
      <div className="jobs-panel glass-panel">
        <h3 className="section-header">PR Review & Diagnostics</h3>
        
        {/* Trigger PR Review */}
         <div style={{ marginBottom: '16px' }}>
          <textarea
            className="input-field"
            rows="3"
            style={{ resize: 'none', marginBottom: '8px' }}
            placeholder="Paste Git code diff payload..."
            value={jobPayloadDiff}
            onChange={(e) => setJobPayloadDiff(e.target.value)}
            disabled={loadingChat}
          />
          <button className="primary-btn" style={{ width: '100%' }} onClick={triggerPRReview} disabled={loadingChat}>
            Analyze Git Diff
          </button>
        </div>

        {/* Trigger Documentation Build */}
        <div style={{ marginBottom: '16px' }}>
          <button className="primary-btn" style={{ width: '100%', background: '#10b981' }} onClick={triggerDocGeneration} disabled={loadingChat}>
            Compile Codebase Documentation
          </button>
        </div>

        {/* Trigger Issue Resolver */}
        <div style={{ marginBottom: '24px' }}>
          <textarea
            className="input-field"
            rows="3"
            style={{ resize: 'none', marginBottom: '8px' }}
            placeholder="Paste bug trace or description..."
            value={jobPayloadIssue}
            onChange={(e) => setJobPayloadIssue(e.target.value)}
            disabled={loadingChat}
          />
          <button className="primary-btn" style={{ width: '100%', background: '#f59e0b' }} onClick={triggerIssueResolution} disabled={loadingChat}>
            Diagnose Trace
          </button>
        </div>

        <h3 className="section-header">Active Execution Jobs</h3>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {jobs.length === 0 ? (
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>No jobs triggered yet.</p>
          ) : (
            jobs.map((job) => (
              <div key={job.id || job.job_id} className="job-card" style={{ position: 'relative' }}>
                <button
                  style={{
                    position: 'absolute',
                    top: '8px',
                    right: '8px',
                    background: 'transparent',
                    border: 'none',
                    color: 'rgba(255,255,255,0.4)',
                    cursor: 'pointer',
                    fontSize: '12px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => (e.target.style.color = '#ff6b6b')}
                  onMouseLeave={(e) => (e.target.style.color = 'rgba(255,255,255,0.4)')}
                  onClick={() => handleCancelJob(job.id || job.job_id)}
                  title="Remove Job"
                >
                  ✕
                </button>
                <div className="job-type" style={{ paddingRight: '20px' }}>{job.agent_type.replace('_', ' ')}</div>
                <div className={`job-status ${job.status}`}>{job.status}</div>
                
                {(job.status === 'pending' || job.status === 'running') && (
                  <div className="progress-bar-container" style={{ marginTop: '8px', height: '6px' }}>
                    <div className="progress-bar-fill animated-glow" style={{ width: '100%' }}></div>
                  </div>
                )}

                {job.result && job.status === 'completed' && (
                  <button
                    className="primary-btn"
                    style={{ marginTop: '8px', padding: '6px 10px', fontSize: '11px', width: '100%', background: '#4b5563' }}
                    onClick={() => {
                      const payload = job.result;
                      let reportContent = '';
                      
                      if (job.agent_type === 'pr_review') {
                        const summary = payload.summary || 'No summary provided.';
                        const issues = payload.issues || [];
                        reportContent = `## PR Review Summary\n\n${summary}\n\n`;
                        if (issues.length > 0) {
                          reportContent += `## Identified Issues\n\n`;
                          issues.forEach((issue, idx) => {
                            const severityEmoji = issue.severity === 'critical' ? '🔴' : (issue.severity === 'warning' ? '🟡' : '🟢');
                            reportContent += `### ${idx + 1}. ${severityEmoji} [${issue.severity.toUpperCase()}] in \`${issue.file}\` (Line ${issue.line})\n`;
                            reportContent += `* **Description**: ${issue.description}\n`;
                            reportContent += `* **Suggestion**:\n\`\`\`python\n${issue.suggestion}\n\`\`\`\n\n`;
                          });
                        } else {
                          reportContent += `### 🎉 No issues identified. Excellent code quality!`;
                        }
                      } else if (job.agent_type === 'issue_resolver') {
                        reportContent = payload.diagnosis || JSON.stringify(payload, null, 2);
                      } else {
                        reportContent = payload.documentation || JSON.stringify(payload, null, 2);
                      }

                      setSelectedJobResult({
                        title: `${job.agent_type.replace('_', ' ')} Report`,
                        content: reportContent
                      });
                    }}
                  >
                    View Compiled Report
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Modal Overlay for Job Reports */}
      {selectedJobResult && (
        <div className="modal-backdrop" onClick={() => setSelectedJobResult(null)}>
          <div className="modal-content glass-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{selectedJobResult.title}</h3>
              <button className="close-btn" onClick={() => setSelectedJobResult(null)}>✕</button>
            </div>
            <div className="modal-body">
              <ReactMarkdown>{selectedJobResult.content}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
