# User Management API

Backend API for the Augment Chat testing interface.

## Running the API

```bash
# From project root
python run_api.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Endpoints

### Authentication
- `POST /api/auth/login` - Login with username (test mode)
- `GET /api/auth/users` - List all users
- `POST /api/auth/users` - Create new user

### User Management
- `GET /api/users/{user_id}` - Get user profile
- `GET /api/users/{user_id}/status` - Get user status with bridges and rooms
- `DELETE /api/users/{user_id}` - Delete user (TODO)
- `GET /api/users/{user_id}/export` - Export user data (TODO)

### Bridge Management
- `GET /api/users/{user_id}/bridges` - List user's bridges
- `POST /api/users/{user_id}/bridges` - Create new bridge
- `POST /api/users/{user_id}/bridges/{bridge_id}/login` - Login to bridge
- `GET /api/users/{user_id}/bridges/{bridge_id}/status` - Get bridge status
- `DELETE /api/users/{user_id}/bridges/{bridge_id}` - Delete bridge (TODO)

### Room Management
- `GET /api/users/{user_id}/rooms` - List user's rooms (TODO)
- `GET /api/users/{user_id}/rooms/{room_id}` - Get room details (TODO)
- `GET /api/users/{user_id}/rooms/{room_id}/messages` - Get room messages (TODO)
- `POST /api/users/{user_id}/rooms/{room_id}/backfill` - Backfill transcripts (TODO)

### Suggestions
- `POST /api/users/{user_id}/rooms/{room_id}/suggestions` - Generate suggestion (TODO)
- `GET /api/users/{user_id}/rooms/{room_id}/suggestions` - Get room suggestions (TODO)
- `GET /api/suggestions/job/{job_id}` - Poll suggestion job status (TODO)

## Testing with curl

### Create a user
```bash
curl -X POST http://localhost:8000/api/auth/users \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser"}'
```

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser"}'
```

### List users
```bash
curl http://localhost:8000/api/auth/users
```

### Get user profile
```bash
curl http://localhost:8000/api/users/1
```

### Create a WhatsApp bridge
```bash
curl -X POST http://localhost:8000/api/users/1/bridges \
  -H "Content-Type: application/json" \
  -d '{"service": "whatsapp", "credentials": {}}'
```

### List bridges
```bash
curl http://localhost:8000/api/users/1/bridges
```

### Login to bridge
```bash
curl -X POST http://localhost:8000/api/users/1/bridges/BRIDGE_ID/login \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+1234567890"}'
```

## CORS Configuration

The API allows requests from:
- http://localhost:3000 (React default)
- http://localhost:5173 (Vite default)
- http://localhost:5500 (LiveServer)

## Notes

- Authentication is simplified for testing (username only, no passwords)
- Some endpoints marked with TODO are placeholders
- All operations go through UserRegister and UserBridgeManager classes
- Frontend will be built with React + Vite
