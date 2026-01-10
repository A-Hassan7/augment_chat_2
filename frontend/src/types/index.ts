// User types
export interface User {
  id: number;
  username: string;
  matrix_user_id: string;
  matrix_password?: string;
  created_at?: string;
}

export interface UserProfile extends User {
  bridge_count: number;
  room_count: number;
}

export interface UserStatus {
  user_id: number;
  username: string;
  matrix_user_id: string;
  bridge_count: number;
  room_count: number;
  bridges: BridgeInfo[];
  recent_activity: ActivityItem[];
}

export interface ActivityItem {
  type: string;
  timestamp: string;
  description: string;
}

// Bridge types
export interface Bridge {
  bridge_id: string;
  orchestrator_id: string;
  service: string;
  status: string;
  matrix_bot_username: string;
  owner_matrix_username: string;
  created_at: string;
  connection_data?: Record<string, unknown>;
}

export interface BridgeInfo {
  bridge_id: string;
  service: string;
  status: string;
  created_at: string | null;
}

export interface BridgeStatusResponse {
  bridge_id: string;
  service: string;
  live_status: string | null;
  ready_status: string | null;
  last_status_update: string | null;
  matrix_bot_username: string;
  created_at: string;
}

// Room types
export interface Room {
  room_id: string;
  room_name: string;
  platform: string;
  message_count: number;
  last_message_at: string | null;
}

export interface RoomDetails extends Room {
  participants: string[];
  created_at: string;
}

export interface Message {
  event_id: string;
  sender: string;
  content: string;
  timestamp: string;
  message_type: string;
}

export interface MessagesResponse {
  room_id: string;
  messages: Message[];
  total_count: number;
  page: number;
  page_size: number;
}

// Suggestion types
export interface Suggestion {
  id: string;
  room_id: string;
  suggestion_type: string;
  content: string;
  created_at: string;
  status: string;
}

export interface SuggestionResponse {
  job_id?: string;
  status: string;
  suggestion?: Suggestion;
  error?: string;
}

// API Request/Response types
export interface LoginRequest {
  username: string;
}

export interface LoginResponse {
  user_id: number;
  username: string;
  matrix_user_id: string;
  message: string;
}

export interface CreateUserRequest {
  username: string;
}

export interface CreateBridgeRequest {
  service: string;
  credentials?: Record<string, unknown>;
}

export interface BridgeLoginRequest {
  phone_number: string;
}

export interface GenerateSuggestionRequest {
  suggestion_type: string;
  until_message_event_id?: string;
}

export interface SuccessResponse {
  message: string;
}
