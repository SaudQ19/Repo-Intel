import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ChatPage from './pages/ChatPage';
import PullRequestsPage from './pages/PullRequestsPage';
import DocsPage from './pages/DocsPage';
import IssuesPage from './pages/IssuesPage';
import { fetchRepositories } from './api';

export default function App() {
  const [repos, setRepos] = useState([]);
  const [activeRepoId, setActiveRepoId] = useState('');

  const loadRepos = async () => {
    try {
      const data = await fetchRepositories();
      setRepos(data);
      if (data.length > 0 && !activeRepoId) {
        // Find first active repository, else fallback to first one
        const active = data.find((r) => r.status === 'active') || data[0];
        setActiveRepoId(active.id);
      }
    } catch (err) {
      console.error('Failed to load repositories:', err);
    }
  };

  useEffect(() => {
    loadRepos();
  }, []);

  // Poll repos list if any repo is currently indexing or pending
  useEffect(() => {
    const hasPendingOrIndexing = repos.some(
      (r) => r.status === 'indexing' || r.status === 'pending'
    );
    if (!hasPendingOrIndexing) return;

    const interval = setInterval(() => {
      loadRepos();
    }, 4000);

    return () => clearInterval(interval);
  }, [repos]);

  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <Layout
              repos={repos}
              activeRepoId={activeRepoId}
              setActiveRepoId={setActiveRepoId}
              loadRepos={loadRepos}
            />
          }
        >
          <Route path="/" element={<ChatPage />} />
          <Route path="/pull-requests" element={<PullRequestsPage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/issues" element={<IssuesPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
