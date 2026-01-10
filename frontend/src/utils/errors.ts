// Type for Axios error responses
export interface ApiErrorResponse {
  response?: {
    data?: {
      detail?: string;
    };
  };
}

// Helper function to extract error message
export function getErrorMessage(error: unknown): string {
  const apiError = error as ApiErrorResponse;
  return apiError?.response?.data?.detail || 'An error occurred';
}
