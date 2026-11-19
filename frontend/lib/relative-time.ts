// "5분 전" in the traveler's language (US-024: the server sends ISO times; the old server sent Korean text and
// compared clocks in different time zones).
import type { Locale } from "./i18n";

const TAGS: Record<Locale, string> = { ko: "ko", en: "en", ja: "ja", zh: "zh-CN" };
const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["minute", 60], ["hour", 3600], ["day", 86400], ["week", 604800],
];

export function relativeTime(iso: string, locale: Locale, justNow: string, now: number = Date.now()): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const sec = Math.round((now - t) / 1000);
  if (sec < 60) return justNow;
  if (sec >= 30 * 86400) {
    return new Intl.DateTimeFormat(TAGS[locale], { year: "numeric", month: "short", day: "numeric", timeZone: "Asia/Seoul" }).format(t);
  }
  const fmt = new Intl.RelativeTimeFormat(TAGS[locale], { numeric: "auto" });
  let unit: Intl.RelativeTimeFormatUnit = "minute";
  let size = 60;
  for (const [u, s] of STEPS) if (sec >= s) { unit = u; size = s; }
  return fmt.format(-Math.floor(sec / size), unit);
}
