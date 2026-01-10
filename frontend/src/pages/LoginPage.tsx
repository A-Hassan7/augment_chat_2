import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { authApi } from '../api/client';
import { useAuth } from '../context';
import { getErrorMessage } from '../utils/errors';
import './LoginPage.css';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [showCreateUser, setShowCreateUser] = useState(false);
  const { setCurrentUser } = useAuth();
  const navigate = useNavigate();

  // Fetch existing users
  const { data: users = [], refetch } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const response = await authApi.listUsers();
      return response.data;
    },
  });

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: async (username: string) => {
      const response = await authApi.login({ username });
      return response.data;
    },
    onSuccess: (data) => {
      setCurrentUser({
        id: data.user_id,
        username: data.username,
        matrix_user_id: data.matrix_user_id,
      });
      navigate('/dashboard');
    },
  });

  // Create user mutation
  const createUserMutation = useMutation({
    mutationFn: async (username: string) => {
      const response = await authApi.createUser({ username });
      return response.data;
    },
    onSuccess: (data) => {
      setCurrentUser({
        id: data.user_id,
        username: data.username,
        matrix_user_id: data.matrix_user_id,
      });
      refetch();
      navigate('/dashboard');
    },
  });

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (username.trim()) {
      loginMutation.mutate(username);
    }
  };

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault();
    if (username.trim()) {
      createUserMutation.mutate(username);
    }
  };

  const handleQuickLogin = (username: string) => {
    loginMutation.mutate(username);
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>Augment Chat</h1>
        <p className="subtitle">User Management</p>

        {!showCreateUser ? (
          <>
            <form onSubmit={handleLogin} className="login-form">
              <input
                type="text"
                placeholder="Enter username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input"
              />
              <button
                type="submit"
                disabled={loginMutation.isPending}
                className="button button-primary"
              >
                {loginMutation.isPending ? 'Logging in...' : 'Login'}
              </button>
            </form>

            {loginMutation.isError && (
              <p className="error">
                Login failed: {getErrorMessage(loginMutation.error)}
              </p>
            )}

            <button
              onClick={() => setShowCreateUser(true)}
              className="button button-secondary"
            >
              Create New User
            </button>

            {users.length > 0 && (
              <div className="quick-switch">
                <h3>Quick Switch</h3>
                <div className="user-list">
                  {users.map((user) => (
                    <button
                      key={user.id}
                      onClick={() => handleQuickLogin(user.username)}
                      className="user-item"
                    >
                      <div className="user-name">{user.username}</div>
                      <div className="user-matrix">{user.matrix_user_id}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <>
            <form onSubmit={handleCreateUser} className="login-form">
              <input
                type="text"
                placeholder="Enter new username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input"
              />
              <button
                type="submit"
                disabled={createUserMutation.isPending}
                className="button button-primary"
              >
                {createUserMutation.isPending ? 'Creating...' : 'Create User'}
              </button>
            </form>

            {createUserMutation.isError && (
              <p className="error">
                Create failed: {getErrorMessage(createUserMutation.error)}
              </p>
            )}

            <button
              onClick={() => setShowCreateUser(false)}
              className="button button-secondary"
            >
              Back to Login
            </button>
          </>
        )}
      </div>
    </div>
  );
}
