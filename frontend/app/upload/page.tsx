"use client";
// tasks/prd-random-jeju-merge.md US-021: choose a photo, its position comes from the photo (EXIF) when it has
// one, otherwise from the phone's location or a tap on the map. Category is required; text is optional.
import exifr from "exifr";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useNicknameGate } from "@/components/NicknameDialog";
import { PickMap } from "@/components/PickMap";
import { TabBar, TabBarSpacer } from "@/components/TabBar";
import { V9Header } from "@/components/V9Header";
import { ApiError, api } from "@/lib/api";
import { AuthError } from "@/lib/auth";
import { MESSAGES, useLocale } from "@/lib/i18n";
import { POST_CATEGORIES, type LocationSource, type PostCategory, type PostMeta } from "@/lib/types";

const MAX_BYTES = 15 * 1024 * 1024;
const MAX_TEXT = 500;
const DEVICE_ACCURACY_M = 100;   // US-021: the phone's position counts only when it is this precise
type Spot = { lat: number; lng: number; source: LocationSource };
type Status = "idle" | "locating" | "sending" | "error";

/** EXIF "2026:11:20 14:03:00" (+ "+09:00" when the camera wrote one) -> ISO. No offset = Korea time (server). */
function exifTime(raw: unknown, offset: unknown): string | undefined {
  if (typeof raw !== "string") return undefined;
  const m = raw.match(/^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/);
  if (!m) return undefined;
  const off = typeof offset === "string" && /^[+-]\d{2}:\d{2}$/.test(offset) ? offset : "";
  return `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}${off}`;
}

export default function UploadPage() {
  const t = MESSAGES[useLocale().locale].social;
  const account = MESSAGES[useLocale().locale].account;
  const router = useRouter();
  const { gate, dialog } = useNicknameGate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [exifSpot, setExifSpot] = useState<Spot | null>(null);
  const [spot, setSpot] = useState<Spot | null>(null);
  const [takenAt, setTakenAt] = useState<string | undefined>();
  const [picking, setPicking] = useState(false);
  const [category, setCategory] = useState<PostCategory | null>(null);
  const [text, setText] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [courseId, setCourseId] = useState<string | null>(null);

  useEffect(() => {
    try { setCourseId(new URLSearchParams(window.location.search).get("course_id")); } catch { /* none */ }
  }, []);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  async function choose(f: File | undefined) {
    if (!f) return;
    setMessage(null);
    if (f.size > MAX_BYTES) { setMessage(t.errFileTooLarge); return; }
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setSpot(null);
    setExifSpot(null);
    setTakenAt(undefined);
    setPicking(false);
    try {
      const gps = await exifr.gps(f).catch(() => undefined);
      const meta = await exifr.parse(f, { pick: ["DateTimeOriginal", "OffsetTimeOriginal"], reviveValues: false }).catch(() => undefined);
      if (gps && Number.isFinite(gps.latitude) && Number.isFinite(gps.longitude)) {
        const s: Spot = { lat: gps.latitude, lng: gps.longitude, source: "exif" };
        setExifSpot(s);
        setSpot(s);
      }
      setTakenAt(exifTime(meta?.DateTimeOriginal, meta?.OffsetTimeOriginal));
    } catch { /* no EXIF: the traveler picks a position */ }
  }

  function useDevice() {
    if (!navigator.geolocation) { setMessage(t.locDenied); return; }
    setStatus("locating");
    setMessage(null);
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      setStatus("idle");
      if (coords.accuracy > DEVICE_ACCURACY_M) { setMessage(t.locWeak(Math.round(coords.accuracy))); return; }
      setSpot({ lat: coords.latitude, lng: coords.longitude, source: "device" });
      setPicking(false);
    }, () => { setStatus("idle"); setMessage(t.locDenied); }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || status === "sending") return;
    if (!category) { setMessage(t.categoryRequired); return; }
    setStatus("sending");
    setMessage(null);
    try {
      if (!(await gate())) { setStatus("idle"); return; }     // US-003: a nickname before the first post
      const meta: PostMeta = { category, content: text.trim() || undefined, taken_at: takenAt, course_id: courseId ?? undefined };
      if (spot) Object.assign(meta, { lat: spot.lat, lng: spot.lng, location_source: spot.source });
      const r = await api.createPost(file, meta);
      // US-021: the feed says "checked in" when this photo checked in at the traveler's course (FR-20)
      router.push(`/feed?posted=${encodeURIComponent(r.post.post_id)}${r.visit ? "&checkin=1" : ""}`);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : null;
      setStatus("error");
      setMessage(err instanceof AuthError ? account.signInFailed
        : code === "FILE_TOO_LARGE" ? t.errFileTooLarge
        : code === "UNSUPPORTED_IMAGE" ? t.errUnsupported
        : code === "UPLOAD_LIMIT" ? t.errLimit
        : t.errGeneric);
    }
  }

  const sourceLabel = spot ? { exif: t.locExif, device: t.locDevice, manual: t.locManual }[spot.source] : null;
  return (
    <main className="v9-site min-h-[100dvh]">
      <V9Header />
      <TabBar />
      <form onSubmit={submit} className="mx-auto max-w-[560px] px-4 pt-5">
        <h1 className="text-2xl font-extrabold text-[#143136]">{t.uploadTitle}</h1>
        {courseId && <p className="mt-2 rounded-xl bg-[#eff7f3] px-4 py-2.5 text-sm font-semibold text-[#1f5a52]">📍 {t.fromCourse}</p>}

        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only"
          onChange={(e) => choose(e.target.files?.[0])} aria-label={t.pick} />
        {preview ? (
          <div className="mt-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="" className="max-h-[420px] w-full rounded-[20px] bg-[#eef1ee] object-contain" />
            <button type="button" onClick={() => fileRef.current?.click()} className="v9-outline mt-2">{t.change}</button>
          </div>
        ) : (
          <button type="button" onClick={() => fileRef.current?.click()}
            className="mt-4 grid h-[220px] w-full place-items-center rounded-[20px] border-2 border-dashed border-[#bcd5cc] bg-[#f6faf8] text-center">
            <span>
              <span className="block text-4xl" aria-hidden="true">📷</span>
              <span className="mt-2 block font-bold text-[#143136]">{t.pick}</span>
              <span className="mt-1 block text-xs text-[var(--muted)]">{t.pickHint}</span>
            </span>
          </button>
        )}

        {file && (
          <>
            <h2 className="mt-6 text-xs font-bold tracking-wide text-[#56767b]">{t.location}</h2>
            <p className="mt-1 text-sm font-semibold text-[#143136]">
              {spot ? `${sourceLabel} · ${spot.lat.toFixed(4)}, ${spot.lng.toFixed(4)}` : exifSpot ? "" : t.locNone}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" onClick={useDevice} disabled={status === "locating"} className="v9-outline">
                ⌖ {status === "locating" ? t.locating : t.useDevice}
              </button>
              <button type="button" onClick={() => setPicking((p) => !p)} aria-pressed={picking} className="v9-outline">
                🗺️ {t.pickOnMap}
              </button>
              {exifSpot && spot?.source !== "exif" && (
                <button type="button" onClick={() => { setSpot(exifSpot); setPicking(false); }} className="v9-outline">📷 {t.locExif}</button>
              )}
            </div>
            {picking && <p className="mt-2 text-xs font-semibold text-[var(--sea)]">{t.pickOnMapHint}</p>}
            <div className="mt-2">
              <PickMap point={spot} picking={picking} label={t.location} failedText={t.mapFailed}
                onPick={(lat, lng) => { setSpot({ lat, lng, source: "manual" }); setPicking(false); }} />
            </div>
            {!spot && <p className="mt-2 text-xs text-[var(--muted)]">{t.noLocation}</p>}

            <h2 className="mt-6 text-xs font-bold tracking-wide text-[#56767b]">{t.category}</h2>
            <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label={t.category}>
              {POST_CATEGORIES.map((c) => (
                <button key={c} type="button" onClick={() => { setCategory(c); setMessage(null); }} aria-pressed={category === c}
                  className={`rounded-full border px-4 py-2 text-sm font-bold ${category === c ? "border-[var(--sea)] bg-[var(--sea)] text-white" : "border-[var(--line)] bg-white text-[#143136]"}`}>
                  {t.categories[c]}
                </button>
              ))}
            </div>

            <label htmlFor="post-text" className="mt-6 block text-xs font-bold tracking-wide text-[#56767b]">{t.content}</label>
            <textarea id="post-text" value={text} onChange={(e) => setText(e.target.value.slice(0, MAX_TEXT))} rows={3}
              placeholder={t.contentPlaceholder}
              className="mt-2 w-full rounded-xl border border-[var(--line)] px-3.5 py-3 text-[15px] outline-none focus:border-[var(--sea)]" />
            <p className="text-right text-xs text-[var(--muted)]">{text.length}/{MAX_TEXT}</p>

            <p className="mt-4 rounded-xl bg-[#fff8e6] px-4 py-3 text-sm text-[#6b5313]">ⓘ {t.publicNotice}</p>
            {message && <p role="alert" className="mt-3 rounded-xl bg-[#fdecea] px-4 py-3 text-sm font-semibold text-[#b3261e]">{message}</p>}
            <button type="submit" disabled={status === "sending"} className="mt-4 w-full rounded-2xl bg-[var(--sea)] py-4 text-base font-bold text-white disabled:opacity-60">
              {status === "sending" ? t.submitting : t.submit}
            </button>
          </>
        )}
        {!file && message && <p role="alert" className="mt-3 rounded-xl bg-[#fdecea] px-4 py-3 text-sm font-semibold text-[#b3261e]">{message}</p>}
        <TabBarSpacer />
      </form>
      {dialog}
    </main>
  );
}
