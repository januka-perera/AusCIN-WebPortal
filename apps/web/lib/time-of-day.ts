/**
 * Named time-of-day buckets for the archive's time-of-day filter.
 * A finite, labelled set of ranges is a simpler and more usable control
 * for a prototype than a free-form minute picker, and lines up with the
 * morning/midday/afternoon/sunset/night rhythm already used to caption
 * the sample observations. Covers the full 24 hours with no gaps.
 *
 * Shared by the station archive and the cross-station observations page
 * (both filter by time of day using the same vocabulary), so it lives
 * under lib/ rather than inside either route.
 */

export type TimeOfDayKey = "morning" | "midday" | "afternoon" | "evening" | "night";

export type TimeOfDayOption = {
  key: TimeOfDayKey;
  label: string;
  startMinutes: number;
  endMinutes: number;
};

export const TIME_OF_DAY_OPTIONS: TimeOfDayOption[] = [
  { key: "morning", label: "Morning (5am–11am)", startMinutes: 300, endMinutes: 659 },
  { key: "midday", label: "Midday (11am–2pm)", startMinutes: 660, endMinutes: 839 },
  { key: "afternoon", label: "Afternoon (2pm–6pm)", startMinutes: 840, endMinutes: 1079 },
  { key: "evening", label: "Evening (6pm–9pm)", startMinutes: 1080, endMinutes: 1259 },
  // Wraps past local midnight: filterMediaByTimeOfDay treats start > end as a wrap.
  { key: "night", label: "Night (9pm–5am)", startMinutes: 1260, endMinutes: 299 },
];

export function getTimeOfDayOption(key: string | undefined): TimeOfDayOption | undefined {
  return TIME_OF_DAY_OPTIONS.find((option) => option.key === key);
}
