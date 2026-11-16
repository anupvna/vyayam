// The offline path end to end, with a fake IndexedDB and a fake network.
import { IDBFactory } from "fake-indexeddb";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, OFFLINE_NEEDS_CONNECTION, OFFLINE_NOT_SAVED, QUEUED, api, setCsrfToken, setSessionUser } from "../api";
import { offlineSet } from "./queue";
import { SIGNED_OUT_EVENT, SYNCED_EVENT, getStatus, syncEvents, updateStatus } from "./status";
import { clearUser, getRead, listOutbox, resetStoreForTests, saveRead } from "./store";
import { flush } from "./sync";

type Route = (init: RequestInit) => Response | "offline";
let routes: Record<string, Route> = {};
const calls: { key: string; init: RequestInit }[] = [];

function fakeNetwork() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      const key = `${init.method} ${url.replace(/^\/api/, "")}`;
      calls.push({ key, init });
      const route = routes[key] ?? routes["*"];
      const res = route ? route(init) : "offline";
      if (res === "offline") throw new TypeError("Failed to fetch");
      return res;
    }),
  );
}

const json = (status: number, body?: unknown) => () =>
  new Response(body === undefined ? null : JSON.stringify(body), { status });
const offline = () => "offline" as const;

const events: string[] = [];
const onSynced = () => events.push("synced");
const onSignedOut = () => events.push("signed-out");

beforeEach(() => {
  vi.stubGlobal("indexedDB", new IDBFactory());
  resetStoreForTests();
  routes = {};
  calls.length = 0;
  events.length = 0;
  setSessionUser("u1");
  setCsrfToken("tok");
  updateStatus({ online: true, pending: 0, syncing: false, failed: [], justSynced: false });
  fakeNetwork();
  syncEvents.addEventListener(SYNCED_EVENT, onSynced);
  syncEvents.addEventListener(SIGNED_OUT_EVENT, onSignedOut);
});

afterEach(() => {
  vi.unstubAllGlobals();
  setSessionUser(null);
  setCsrfToken(null);
  syncEvents.removeEventListener(SYNCED_EVENT, onSynced);
  syncEvents.removeEventListener(SIGNED_OUT_EVENT, onSignedOut);
});

const newSet = (id: string, set_index = 1) => ({
  id,
  day: "2026-11-16",
  exercise_id: "bench_press",
  set_index,
  weight_kg: 60,
  reps: 8,
  rir: 2,
});
const logSet = (id: string, set_index = 1) => {
  const body = newSet(id, set_index);
  return api("/logs", { method: "POST", body, offline: () => offlineSet(body) });
};

describe("reading offline", () => {
  it("saves each screen and shows the saved copy with no connection", async () => {
    routes["GET /profile"] = json(200, { name: "fresh" });
    expect(await api("/profile")).toEqual({ name: "fresh" });
    await vi.waitFor(async () => expect(await getRead("u1", "/profile")).toBeDefined());

    routes["GET /profile"] = offline;
    expect(await api("/profile")).toEqual({ name: "fresh" });
    expect(getStatus().online).toBe(false);
  });

  it("explains when a screen was never saved", async () => {
    await expect(api("/plan/week?today=2026-11-20")).rejects.toMatchObject({ status: 0, message: OFFLINE_NOT_SAVED });
  });

  it("never saves sign-in answers", async () => {
    routes["GET /auth/me"] = json(200, { user: { id: "u1" }, csrf_token: "secret" });
    await api("/auth/me");
    expect(await getRead("u1", "/auth/me")).toBeUndefined();
  });

  it("keeps each user's saved screens apart, and logout clears them", async () => {
    await saveRead("u1", "/profile", { who: 1 });
    await saveRead("u2", "/profile", { who: 2 });
    await clearUser("u1");
    expect(await getRead("u1", "/profile")).toBeUndefined();
    expect((await getRead("u2", "/profile"))?.data).toEqual({ who: 2 });
  });
});

describe("changing things offline", () => {
  it("sends straight away when online", async () => {
    routes["POST /logs"] = json(201, { ...offlineSet(newSet("a")), pr: true });
    expect(await logSet("a")).toMatchObject({ pr: true });
    expect(await listOutbox("u1")).toEqual([]);
  });

  it("keeps the set on the phone and shows it as typed when offline", async () => {
    expect(await logSet("a")).toMatchObject({ id: "a", pr: false });
    const box = await listOutbox("u1");
    expect(box.map((i) => [i.method, i.path])).toEqual([["POST", "/logs"]]);
    expect(getStatus()).toMatchObject({ online: false, pending: 1 });
  });

  it("puts later changes behind waiting ones, even once online", async () => {
    await logSet("a", 1);
    routes["*"] = json(201, {});
    await logSet("b", 2);
    expect(calls.filter((c) => c.key === "POST /logs")).toHaveLength(1); // only the first, offline try
    expect((await listOutbox("u1")).map((i) => (i.body as { id: string }).id)).toEqual(["a", "b"]);
  });

  it("says plan changes need a connection", async () => {
    const call = api("/plan/days/2026-11-16/skip", { method: "POST", body: {} });
    await expect(call).rejects.toBeInstanceOf(ApiError);
    await expect(call).rejects.toMatchObject({ status: 0, message: OFFLINE_NEEDS_CONNECTION });
  });

  it("shows waiting sets on today's workout, from the saved copy", async () => {
    await saveRead("u1", "/training/today?today=2026-11-16", {
      day: { logged_sets: 0 },
      readiness: null,
      stop: false,
      exercises: [{ exercise_id: "bench_press", logged: [] }],
    });
    await logSet("a");
    const t = await api<{ exercises: { logged: { id: string }[] }[] }>("/training/today?today=2026-11-16");
    expect(t.exercises[0].logged.map((s) => s.id)).toEqual(["a"]);
  });

  it("undoing an unsent set leaves nothing to send", async () => {
    await logSet("a");
    expect(await api("/logs/a", { method: "DELETE", offline: () => QUEUED })).toBe(QUEUED);
    expect(await listOutbox("u1")).toEqual([]);
  });

  it("refuses to queue for nobody (signed out)", async () => {
    setSessionUser(null);
    await expect(logSet("a")).rejects.toMatchObject({ status: 0 });
  });
});

describe("syncing", () => {
  it("sends everything in order once back online, then says so", async () => {
    await logSet("a", 1);
    await logSet("b", 2);
    await api("/body/weights/2026-11-16", { method: "PUT", body: { weight_kg: 80 }, offline: () => QUEUED });

    calls.length = 0;
    routes["*"] = json(201, {});
    await flush();
    expect(calls.map((c) => c.key)).toEqual(["POST /logs", "POST /logs", "PUT /body/weights/2026-11-16"]);
    expect(calls.map((c) => (c.init.headers as Record<string, string>)["X-CSRF-Token"])).toEqual(["tok", "tok", "tok"]);
    expect(await listOutbox("u1")).toEqual([]);
    expect(getStatus()).toMatchObject({ online: true, pending: 0, justSynced: true });
    expect(events).toContain("synced");
  });

  it("stops at the first network failure and keeps the rest", async () => {
    await logSet("a", 1);
    await logSet("b", 2);
    let n = 0;
    routes["POST /logs"] = () => (n++ === 0 ? new Response("{}", { status: 201 }) : "offline");
    await flush();
    expect((await listOutbox("u1")).map((i) => (i.body as { id: string }).id)).toEqual(["b"]);
    expect(getStatus()).toMatchObject({ online: false, pending: 1 });
  });

  it("drops a change the server refuses, tells the user, and carries on", async () => {
    await logSet("a", 1);
    await logSet("b", 2);
    let n = 0;
    routes["POST /logs"] = () =>
      n++ === 0 ? new Response(JSON.stringify({ detail: "Set is from another account" }), { status: 409 }) : new Response("{}", { status: 201 });
    await flush();
    expect(await listOutbox("u1")).toEqual([]);
    expect(getStatus().failed).toEqual([{ path: "/logs", status: 409, message: "Set is from another account" }]);
  });

  it("keeps changes on server errors, to retry later", async () => {
    await logSet("a");
    routes["POST /logs"] = json(503, { detail: "busy" });
    await flush();
    expect(await listOutbox("u1")).toHaveLength(1);
    expect(getStatus().failed).toEqual([]);
  });

  it("gets a fresh CSRF token first after an offline start", async () => {
    await logSet("a");
    setCsrfToken(null);
    calls.length = 0;
    routes["GET /auth/me"] = json(200, { user: { id: "u1", email: "a@b.co" }, csrf_token: "new" });
    routes["POST /logs"] = json(201, {});
    await flush();
    expect(calls.map((c) => c.key)).toEqual(["GET /auth/me", "POST /logs"]);
    expect((calls[1].init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("new");
  });

  it("retries once with a fresh token when the old one is refused", async () => {
    await logSet("a");
    let n = 0;
    routes["POST /logs"] = () => new Response("{}", { status: n++ === 0 ? 403 : 201 });
    routes["GET /auth/me"] = json(200, { user: { id: "u1", email: "a@b.co" }, csrf_token: "new" });
    await flush();
    expect(await listOutbox("u1")).toEqual([]);
  });

  it("keeps changes and signs out if the session ended", async () => {
    await logSet("a");
    setCsrfToken(null);
    routes["GET /auth/me"] = json(401, { detail: "Not signed in" });
    await flush();
    expect(await listOutbox("u1")).toHaveLength(1);
    expect(events).toContain("signed-out");
  });

  it("only sends the signed-in user's changes", async () => {
    await logSet("a");
    setSessionUser("u2");
    routes["*"] = json(201, {});
    calls.length = 0;
    await flush();
    expect(calls).toEqual([]);
    expect(await listOutbox("u1")).toHaveLength(1);
  });
});
