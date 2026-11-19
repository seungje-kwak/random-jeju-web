"use client";
// Browser-only conveniences for the random flow (tasks/prd-random-jeju-merge.md US-013, US-016).
// Every read and write is wrapped: private windows and blocked storage just behave as "nothing saved".
import type { RandomPoint, UserProfileInput } from "./types";

const PROFILE_KEY = "rj.profile";       // localStorage: the last onboarding answers
const POINT_KEY = "rj.lastPoint";       // sessionStorage: the last drawn point, so the card survives a tab switch

export type SavedProfile = { user_profile: UserProfileInput; start_time: string; end_time: string };

export function loadProfile(): SavedProfile | null {
  try {
    const raw = window.localStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as SavedProfile;
    if (!v?.user_profile?.interests?.length || !/^\d\d:\d\d$/.test(v.start_time) || !/^\d\d:\d\d$/.test(v.end_time)) return null;
    return v;
  } catch {
    return null;
  }
}

export function saveProfile(p: SavedProfile): void {
  try { window.localStorage.setItem(PROFILE_KEY, JSON.stringify(p)); } catch { /* not saved: onboarding asks again */ }
}

export function loadLastPoint(): RandomPoint | null {
  try {
    const raw = window.sessionStorage.getItem(POINT_KEY);
    return raw ? (JSON.parse(raw) as RandomPoint) : null;
  } catch {
    return null;
  }
}

export function saveLastPoint(p: RandomPoint | null): void {
  try {
    if (p) window.sessionStorage.setItem(POINT_KEY, JSON.stringify(p));
    else window.sessionStorage.removeItem(POINT_KEY);
  } catch { /* the card just resets on the next visit */ }
}

/** Where the traveler goes to pick (or change) their taste before a random course. */
export function randomOnboardingHref(locationId: number): string {
  return `/onboarding?mode=random&location_id=${locationId}`;
}
