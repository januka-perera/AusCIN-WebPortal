import { describe, expect, it } from "vitest";
import { latitudeTicks, longitudeTicks, projectToPercent } from "./geo";

describe("projectToPercent", () => {
  it("projects a station near the eastern edge of the bounds", () => {
    // Seaglass Point: -34.42, 150.89
    const { xPercent, yPercent } = projectToPercent(-34.42, 150.89);
    expect(xPercent).toBeCloseTo(92.595, 2);
    expect(yPercent).toBeCloseTo(71.824, 2);
  });

  it("projects a station near the western edge of the bounds", () => {
    // Cape Mirrigan: -34.0, 115.15
    const { xPercent, yPercent } = projectToPercent(-34.0, 115.15);
    expect(xPercent).toBeCloseTo(7.5, 2);
    expect(yPercent).toBeCloseTo(70.588, 2);
  });

  it("places the north-west corner of the bounds at (0, 0)", () => {
    const { xPercent, yPercent } = projectToPercent(-10, 112);
    expect(xPercent).toBeCloseTo(0, 5);
    expect(yPercent).toBeCloseTo(0, 5);
  });

  it("places the south-east corner of the bounds at (100, 100)", () => {
    const { xPercent, yPercent } = projectToPercent(-44, 154);
    expect(xPercent).toBeCloseTo(100, 5);
    expect(yPercent).toBeCloseTo(100, 5);
  });
});

describe("latitudeTicks", () => {
  it("returns whole 10-degree ticks within the bounds", () => {
    expect(latitudeTicks()).toEqual([-10, -20, -30, -40]);
  });
});

describe("longitudeTicks", () => {
  it("returns whole 10-degree ticks within the bounds", () => {
    expect(longitudeTicks()).toEqual([120, 130, 140, 150]);
  });
});
