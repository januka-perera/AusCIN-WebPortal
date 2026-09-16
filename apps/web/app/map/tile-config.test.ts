import { describe, expect, it } from "vitest";
import { OSM_DEV_TILE_URL, resolveTileConfig } from "./tile-config";

describe("resolveTileConfig", () => {
  it("falls back to the OpenStreetMap dev tile source when no URL is configured", () => {
    const config = resolveTileConfig(undefined, undefined);
    expect(config).toEqual({
      available: true,
      url: OSM_DEV_TILE_URL,
      attribution: expect.stringContaining("OpenStreetMap"),
      isDevDefault: true,
    });
  });

  it("falls back to the OpenStreetMap dev tile source when the URL is an empty string", () => {
    const config = resolveTileConfig("", undefined);
    expect(config.available).toBe(true);
    if (config.available) {
      expect(config.isDevDefault).toBe(true);
    }
  });

  it("uses a configured tile URL and marks it as not the dev default", () => {
    const config = resolveTileConfig("https://tiles.example.com/{z}/{x}/{y}.png", undefined);
    expect(config).toEqual({
      available: true,
      url: "https://tiles.example.com/{z}/{x}/{y}.png",
      attribution: expect.stringContaining("OpenStreetMap"),
      isDevDefault: false,
    });
  });

  it("uses a configured attribution string when provided alongside a configured URL", () => {
    const config = resolveTileConfig(
      "https://tiles.example.com/{z}/{x}/{y}.png",
      "&copy; Example Tiles",
    );
    expect(config).toEqual({
      available: true,
      url: "https://tiles.example.com/{z}/{x}/{y}.png",
      attribution: "&copy; Example Tiles",
      isDevDefault: false,
    });
  });

  it("treats the literal value \"disabled\" as no tile source available", () => {
    const config = resolveTileConfig("disabled", undefined);
    expect(config).toEqual({ available: false });
  });
});
