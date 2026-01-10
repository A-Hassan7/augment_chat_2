import axios from 'axios';
import type {
  LoginRequest,
  LoginResponse,
  CreateUserRequest,
  User,
  UserProfile,
  UserStatus,
  Bridge,
  CreateBridgeRequest,
  BridgeLoginRequest,
  BridgeStatusResponse,
  Room,
  RoomDetails,
  MessagesResponse,
  GenerateSuggestionRequest,
  SuggestionResponse,
  SuccessResponse,
} from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Auth endpoints
export const authApi = {
  login: (data: LoginRequest) => 
    api.post<LoginResponse>('/auth/login', data),
  
  listUsers: () => 
    api.get<User[]>('/auth/users'),
  
  createUser: (data: CreateUserRequest) => 
    api.post<LoginResponse>('/auth/users', data),
};

// User endpoints
export const userApi = {
  getProfile: (userId: number) => 
    api.get<UserProfile>(`/users/${userId}`),
  
  getStatus: (userId: number) => 
    api.get<UserStatus>(`/users/${userId}/status`),
  
  deleteUser: (userId: number) => 
    api.delete<SuccessResponse>(`/users/${userId}`),
  
  exportData: (userId: number) => 
    api.get(`/users/${userId}/export`),
};

// Bridge endpoints
export const bridgeApi = {
  list: (userId: number) => 
    api.get<Bridge[]>(`/users/${userId}/bridges`),
  
  create: (userId: number, data: CreateBridgeRequest) => 
    api.post<Bridge>(`/users/${userId}/bridges`, data),
  
  login: (userId: number, bridgeId: string, data: BridgeLoginRequest) => 
    api.post<{ login_code: string; phone_number: string; bridge_id: string }>(
      `/users/${userId}/bridges/${bridgeId}/login`,
      data
    ),
  
  getStatus: (userId: number, bridgeId: string) => 
    api.get<BridgeStatusResponse>(`/users/${userId}/bridges/${bridgeId}/status`),
  
  delete: (userId: number, bridgeId: string) => 
    api.delete<SuccessResponse>(`/users/${userId}/bridges/${bridgeId}`),
};

// Room endpoints
export const roomApi = {
  list: (userId: number, platform?: string) => 
    api.get<Room[]>(`/users/${userId}/rooms`, { params: { platform } }),
  
  getDetails: (userId: number, roomId: string) => 
    api.get<RoomDetails>(`/users/${userId}/rooms/${roomId}`),
  
  getMessages: (userId: number, roomId: string, page = 1, pageSize = 50) => 
    api.get<MessagesResponse>(`/users/${userId}/rooms/${roomId}/messages`, {
      params: { page, page_size: pageSize },
    }),
  
  backfill: (userId: number, roomId: string) => 
    api.post<SuccessResponse>(`/users/${userId}/rooms/${roomId}/backfill`),
};

// Suggestion endpoints
export const suggestionApi = {
  generate: (userId: number, roomId: string, data: GenerateSuggestionRequest) => 
    api.post<SuggestionResponse>(`/users/${userId}/rooms/${roomId}/suggestions`, data),
  
  listForRoom: (userId: number, roomId: string) => 
    api.get<SuggestionResponse[]>(`/users/${userId}/rooms/${roomId}/suggestions`),
  
  getJobStatus: (jobId: string) => 
    api.get<SuggestionResponse>(`/suggestions/job/${jobId}`),
};

export default api;
