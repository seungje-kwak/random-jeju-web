"use client";
// tasks/prd-random-jeju-merge.md US-013: roll the dice, see where it landed and what is near, then plan a day there.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CategoryIcon } from "@/components/CategoryIcon";
import { RandomMap } from "@/components/RandomMap";
import { V9Header } from "@/components/V9Header";
import { ApiError, api } from "@/lib/api";
import { AuthError } from "@/lib/auth";
import { MESSAGES, useLocale } from "@/lib/i18n";
import { loadLastPoint, loadProfile, randomOnboardingHref, saveLastPoint } from "@/lib/random-store";
import type { RandomPoint } from "@/lib/types";

const MIN_ROLL_MS = 700;   // long enough to see the dice tumble even when the API is quick

type Phase = "idle" | "rolling" | "planning" | "rollFailed" | "signInFailed" | "planFailed" | "noCourse";

export default function RandomPage() {
  const { locale } = useLocale();
  const t = MESSAGES[locale].random;
  const account = MESSAGES[locale].account;
  const router = useRouter();
  const [point, setPoint] = useState<RandomPoint | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [hasProfile, setHasProfile] = useState(false);
  const [areaNames, setAreaNames] = useState<Record<string, string>>({});
  const busy = useRef(false);

  useEffect(() => {
    setPoint(loadLastPoint());
    setHasProfile(loadProfile() !== null);
  }, []);
  // Eup/myeon/dong names exist only in Korean; other languages name the area instead ("Jeju City Downtown").
  useEffect(() => {
    if (locale === "ko" || Object.keys(areaNames).length) return;
    api.areas().then((r) => setAreaNames(Object.fromEntries(r.areas.map((a) => [a.id, a.name_en])))).catch(() => {});
  }, [locale, areaNames]);

  async function roll() {
    if (busy.current) return;
    busy.current = true;
    setPhase("rolling");
    const started = Date.now();
    try {
      const p = await api.drawPoint();
      await new Promise((r) => setTimeout(r, Math.max(0, MIN_ROLL_MS - (Date.now() - started))));
      setPoint(p);
      saveLastPoint(p);
      setPhase("idle");
    } catch (e) {
      setPhase(e instanceof AuthError ? "signInFailed" : "rollFailed");
    } finally {
      busy.current = false;
    }
  }

  async function planHere() {
    if (!point || busy.current) return;
    const saved = loadProfile();
    if (!saved) {
      router.push(randomOnboardingHref(point.location_id));
      return;
    }
    busy.current = true;
    setPhase("planning");
    try {
      const course = await api.createRandomCourse(point.location_id, saved.user_profile, saved.start_time, saved.end_time);
      router.push(`/course/${course.id}`);
    } catch (e) {
      setPhase(e instanceof ApiError && e.code === "NO_CANDIDATES" ? "noCourse" : "planFailed");
      busy.current = false;
    }
  }

  const rolling = phase === "rolling";
  const planning = phase === "planning";
  const error = { rollFailed: t.failed, signInFailed: account.signInFailed, planFailed: t.planFailed, noCourse: t.noCourse }[
    phase as "rollFailed" | "signInFailed" | "planFailed" | "noCourse"];
  const name = (p: { name_ko: string; name_en: string }) => (locale === "ko" ? p.name_ko : p.name_en || p.name_ko);
  const placeLabel = (p: RandomPoint) =>
    (locale !== "ko" && p.area_id && areaNames[p.area_id]) || p.adm_nm;

  return (
    <main className="v9-site flex min-h-[100dvh] flex-col">
      <V9Header />
      <div className="grid flex-1 lg:grid-cols-[minmax(0,1fr)_440px]">
        <section className="h-[46dvh] min-h-[280px] lg:h-auto">
          <RandomMap point={point} label={t.mapLabel} markerLabel={t.marker} />
        </section>

        <section className="relative z-10 -mt-5 rounded-t-[24px] bg-white px-5 pb-10 pt-6 shadow-[0_-8px_30px_rgba(20,49,54,.12)] lg:mt-0 lg:rounded-none lg:shadow-none lg:border-l lg:border-[var(--line)]"
          aria-live="polite">
          {!point ? (
            <div className="flex flex-col items-center text-center">
              <h1 className="text-2xl font-extrabold text-[#143136]">{t.title}</h1>
              <p className="mt-2 max-w-[340px] text-[15px] leading-relaxed text-[var(--muted)]">{t.intro}</p>
              <button type="button" onClick={roll} disabled={rolling}
                className="mt-7 grid h-[120px] w-[120px] place-items-center rounded-full bg-[var(--sea)] text-white shadow-[0_10px_24px_rgba(23,109,98,.35)] disabled:opacity-80">
                <span className={`text-[44px] leading-none ${rolling ? "rj-dice-rolling" : ""}`} aria-hidden="true">🎲</span>
                <span className="-mt-3 text-sm font-bold">{rolling ? t.rolling : t.roll}</span>
              </button>
            </div>
          ) : (
            <div>
              <h1 className="text-2xl font-extrabold text-[#143136]">
                {placeLabel(point) ? t.somewhere(placeLabel(point)!) : t.somewhereUnknown}
              </h1>
              <p className="mt-1 text-xs tabular-nums text-[var(--muted)]">{point.lat.toFixed(4)}, {point.lng.toFixed(4)}</p>
              {point.nearest_hub && (
                <p className="mt-3 text-[15px] font-semibold text-[#1f5a52]">
                  {t.nearestHub(name(point.nearest_hub), t.km(point.nearest_hub.km))}
                </p>
              )}

              <h2 className="mt-5 text-xs font-bold tracking-wide text-[#56767b]">{t.nearbyTitle}</h2>
              {point.preview_places.length ? (
                <ul className="mt-2 grid gap-2">
                  {point.preview_places.map((p) => (
                    <li key={p.id} className="flex items-center gap-3 rounded-2xl border border-[var(--line)] p-2">
                      {p.image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={p.image_url} alt="" className="h-14 w-14 shrink-0 rounded-xl object-cover" loading="lazy" />
                      ) : (
                        <span className="grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-[#eff5f2]"><CategoryIcon category={p.category} /></span>
                      )}
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-semibold text-[#143136]">{name(p)}</span>
                        <span className="text-xs text-[var(--muted)]">{t.km(p.km)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-[var(--muted)]">{t.nothingNearby}</p>
              )}

              <div className="mt-6 grid gap-2.5">
                <button type="button" onClick={planHere} disabled={planning || rolling}
                  className="rounded-2xl bg-[var(--sea)] py-4 text-base font-bold text-white">
                  {planning ? t.planning : t.planHere}
                </button>
                <button type="button" onClick={roll} disabled={planning || rolling}
                  className="flex items-center justify-center gap-2 rounded-2xl border border-[var(--line)] bg-white py-3.5 font-bold text-[#143136]">
                  <span className={rolling ? "rj-dice-rolling" : ""} aria-hidden="true">🎲</span>
                  {rolling ? t.rolling : t.rollAgain}
                </button>
                {hasProfile && (
                  <Link href={randomOnboardingHref(point.location_id)} className="mt-1 text-center text-sm font-semibold text-[#56767b] underline underline-offset-4">
                    {t.changeTaste}
                  </Link>
                )}
              </div>
            </div>
          )}
          {error && <p role="alert" className="mt-4 rounded-xl bg-[#fdecea] px-4 py-3 text-sm font-semibold text-[#b3261e]">{error}</p>}
        </section>
      </div>
    </main>
  );
}
