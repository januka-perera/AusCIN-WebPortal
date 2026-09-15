import { describe, expect, it } from "vitest";
import {
  formatCoordinates,
  formatDayHeading,
  formatFileSize,
  formatLocalDateTime,
  formatLocalTime,
  formatOperationalDate,
  formatShortDate,
  getLocalDateKey,
  getLocalMinutesOfDay,
} from "./format";

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

describe("getLocalDateKey", () => {
  it("resolves the local calendar date even when it differs from the UTC date", () => {
    // 20:00 UTC on the 9th is 06:00 AEST on the 10th in Brisbane (UTC+10).
    expect(getLocalDateKey("2025-02-09T20:00:00.000Z", "Australia/Brisbane")).toBe("2025-02-10");
  });

  it("matches the UTC date for a time zone where no shift occurs", () => {
    expect(getLocalDateKey("2025-02-10T02:00:00.000Z", "Australia/Brisbane")).toBe("2025-02-10");
  });
});

describe("getLocalMinutesOfDay", () => {
  it("returns 0 at local midnight, not 1440", () => {
    // 14:00 UTC is 00:00 AEST the next day in Brisbane (UTC+10).
    expect(getLocalMinutesOfDay("2025-02-09T14:00:00.000Z", "Australia/Brisbane")).toBe(0);
  });

  it("computes minutes since local midnight for a known instant", () => {
    // 20:00 UTC on the 9th is 06:00 local in Brisbane -> 6 * 60 = 360.
    expect(getLocalMinutesOfDay("2025-02-09T20:00:00.000Z", "Australia/Brisbane")).toBe(360);
  });
});

describe("formatDayHeading", () => {
  it("formats a local date key as a full weekday heading", () => {
    expect(formatDayHeading("2025-02-12")).toBe("Wednesday 12 February 2025");
  });
});

describe("formatShortDate", () => {
  it("formats a local date key compactly", () => {
    expect(formatShortDate("2025-02-12")).toBe("12 Feb");
  });
});

describe("formatLocalTime", () => {
  it("formats a time-only label in the given time zone", () => {
    expect(formatLocalTime("2025-02-09T20:00:00.000Z", "Australia/Brisbane")).toBe("6:00 am");
  });
});

describe("formatFileSize", () => {
  it("formats bytes below 1 KB", () => {
    expect(formatFileSize(500)).toBe("500 B");
  });

  it("formats kilobytes", () => {
    expect(formatFileSize(2048)).toBe("2.0 KB");
  });

  it("formats megabytes", () => {
    expect(formatFileSize(1_296_000)).toBe("1.2 MB");
  });
});
