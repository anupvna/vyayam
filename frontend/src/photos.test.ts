import "fake-indexeddb/auto";

import { describe, expect, it } from "vitest";

import { addPhoto, daysSinceLast, defaultPair, deletePhoto, listPhotos, type Photo } from "./photos";

const photo = (id: string, userId: string, day: string, pose: Photo["pose"] = "front"): Photo => ({
  id,
  userId,
  day,
  pose,
  blob: new Blob(["x"], { type: "image/jpeg" }),
  createdAt: Date.parse(day),
});

describe("on-device photo store", () => {
  it("stores, lists in date order, and keeps accounts separate", async () => {
    await addPhoto(photo("b", "anoop", "2026-11-15"));
    await addPhoto(photo("a", "anoop", "2026-11-01"));
    await addPhoto(photo("c", "guest", "2026-11-10"));
    expect((await listPhotos("anoop")).map((p) => p.id)).toEqual(["a", "b"]);
    expect((await listPhotos("guest")).map((p) => p.id)).toEqual(["c"]);
  });

  it("only lets an account delete its own photos", async () => {
    await deletePhoto("c", "anoop"); // not Anoop's: nothing happens
    expect(await listPhotos("guest")).toHaveLength(1);
    await deletePhoto("c", "guest");
    expect(await listPhotos("guest")).toHaveLength(0);
  });

  it("works out reminders and the default comparison", () => {
    const photos = [photo("1", "u", "2026-10-01"), photo("2", "u", "2026-10-15", "side"), photo("3", "u", "2026-11-01")];
    expect(daysSinceLast(photos, "2026-11-16")).toBe(15);
    expect(daysSinceLast([], "2026-11-16")).toBeNull();
    expect(defaultPair(photos, "front")?.map((p) => p.id)).toEqual(["1", "3"]);
    expect(defaultPair(photos, "side")).toBeNull();
  });
});
