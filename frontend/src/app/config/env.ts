const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function getInitialApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (typeof configured !== "string") {
    return DEFAULT_API_BASE_URL;
  }

  const value = configured.trim();
  return value.length > 0 ? value : DEFAULT_API_BASE_URL;
}
