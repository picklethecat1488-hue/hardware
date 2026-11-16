import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { describe, it } from "node:test";

import {
  createMemoryStorage,
  createMockRuntimeContext,
  DEFAULT_BOOT_CONFIG_ID,
} from "../../js/core/runtime_context.js";

describe("RuntimeContext & Mock DOM Isolation", () => {
  it("parses JSON boot configuration from the mock document without touching browser globals", () => {
    const ctx = createMockRuntimeContext({
      bootConfig: {
        project: "cat_fountain",
        target: "product",
        mode: "simulate",
        maxSteps: 150,
      },
      devicePixelRatio: 2.0,
      viewportWidth: 1600,
      viewportHeight: 900,
    });

    const cfg = ctx.getBootConfig();
    assert.equal(cfg.project, "cat_fountain");
    assert.equal(cfg.target, "product");
    assert.equal(cfg.mode, "simulate");
    assert.equal(cfg.maxSteps, 150);
    assert.equal(ctx.getDevicePixelRatio(), 2.0);
    assert.deepEqual(ctx.getViewportSize(), { width: 1600, height: 900 });
  });

  it("throws SyntaxError when boot config script contains invalid JSON", () => {
    const ctx = createMockRuntimeContext({
      bootConfig: "{ broken_json: ",
      bootConfigId: DEFAULT_BOOT_CONFIG_ID,
    });
    assert.throws(() => ctx.getBootConfig(), SyntaxError);
  });

  it("executes mocked HTTP JSON routes and propagates structured HTTP errors", async () => {
    const ctx = createMockRuntimeContext({
      fetchRoutes: {
        "GET /api/status": { status: 200, body: { ok: true, mode: "pcb" } },
        "POST /api/fail": { status: 422, body: { error: "Invalid parameter" } },
      },
    });

    const status = await ctx.fetchJson("/api/status");
    assert.deepEqual(status, { ok: true, mode: "pcb" });

    await assert.rejects(
      () => ctx.postJson("/api/fail", { bad: 1 }),
      (err) => err.status === 422 && err.message === "Invalid parameter",
    );
    assert.equal(ctx.fetchCalls.length, 2);
  });

  it("coalesces animation frames and advances deterministic timers", () => {
    const ctx = createMockRuntimeContext({ initialTimeMs: 500 });
    const fired = [];

    const cancelId = ctx.requestAnimationFrame(() => fired.push("cancelled"));
    ctx.cancelAnimationFrame(cancelId);
    ctx.requestAnimationFrame((ts) => fired.push(`raf:${Math.round(ts)}`));

    ctx.setTimeout(() => fired.push("timeout:100"), 100);
    const intervalId = ctx.setInterval(() => fired.push("interval:40"), 40);

    assert.equal(ctx.flushAnimationFrames(16), 1);
    assert.deepEqual(fired, ["raf:516"]);

    ctx.advanceTime(95);
    ctx.clearInterval(intervalId);
    assert.deepEqual(fired, ["raf:516", "interval:40", "interval:40", "timeout:100"]);
  });

  it("provides isolated storage and base64 binary decoding", () => {
    const storage = createMemoryStorage({ theme: "quake" });
    assert.equal(storage.getItem("theme"), "quake");
    storage.setItem("scale", "1.25");
    assert.equal(storage.getItem("scale"), "1.25");
    storage.removeItem("theme");
    assert.equal(storage.getItem("theme"), null);

    const ctx = createMockRuntimeContext({ storage });
    const raw = new Float32Array([3.5, -7.25, 14.0]);
    const b64 = Buffer.from(raw.buffer).toString("base64");
    const decodedBytes = ctx.decodeBase64Bytes(b64);
    const decodedFloats = new Float32Array(
      decodedBytes.buffer,
      decodedBytes.byteOffset,
      decodedBytes.byteLength / 4,
    );
    assert.deepEqual(Array.from(decodedFloats), [3.5, -7.25, 14.0]);
  });
});
