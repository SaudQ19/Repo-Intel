import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { MessageSquare, GitPullRequest, FileText, Bug, Layers, Plus, Folder, Loader2, Trash2, AlertCircle } from 'lucide-react';
import { registerRepository, triggerIndexing, deleteRepository } from '../api';

const navItems = [
  { to: '/', icon: MessageSquare, label: 'Chat' },
  { to: '/pull-requests', icon: GitPullRequest, label: 'Pull Requests' },
  { to: '/docs', icon: FileText, label: 'Documentation' },
  { to: '/issues', icon: Bug, label: 'Issues' },
];

export default function Layout({ repos, activeRepoId, setActiveRepoId, loadRepos }) {
  const activeRepo = repos.find(r => r.id === activeRepoId);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [name, setName] = useState('');
  const [cloneUrl, setCloneUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Parse owner/repo from clone_url for MCP endpoints
  const getOwnerRepo = () => {
    if (!activeRepo) return { owner: '', repo: '' };
    const url = activeRepo.clone_url;
    // Handle GitHub URLs: https://github.com/owner/repo.git
    const match = url.match(/github\.com[/:]([^/]+)\/([^/.]+)/);
    if (match) return { owner: match[1], repo: match[2] };
    return { owner: '', repo: activeRepo.name };
  };

  const { owner, repo } = getOwnerRepo();

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!name || !cloneUrl) return;
    setLoading(true);
    setError('');

    try {
      // 1. Register repository
      const newRepo = await registerRepository({ name, clone_url: cloneUrl, branch });
      
      // 2. Trigger indexing
      try {
        await triggerIndexing(newRepo.id);
      } catch (idxErr) {
        console.error('Trigger indexing failed:', idxErr);
      }

      // 3. Clear inputs & close form
      setName('');
      setCloneUrl('');
      setBranch('main');
      setIsFormOpen(false);

      // 4. Refresh repositories list in App state
      if (loadRepos) {
        await loadRepos();
        setActiveRepoId(newRepo.id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation(); // Prevent choosing as active repo
    if (!confirm('Are you sure you want to delete this repository? All parsed chunks will be deleted.')) return;
    try {
      await deleteRepository(id);
      if (loadRepos) {
        await loadRepos();
        if (activeRepoId === id) {
          setActiveRepoId('');
        }
      }
    } catch (err) {
      alert(`Failed to delete repository: ${err.message}`);
    }
  };

  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
      <nav className="nav-sidebar glass-panel">
        <div className="brand">
          <div className="brand-icon">
            <Layers size={18} strokeWidth={2.5} />
          </div>
          <span>RepoIntel</span>
        </div>

        {/* Page Nav Links */}
        <div className="nav-links">
          <label className="section-label">Features</label>
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>

        {/* Codebases Direct List */}
        <div className="nav-codebases-list">
          <label className="section-label">Codebases</label>
          <div className="sidebar-repos-list">
            {repos.length === 0 ? (
              <span className="sidebar-no-repos">No repositories registered.</span>
            ) : (
              repos.map((r) => {
                const isSelected = r.id === activeRepoId;
                return (
                  <div
                    key={r.id}
                    onClick={() => setActiveRepoId(r.id)}
                    className={`sidebar-repo-item-container ${isSelected ? 'active' : ''}`}
                  >
                    <button className="sidebar-repo-select-btn">
                      <Folder size={14} className="repo-folder-icon" />
                      <span className="repo-item-name">
                        {r.name}
                        {r.status === 'indexing' && (
                          <span className="repo-indexing-status-text"> (indexing...)</span>
                        )}
                        {r.status === 'pending' && (
                          <span className="repo-indexing-status-text"> (pending...)</span>
                        )}
                      </span>
                    </button>
                    
                    {r.status === 'indexing' && (
                      <Loader2 size={12} className="spin status-spinner" />
                    )}
                    {r.status === 'pending' && (
                      <span className="status-dot-mini pending" title="Pending" />
                    )}
                    {r.status === 'active' && (
                      <span className="status-dot-mini active" title="Active & Ready" />
                    )}
                    {r.status === 'failed' && (
                      <span className="status-dot-mini failed" title="Indexing Failed" />
                    )}

                    <button
                      className="sidebar-repo-delete-btn"
                      onClick={(e) => handleDelete(r.id, e)}
                      title="Delete codebase"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Bottom Left Corner - Register Repository Form */}
        <div className="nav-register-footer">
          {!isFormOpen ? (
            <button
              className="register-trigger-btn"
              onClick={() => setIsFormOpen(true)}
            >
              <Plus size={16} />
              <span>Register Repository</span>
            </button>
          ) : (
            <form onSubmit={handleRegister} className="sidebar-register-form glass-panel">
              <div className="register-form-header">
                <h4>New Codebase</h4>
                <button
                  type="button"
                  className="close-form-btn"
                  onClick={() => setIsFormOpen(false)}
                >
                  ✕
                </button>
              </div>

              {error && (
                <div className="form-error-box">
                  <AlertCircle size={12} />
                  <span>{error}</span>
                </div>
              )}

              <input
                type="text"
                placeholder="Name (e.g. Flask)"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                disabled={loading}
              />
              <input
                type="text"
                placeholder="Git URL / Local Path"
                value={cloneUrl}
                onChange={(e) => setCloneUrl(e.target.value)}
                required
                disabled={loading}
              />
              <input
                type="text"
                placeholder="Branch (default: main)"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                disabled={loading}
              />

              <button type="submit" className="form-submit-btn" disabled={loading}>
                {loading ? <Loader2 size={12} className="spin" /> : 'Register & Index'}
              </button>
            </form>
          )}
        </div>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        <Outlet context={{ repos, activeRepoId, activeRepo, owner, repo }} />
      </main>
    </div>
  );
}
