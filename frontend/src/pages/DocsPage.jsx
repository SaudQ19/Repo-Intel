import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { FileText, Loader2, Sparkles, AlertCircle, RefreshCw } from 'lucide-react';
import { generateDocs } from '../api';

export default function DocsPage() {
  const { owner, repo, activeRepoId, activeRepo } = useOutletContext();
  const [loading, setLoading] = useState(false);
  const [generatedDoc, setGeneratedDoc] = useState('');
  const [error, setError] = useState('');

  // Try to load cached doc from database if available (or generate it)
  // Let's reset the document state when repo changes
  useEffect(() => {
    setGeneratedDoc('');
    setError('');
  }, [activeRepoId]);

  const handleGenerateDocs = async () => {
    if (!activeRepoId) return;
    setLoading(true);
    setError('');
    try {
      const data = await generateDocs(owner, repo, activeRepoId);
      if (data.documentation) {
        setGeneratedDoc(data.documentation);
      } else {
        throw new Error("No documentation content returned");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!activeRepoId) {
    return (
      <div className="empty-state">
        <FileText size={48} strokeWidth={1} />
        <h3>No Repository Selected</h3>
        <p>Select a codebase from the sidebar to generate technical documentation.</p>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2>Technical Specifications</h2>
          <span className="context-badge">{activeRepo?.name || `${owner}/${repo}`}</span>
        </div>
        {generatedDoc && (
          <button className="secondary-btn" onClick={handleGenerateDocs} disabled={loading}>
            {loading ? <Loader2 size={14} className="spin" /> : (
              <>
                <RefreshCw size={14} /> Re-Generate
              </>
            )}
          </button>
        )}
      </div>

      {error && (
        <div className="error-banner">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="docs-layout-simple">
        {loading ? (
          <div className="loading-state">
            <Loader2 size={40} className="spin" />
            <p>Generating architectural documentation...</p>
            <span className="loading-sub">Analyzing tree-sitter AST symbols and classes structure</span>
          </div>
        ) : generatedDoc ? (
          <div className="docs-content-simple glass-panel">
            <div className="markdown-body">
              <ReactMarkdown>{generatedDoc}</ReactMarkdown>
            </div>
          </div>
        ) : (
          <div className="empty-state doc-landing">
            <Sparkles size={48} className="doc-sparkle-icon" />
            <h3>Generate Architectural Docs</h3>
            <p>
              RepoIntel will scan the classes, methods, and file tree of <strong>{activeRepo?.name}</strong> to build a unified system architecture blueprint guide.
            </p>
            <button className="primary-btn lg-btn" onClick={handleGenerateDocs}>
              <Sparkles size={16} /> Generate Technical Specification Guide
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
