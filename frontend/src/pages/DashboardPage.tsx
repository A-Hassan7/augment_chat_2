import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context';
import { userApi } from '../api/client';
import './DashboardPage.css';

export default function DashboardPage() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const { data: profile, isLoading } = useQuery({
    queryKey: ['userProfile', currentUser?.id],
    queryFn: async () => {
      if (!currentUser) return null;
      const response = await userApi.getProfile(currentUser.id);
      return response.data;
    },
    enabled: !!currentUser,
  });

  const { data: status } = useQuery({
    queryKey: ['userStatus', currentUser?.id],
    queryFn: async () => {
      if (!currentUser) return null;
      const response = await userApi.getStatus(currentUser.id);
      return response.data;
    },
    enabled: !!currentUser,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  if (isLoading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Dashboard</h1>
        <button onClick={handleLogout} className="button button-secondary">
          Logout
        </button>
      </header>

      <div className="dashboard-content">
        <div className="profile-card">
          <h2>Profile</h2>
          <div className="profile-info">
            <div className="info-row">
              <span className="label">Username:</span>
              <span className="value">{profile?.username}</span>
            </div>
            <div className="info-row">
              <span className="label">Matrix ID:</span>
              <span className="value">{profile?.matrix_user_id}</span>
            </div>
            <div className="info-row">
              <span className="label">User ID:</span>
              <span className="value">{profile?.id}</span>
            </div>
          </div>
        </div>

        <div className="stats-grid">
          <div className="stat-card" onClick={() => navigate('/bridges')}>
            <div className="stat-number">{profile?.bridge_count || 0}</div>
            <div className="stat-label">Bridges</div>
          </div>
          <div className="stat-card" onClick={() => navigate('/rooms')}>
            <div className="stat-number">{profile?.room_count || 0}</div>
            <div className="stat-label">Rooms</div>
          </div>
        </div>

        <div className="actions-card">
          <h2>Quick Actions</h2>
          <div className="actions-grid">
            <button
              onClick={() => navigate('/bridges')}
              className="action-button"
            >
              <span className="action-icon">🌉</span>
              <span>Manage Bridges</span>
            </button>
            <button
              onClick={() => navigate('/rooms')}
              className="action-button"
            >
              <span className="action-icon">💬</span>
              <span>View Rooms</span>
            </button>
          </div>
        </div>

        {status && status.bridges.length > 0 && (
          <div className="bridges-card">
            <h2>Your Bridges</h2>
            <div className="bridge-list">
              {status.bridges.map((bridge) => (
                <div key={bridge.bridge_id} className="bridge-item">
                  <div className="bridge-service">{bridge.service}</div>
                  <div className={`bridge-status status-${bridge.status}`}>
                    {bridge.status}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
