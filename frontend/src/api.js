/**
 * Centralized API client for the Repository Intelligence Platform.
 * All backend communication goes through this module.
 */

let API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
if (!API_BASE.endsWith('/api/v1')) {
  if (API_BASE.endsWith('/')) {
    API_BASE = API_BASE.slice(0, -1);
  }
  API_BASE = `${API_BASE}/api/v1`;
}

/**
 * Generic fetch wrapper with error handling.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  };

  const res = await fetch(url, config);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) {
    return null;
  }
  return res.json();
}

// ─── Repositories ────────────────────────────────────────────
export const fetchRepositories = () => request('/repositories/');
export const registerRepository = (data) =>
  request('/repositories/', { method: 'POST', body: JSON.stringify(data) });
export const deleteRepository = (id) =>
  request(`/repositories/${id}`, { method: 'DELETE' });
export const triggerIndexing = (id) =>
  request(`/repositories/${id}/index`, { method: 'POST' });

// ─── Chat ────────────────────────────────────────────────────
export const sendChatMessage = (messages, sessionId, repositoryId) =>
  request('/chatbot/chat', {
    method: 'POST',
    body: JSON.stringify({ messages, session_id: sessionId, repository_id: repositoryId }),
  });
export const fetchChatHistory = (sessionId) =>
  request(`/chatbot/messages?session_id=${sessionId}`);
export const fetchSessions = () => request('/chatbot/sessions');

// ─── Pull Requests ───────────────────────────────────────────
export const fetchPullRequests = (owner, repo, state = 'open') =>
  request(`/pull-requests/${owner}/${repo}?state=${state}`);
export const reviewPullRequest = (owner, repo, prNumber) =>
  request(`/pull-requests/${owner}/${repo}/${prNumber}/review`);

// ─── Issues ──────────────────────────────────────────────────
export const fetchIssues = (owner, repo, state = 'open') =>
  request(`/issues/${owner}/${repo}?state=${state}`);
export const analyzeIssue = (owner, repo, issueNumber) =>
  request(`/issues/${owner}/${repo}/${issueNumber}/analyze`);

// ─── Documentation ──────────────────────────────────────────
export const fetchDocs = (owner, repo) =>
  request(`/docs/${owner}/${repo}`);
export const generateDocs = (owner, repo, repositoryId) =>
  request(`/docs/${owner}/${repo}/generate`, {
    method: 'POST',
    body: JSON.stringify({ repository_id: repositoryId }),
  });

// ─── Jobs ────────────────────────────────────────────────────
export const fetchJob = (jobId) => request(`/jobs/${jobId}`);
export const triggerPRReview = (repoId, diff) =>
  request('/jobs/pr-review', {
    method: 'POST',
    body: JSON.stringify({ repository_id: repoId, diff }),
  });
export const triggerDocGeneration = (repoId) =>
  request('/jobs/documentation', {
    method: 'POST',
    body: JSON.stringify({ repository_id: repoId }),
  });
export const triggerIssueResolution = (repoId, issueText) =>
  request('/jobs/issues', {
    method: 'POST',
    body: JSON.stringify({ repository_id: repoId, issue_text: issueText }),
  });

export default {
  fetchRepositories, registerRepository, deleteRepository, triggerIndexing,
  sendChatMessage, fetchChatHistory, fetchSessions,
  fetchPullRequests, reviewPullRequest,
  fetchIssues, analyzeIssue,
  fetchDocs, generateDocs,
  fetchJob, triggerPRReview, triggerDocGeneration, triggerIssueResolution,
};
