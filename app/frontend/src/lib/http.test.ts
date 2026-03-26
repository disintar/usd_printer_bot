import { describe, expect, it, vi } from "vitest";

import { HttpClient } from "./http";

describe("HttpClient", () => {
  it("adds bearer token and unwraps response envelopes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () =>
        JSON.stringify({
        status: "ok",
        data: { token: "123" }
      }),
    });

    const client = new HttpClient("/api", () => "session-token", fetchMock);
    const response = await client.post<{ token: string }, { telegram_user_id: number }>(
      "/auth/telegram",
      { telegram_user_id: 7 }
    );

    expect(response.token).toBe("123");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/telegram",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer session-token",
          "Content-Type": "application/json"
        })
      })
    );
  });

  it("throws the backend message on error responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      text: async () =>
        JSON.stringify({
        status: "error",
        message: "Authentication required"
      }),
    });

    const client = new HttpClient("/api", () => null, fetchMock);

    await expect(client.get("/test/balance")).rejects.toThrow("Authentication required");
  });
});
