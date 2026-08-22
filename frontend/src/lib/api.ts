import type {
  AuthResponse, Budget, BudgetUpsert, CategorySpend, ChatMessage, ChatResponse,
  CurrentUser, Forecast, PurchaseEvaluation, SafeToSpend, Transaction,
  TransactionCreate, Velocity,
} from "./types";

const BASE_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "spendshield_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Fired when the API rejects our token, so the app can send the user to /login
 *  instead of rendering a dashboard full of failed requests. */
const UNAUTHORIZED_EVENT = "spendshield:unauthorized";
export function onUnauthorized(handler: () => void): () => void {
  window.addEventListener(UNAUTHORIZED_EVENT, handler);
  return () => window.removeEventListener(UNAUTHORIZED_EVENT, handler);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    // fetch only rejects on network failure, never on a 4xx/5xx.
    throw new ApiError(0, "Couldn't reach the SpendShield API. Is the backend running?");
  }

  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // no JSON body; keep the status text
    }
    if (res.status === 401 && token) {
      clearToken();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  async login(email: string, password: string): Promise<AuthResponse> {
    // OAuth2 password flow requires form encoding, not JSON.
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!res.ok) {
      const detail = await res.json().then((b) => b?.detail).catch(() => null);
      throw new ApiError(res.status, detail ?? "Invalid email or password");
    }
    return res.json() as Promise<AuthResponse>;
  },

  /** Sends credentials in a JSON body. They used to go in the query string,
   *  which writes passwords into access logs and browser history. */
  register: (email: string, password: string, fullName: string): Promise<AuthResponse> =>
    request<AuthResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        full_name: fullName || null,
      }),
    }),

  startDemo: (): Promise<AuthResponse> =>
    request<AuthResponse>("/api/v1/demo", { method: "POST" }),

  me: (): Promise<CurrentUser> => request<CurrentUser>("/api/v1/auth/me"),

  deleteAccount: (): Promise<void> =>
    request<void>("/api/v1/auth/me", { method: "DELETE" }),

  getSafeToSpend: (): Promise<SafeToSpend> => request<SafeToSpend>("/api/v1/safe-to-spend"),

  getCurrentBudget: (): Promise<Budget> => request<Budget>("/api/v1/budgets/current"),

  saveBudget: (payload: BudgetUpsert): Promise<Budget> =>
    request<Budget>("/api/v1/budgets", { method: "PUT", body: JSON.stringify(payload) }),

  evaluatePurchase: (price: number, category: string): Promise<PurchaseEvaluation> =>
    request<PurchaseEvaluation>("/api/v1/purchase/evaluate", {
      method: "POST",
      body: JSON.stringify({ price, category }),
    }),

  listTransactions: (limit = 50): Promise<Transaction[]> =>
    request<Transaction[]>(`/api/v1/transactions?limit=${limit}`),

  createTransaction: (payload: TransactionCreate): Promise<Transaction> =>
    request<Transaction>("/api/v1/transactions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  deleteTransaction: (id: string): Promise<void> =>
    request<void>(`/api/v1/transactions/${id}`, { method: "DELETE" }),

  getForecast: (): Promise<Forecast> => request<Forecast>("/api/v1/forecast"),

  getVelocity: (): Promise<Velocity> => request<Velocity>("/api/v1/analytics/velocity"),

  getCategories: (): Promise<CategorySpend[]> =>
    request<CategorySpend[]>("/api/v1/analytics/categories"),

  chat: (message: string, history: ChatMessage[]): Promise<ChatResponse> =>
    request<ChatResponse>("/api/v1/copilot/chat", {
      method: "POST",
      body: JSON.stringify({ message, history }),
    }),
};

/** ₹ with Indian digit grouping (1,20,000 not 120,000). */
export function formatINR(amount: number, withDecimals = false): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: withDecimals ? 2 : 0,
    maximumFractionDigits: withDecimals ? 2 : 0,
  }).format(amount);
}
