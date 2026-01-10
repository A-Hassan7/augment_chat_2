import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context';
import { roomApi } from '../api/client';
import './RoomsPage.css';

export default function RoomsPage() {
  const { currentUser } = useAuth();
  const navigate = useNavigate();

  const { data: rooms = [], isLoading } = useQuery({
    queryKey: ['rooms', currentUser?.id],
    queryFn: async () => {
      if (!currentUser) return [];
      const response = await roomApi.list(currentUser.id);
      return response.data;
    },
    enabled: !!currentUser,
  });

  if (isLoading) {
    return <div className="loading">Loading rooms...</div>;
  }

  return (
    <div className="rooms-page">
      <header className="page-header">
        <button onClick={() => navigate('/dashboard')} className="back-button">
          ← Back
        </button>
        <h1>Rooms</h1>
      </header>

      <div className="page-content">
        <div className="rooms-list">
          {rooms.length === 0 ? (
            <div className="empty-state">
              <p>No rooms found. Create a bridge and connect to start chatting!</p>
            </div>
          ) : (
            rooms.map((room) => (
              <div key={room.room_id} className="room-card">
                <div className="room-header">
                  <h3>{room.room_name}</h3>
                  <span className="platform-badge">{room.platform}</span>
                </div>
                <div className="room-details">
                  <div className="detail-row">
                    <span>Messages:</span>
                    <span>{room.message_count}</span>
                  </div>
                  {room.last_message_at && (
                    <div className="detail-row">
                      <span>Last Activity:</span>
                      <span>{new Date(room.last_message_at).toLocaleString()}</span>
                    </div>
                  )}
                  <div className="detail-row">
                    <span>Room ID:</span>
                    <span className="mono">{room.room_id}</span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
