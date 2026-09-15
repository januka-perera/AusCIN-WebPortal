import { describe, expect, it } from "vitest";
import { formatCoordinates, formatLocalDateTime, formatOperationalDate } from "./format";

describe("formatCoordinates", () => {
  it("labels southern and eastern hemispheres for Australian coordinates", () => {
    expect(formatCoordinates(-34.42, 150.89)).toBe("34.4200° S, 150.8900° E");
  });

  it("labels northern and western hemispheres for positive/negative inputs", () => {
    expect(formatCoordinates(12.5, -70.25)).toBe("12.5000° N, 70.2500° W");
  });
});

describe("formatOperationalDate", () => {
  it("formats a date-only ISO string without shifting day", () => {
    expect(formatOperationalDate("2018-03-01")).toBe("1 March 2018");
  });
});

describe("formatLocalDateTime", () => {
  it("renders a non-empty, locale-formatted string for a known UTC instant", () => {
    const result = formatLocalDateTime("2025-02-09T20:00:00.000Z", "Australia/Brisbane");
    expect(result.length).toBeGreaterThan(0);
    expect(result).toContain("2025");
    // Brisbane is UTC+10 year-round, so 20:00 UTC on the 9th is 06:00 local on the 10th.
    expect(result).toContain("10");
  });
});
