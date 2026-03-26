import type { ApiEnvelope } from "../types/api";

type FetchLike = typeof fetch;

export class HttpClient {
  private readonly baseUrl: string;
  private readonly getToken: () => string | null;
  private readonly fetcher: FetchLike;

  public constructor(baseUrl: string, getToken: () => string | null, fetcher: FetchLike = fetch) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.getToken = getToken;
    this.fetcher = fetcher.bind(globalThis);
  }

  public async get<TResponse>(path: string): Promise<TResponse> {
    return this.request<TResponse>(path, "GET");
  }

  public async post<TResponse, TPayload>(path: string, payload: TPayload): Promise<TResponse> {
    return this.request<TResponse>(path, "POST", payload);
  }

  private async request<TResponse>(
    path: string,
    method: "GET" | "POST",
    payload?: unknown
  ): Promise<TResponse> {
    const headers: Record<string, string> = {
      Accept: "application/json"
    };
    const token = this.getToken();

    if (token !== null) {
      headers.Authorization = `Bearer ${token}`;
    }
    if (payload !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: payload === undefined ? undefined : JSON.stringify(payload)
    });

    const rawBody = await response.text();
    let envelope: ApiEnvelope<TResponse> | null = null;
    try {
      envelope = JSON.parse(rawBody) as ApiEnvelope<TResponse>;
    } catch {
      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }
      throw new Error("Invalid API response format");
    }
    if (!response.ok || envelope.status !== "ok" || envelope.data === undefined) {
      throw new Error(envelope.message ?? "Request failed");
    }
    return envelope.data;
  }
}
