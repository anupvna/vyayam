import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, SERVER_UNREACHABLE, api, errorMessage, setCsrfToken } from "./api";

function mockFetch(status: number, body?: unknown) {
  const fn = vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

describe("api", () => {
  it("sends the CSRF token on writes", async () => {
    setCsrfToken("tok");
    const fetch = mockFetch(200, { ok: true });
    await api("/auth/logout", { method: "POST" });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/auth/logout");
    expect(init.headers["X-CSRF-Token"]).toBe("tok");
    expect(init.credentials).toBe("same-origin");
  });

  it("does not send the CSRF token on reads", async () => {
    setCsrfToken("tok");
    const fetch = mockFetch(200, {});
    await api("/auth/me");
    expect(fetch.mock.calls[0][1].headers["X-CSRF-Token"]).toBeUndefined();
  });

  it("sends JSON bodies", async () => {
    const fetch = mockFetch(201, {});
    await api("/auth/signup", { method: "POST", body: { email: "a@b.co" } });
    const init = fetch.mock.calls[0][1];
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ email: "a@b.co" });
  });

  it("returns undefined for 204 No Content", async () => {
    mockFetch(204);
    await expect(api("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("throws ApiError with the server's message", async () => {
    mockFetch(401, { detail: "Invalid email or password" });
    const call = api("/auth/login", { method: "POST", body: {} });
    await expect(call).rejects.toBeInstanceOf(ApiError);
    await expect(call).rejects.toMatchObject({
      status: 401,
      message: "Invalid email or password",
    });
  });
});

describe("errorMessage", () => {
  it("formats FastAPI validation errors by field", () => {
    const detail = [{ loc: ["body", "password"], msg: "String should have at least 10 characters" }];
    expect(errorMessage(detail, "x")).toBe("password: String should have at least 10 characters");
  });

  it("falls back when there is no detail", () => {
    expect(errorMessage(undefined, "fallback")).toBe("fallback");
  });
});

describe("server unreachable", () => {
  it("explains a 502 from the proxy in plain words", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Bad Gateway", { status: 502 })));
    await expect(api("/auth/login", { method: "POST", body: {} })).rejects.toMatchObject({
      status: 502,
      message: SERVER_UNREACHABLE,
    });
    vi.unstubAllGlobals();
  });
});
