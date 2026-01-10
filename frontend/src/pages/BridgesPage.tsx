import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context';
import { bridgeApi } from '../api/client';
import { getErrorMessage } from '../utils/errors';
import './BridgesPage.css';

export default function BridgesPage() {
  const { currentUser } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [service, setService] = useState('whatsapp');
  const [loginBridgeId, setLoginBridgeId] = useState<string | null>(null);
  const [phoneNumber, setPhoneNumber] = useState('');

  const { data: bridges = [], isLoading } = useQuery({
    queryKey: ['bridges', currentUser?.id],
    queryFn: async () => {
      if (!currentUser) return [];
      const response = await bridgeApi.list(currentUser.id);
      return response.data;
    },
    enabled: !!currentUser,
  });

  const createBridgeMutation = useMutation({
    mutationFn: async (service: string) => {
      if (!currentUser) throw new Error('No user');
      const response = await bridgeApi.create(currentUser.id, { service });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bridges', currentUser?.id] });
      setShowCreateForm(false);
      setService('whatsapp');
    },
  });

  const loginMutation = useMutation({
    mutationFn: async ({ bridgeId, phone }: { bridgeId: string; phone: string }) => {
      if (!currentUser) throw new Error('No user');
      const response = await bridgeApi.login(currentUser.id, bridgeId, { phone_number: phone });
      return response.data;
    },
    onSuccess: (data) => {
      alert(`Login initiated! Code: ${data.login_code}\nPhone: ${data.phone_number}`);
      setLoginBridgeId(null);
      setPhoneNumber('');
      queryClient.invalidateQueries({ queryKey: ['bridges', currentUser?.id] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (bridgeId: string) => {
      if (!currentUser) throw new Error('No user');
      await bridgeApi.delete(currentUser.id, bridgeId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bridges', currentUser?.id] });
    },
  });

  const handleCreateBridge = (e: React.FormEvent) => {
    e.preventDefault();
    createBridgeMutation.mutate(service);
  };

  const handleLogin = (bridgeId: string) => {
    if (phoneNumber.trim()) {
      loginMutation.mutate({ bridgeId, phone: phoneNumber });
    }
  };

  if (isLoading) {
    return <div className="loading">Loading bridges...</div>;
  }

  return (
    <div className="bridges-page">
      <header className="page-header">
        <button onClick={() => navigate('/dashboard')} className="back-button">
          ← Back
        </button>
        <h1>Bridge Management</h1>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="button button-primary"
        >
          {showCreateForm ? 'Cancel' : 'Create Bridge'}
        </button>
      </header>

      <div className="page-content">
        {showCreateForm && (
          <div className="create-form-card">
            <h2>Create New Bridge</h2>
            <form onSubmit={handleCreateBridge}>
              <div className="form-group">
                <label>Service:</label>
                <select
                  value={service}
                  onChange={(e) => setService(e.target.value)}
                  className="select-input"
                >
                  <option value="whatsapp">WhatsApp</option>
                  <option value="discord">Discord</option>
                  <option value="telegram">Telegram</option>
                </select>
              </div>
              <button
                type="submit"
                disabled={createBridgeMutation.isPending}
                className="button button-primary"
              >
                {createBridgeMutation.isPending ? 'Creating...' : 'Create'}
              </button>
            </form>
            {createBridgeMutation.isError && (
              <p className="error">
                {getErrorMessage(createBridgeMutation.error)}
              </p>
            )}
          </div>
        )}

        <div className="bridges-list">
          {bridges.length === 0 ? (
            <div className="empty-state">
              <p>No bridges yet. Create one to get started!</p>
            </div>
          ) : (
            bridges.map((bridge) => (
              <div key={bridge.bridge_id} className="bridge-card">
                <div className="bridge-header">
                  <div>
                    <h3>{bridge.service}</h3>
                    <p className="bridge-id">{bridge.orchestrator_id}</p>
                  </div>
                  <span className={`status-badge status-${bridge.status}`}>
                    {bridge.status}
                  </span>
                </div>

                <div className="bridge-details">
                  <div className="detail-row">
                    <span>Matrix Bot:</span>
                    <span className="mono">{bridge.matrix_bot_username}</span>
                  </div>
                  <div className="detail-row">
                    <span>Owner:</span>
                    <span className="mono">{bridge.owner_matrix_username}</span>
                  </div>
                  <div className="detail-row">
                    <span>Created:</span>
                    <span>{new Date(bridge.created_at).toLocaleString()}</span>
                  </div>
                </div>

                <div className="bridge-actions">
                  {loginBridgeId === bridge.orchestrator_id ? (
                    <div className="login-form">
                      <input
                        type="tel"
                        placeholder="Phone number (e.g., +1234567890)"
                        value={phoneNumber}
                        onChange={(e) => setPhoneNumber(e.target.value)}
                        className="input"
                      />
                      <button
                        onClick={() => handleLogin(bridge.orchestrator_id)}
                        disabled={loginMutation.isPending}
                        className="button button-primary"
                      >
                        {loginMutation.isPending ? 'Logging in...' : 'Submit'}
                      </button>
                      <button
                        onClick={() => {
                          setLoginBridgeId(null);
                          setPhoneNumber('');
                        }}
                        className="button button-secondary"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        onClick={() => setLoginBridgeId(bridge.orchestrator_id)}
                        className="button button-primary"
                      >
                        Login
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('Delete this bridge?')) {
                            deleteMutation.mutate(bridge.orchestrator_id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                        className="button button-danger"
                      >
                        Delete
                      </button>
                    </>
                  )}
                </div>

                {loginMutation.isError && loginBridgeId === bridge.orchestrator_id && (
                  <p className="error">
                    {getErrorMessage(loginMutation.error)}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
