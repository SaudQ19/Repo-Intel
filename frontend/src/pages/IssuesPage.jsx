import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { Bug, AlertCircle, Clock, ChevronRight, Loader2, Play } from 'lucide-react';
import { fetchIssues, analyzeIssue } from '../api';

export default function IssuesPage() {
  const { owner, repo } = useOutletContext();
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!owner || !repo) return;
    loadIssues();
  }, [owner, repo]);

  const loadIssues = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchIssues(owner, repo);
      setIssues(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (issue) => {
    setSelectedIssue(issue);
    setAnalysis(null);
    setAnalyzing(true);
    try {
      const data = await analyzeIssue(owner, repo, issue.number);
      setAnalysis(data);
    } catch (err) {
      setAnalysis({ error: err.message });
    } finally {
      setAnalyzing(false);
    }
  };

  if (!owner || !repo) {
    return (
      <div className="empty-state">
        <Bug size={48} strokeWidth={1} />
        <h3>No Repository Selected</h3>
        <p>Select a GitHub repository from the sidebar to view open issues.</p>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2>Open Issues & Bugs</h2>
          <span className="context-badge">{owner}/{repo}</span>
        </div>
        <button className="secondary-btn" onClick={loadIssues} disabled={loading}>
          {loading ? <Loader2 size={14} className="spin" /> : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="pr-layout">
        {/* Issues List */}
        <div className="pr-list">
          {loading && issues.length === 0 ? (
            <div className="loading-state">
              <Loader2 size={24} className="spin" />
              <p>Fetching issues...</p>
            </div>
          ) : issues.length === 0 ? (
            <div className="empty-state small">
              <AlertCircle size={32} strokeWidth={1} />
              <p>No open issues found</p>
            </div>
          ) : (
            issues.map((issue) => (
              <div
                key={issue.number}
                className={`pr-card ${selectedIssue?.number === issue.number ? 'active' : ''}`}
                onClick={() => handleAnalyze(issue)}
              >
                <div className="pr-card-header">
                  <span className="pr-number">#{issue.number}</span>
                  <ChevronRight size={14} className="pr-chevron" />
                </div>
                <h4 className="pr-title">{issue.title}</h4>
                <div className="pr-meta">
                  <span>{issue.user}</span>
                  <span>
                    <Clock size={12} /> {new Date(issue.created_at).toLocaleDateString()}
                  </span>
                </div>
                {issue.labels?.length > 0 && (
                  <div className="issue-labels">
                    {issue.labels.map((l) => (
                      <span key={l} className="label-badge">
                        {l}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Diagnostics Panel */}
        <div className="pr-review-panel glass-panel">
          {!selectedIssue ? (
            <div className="empty-state">
              <Bug size={40} strokeWidth={1} />
              <p>Select an issue to run diagnostic analysis</p>
            </div>
          ) : analyzing ? (
            <div className="loading-state">
              <Loader2 size={32} className="spin" />
              <p>Diagnosing Issue #{selectedIssue.number}...</p>
              <span className="loading-sub">Analyzing description and identifying root cause</span>
            </div>
          ) : analysis?.error ? (
            <div className="error-banner">
              <AlertCircle size={16} />
              <span>{analysis.error}</span>
            </div>
          ) : analysis ? (
            <div className="review-content">
              <div className="review-header">
                <h3>Diagnostic Report: #{analysis.number}</h3>
                <span className={`verdict-badge severity-${analysis.severity?.toLowerCase()}`}>
                  {analysis.severity?.toUpperCase()}
                </span>
              </div>

              <div className="review-sections">
                <div className="review-section">
                  <h4>Root Cause Analysis</h4>
                  <p>{analysis.root_cause}</p>
                </div>

                {analysis.affected_components?.length > 0 && (
                  <div className="review-section">
                    <h4>Affected Components</h4>
                    <ul>
                      {analysis.affected_components.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="review-section">
                  <h4>Suggested Fix</h4>
                  <ReactMarkdown>{analysis.suggested_fix}</ReactMarkdown>
                </div>

                {analysis.related_files?.length > 0 && (
                  <div className="review-section">
                    <h4>Related Files</h4>
                    <div className="file-list">
                      {analysis.related_files.map((file) => (
                        <span key={file} className="file-chip">
                          {file}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
