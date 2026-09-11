import { BASE_URL, PREFIX, ApiError } from "./api";

export async function courtRequest<T>(
  path: string,
  options: { method?: string; body?: any; unauthenticated?: boolean } = {}
): Promise<T> {
  const headers: HeadersInit = {
    Accept: "application/json",
  };

  if (!options.unauthenticated) {
    const token = typeof window !== "undefined" ? sessionStorage.getItem("court_token") : null;
    if (!token) {
      if (typeof window !== "undefined") window.location.href = "/court-access";
      throw new ApiError(401, "No court session active.");
    }
    headers.Authorization = `Bearer ${token}`;
  }

  if (options.body) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${BASE_URL}${PREFIX}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload?.detail || payload?.error?.message || message;
    } catch {}
    if (response.status === 401 && !options.unauthenticated) {
      if (typeof window !== "undefined") {
          sessionStorage.removeItem("court_token");
          window.location.href = "/court-access";
      }
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
