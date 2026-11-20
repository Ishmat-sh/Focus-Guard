const API_BASE = (
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function createApiClient({
  getAccessToken,
  getAdminCredentials,
  onUnauthorized,
}) {
  return async function apiFetch(path, options = {}) {
    const { skipAuth = false, ...fetchOptions } = options;
    const headers = new Headers(fetchOptions.headers || {});

    if (!skipAuth && !headers.has("Authorization")) {
      const token = getAccessToken?.();
      const admin = getAdminCredentials?.();
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      } else if (admin) {
        headers.set(
          "Authorization",
          `Basic ${btoa(`${admin.username}:${admin.password}`)}`,
        );
      }
    }

    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, {
        ...fetchOptions,
        headers,
      });
    } catch (error) {
      throw new ApiError(error.message || "Could not connect to Focus Guard");
    }

    if (response.status === 401 && !skipAuth) {
      onUnauthorized?.();
    }
    return response;
  };
}

export async function apiRequest(apiFetch, path, options) {
  const response = await apiFetch(path, options);
  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    if (response.ok) {
      throw new ApiError("The server returned an invalid response", response.status);
    }
  }

  if (!response.ok) {
    throw new ApiError(
      payload?.detail || payload?.message || "The request could not be completed",
      response.status,
    );
  }
  return payload;
}
