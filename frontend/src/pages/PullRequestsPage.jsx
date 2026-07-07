import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { GitPullRequest, AlertCircle, CheckCircle, Clock, ChevronRight, Loader2, X } from 'lucide-react';
import { fetchPullRequests, reviewPullRequest } from '../api';

export default function PullRequestsPage() {
  const { owner, repo, activeRepo } = useOutletContext();
  const [prs, setPrs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPR, setSelectedPR] = useState(null);
  const [review, setReview] = useState(null);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!owner || !repo) return;
    loadPRs();
  }, [owner, repo]);

  const loadPRs = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchPullRequests(owner, repo);
      setPrs(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (pr) => {
    setSelectedPR(pr);
    setReview(null);
    setReviewing(true);
    try {
      const data = await reviewPullRequest(owner, repo, pr.number);
      setReview(data);
    } catch (err) {
      setReview({ error: err.message });
    } finally {
      setReviewing(false);
    }
  };

  if (!owner || !repo) {
    return (
      <div className="empty-state">
        <GitPullRequest size={48} strokeWidth={1} />
        <h3>No Repository Selected</h3>
        <p>Select a GitHub repository from the sidebar to view its pull requests.</p>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2>Pull Requests</h2>
          <span className="context-badge">{owner}/{repo}</span>
        </div>
        <button className="secondary-btn" onClick={loadPRs} disabled={loading}>
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
        {/* PR List */}
        <div className="pr-list">
          {loading && prs.length === 0 ? (
            <div className="loading-state"><Loader2 size={24} className="spin" /><p>Fetching pull requests...</p></div>
          ) : prs.length === 0 ? (
            <div className="empty-state small">
              <CheckCircle size={32} strokeWidth={1} />
              <p>No open pull requests</p>
            </div>
          ) : (
            prs.map((pr) => (
              <div
                key={pr.number}
                className={`pr-card ${selectedPR?.number === pr.number ? 'active' : ''}`}
                onClick={() => handleReview(pr)}
              >
                <div className="pr-card-header">
                  <GitPullRequest size={16} className="pr-icon open" />
                  <span className="pr-number">#{pr.number}</span>
                  <ChevronRight size={14} className="pr-chevron" />
                </div>
                <h4 className="pr-title">{pr.title}</h4>
                <div className="pr-meta">
                  <span>{pr.user}</span>
                  <span><Clock size={12} /> {new Date(pr.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Review Panel */}
        <div className="pr-review-panel glass-panel">
          {!selectedPR ? (
            <div className="empty-state">
              <GitPullRequest size={40} strokeWidth={1} />
              <p>Select a pull request to generate an AI review</p>
            </div>
          ) : reviewing ? (
            <div className="loading-state">
              <Loader2 size={32} className="spin" />
              <p>Analyzing PR #{selectedPR.number}...</p>
              <span className="loading-sub">Fetching diff and generating review</span>
            </div>
          ) : review?.error ? (
            <div className="error-banner">
              <AlertCircle size={16} />
              <span>{review.error}</span>
            </div>
          ) : review ? (
            <div className="review-content">
              <div className="review-header">
                <h3>AI Review: #{review.pr_number}</h3>
                <span className={`verdict-badge ${review.review_verdict?.toLowerCase().includes('approve') ? 'approve' : 'changes'}`}>
                  {review.review_verdict?.split('—')[0]?.trim() || 'COMMENT'}
                </span>
              </div>

              <div className="review-sections">
                <ReviewSection title="Summary" content={review.summary} />
                <ReviewSection title="What Changed" content={review.what_changed} />
                <ReviewSection title="Architectural Impact" content={review.architectural_impact} />
                <ReviewSection title="Potential Risks" content={review.potential_risks} />
                <ReviewSection title="Possible Bugs" content={review.possible_bugs} />
                <ReviewSection title="Testing Recommendations" content={review.testing_recommendations} />
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ReviewSection({ title, content }) {
  if (!content || content === 'N/A') return null;
  return (
    <div className="review-section">
      <h4>{title}</h4>
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}
