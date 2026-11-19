"use client";
// Guest sessions (tasks/prd-random-jeju-merge.md US-003). The first action that needs to know who the
// traveler is (rolling the dice, uploading, liking, commenting) calls accessToken(). Nothing is shown on
// screen: a Supabase anonymous session is made once and kept in localStorage by supabase-js.
import { getSupabase } from "./supabase";

export class AuthError extends Error {
  code: "AUTH_NOT_CONFIGURED" | "SIGN_IN_FAILED";
  constructor(code: AuthError["code"], message: string) {
    super(message);
    this.code = code;
  }
}

let signingIn: Promise<string> | null = null;

/** A valid access token, signing in as a guest first if there is no session. Concurrent callers share one sign-in. */
export async function accessToken(): Promise<string> {
  const sb = getSupabase();
  if (!sb) throw new AuthError("AUTH_NOT_CONFIGURED", "NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY are not set");
  const { data } = await sb.auth.getSession();
  if (data.session) return data.session.access_token;
  if (!signingIn) {
    signingIn = (async () => {
      const { data: created, error } = await sb.auth.signInAnonymously();
      if (error || !created.session) throw new AuthError("SIGN_IN_FAILED", error?.message || "No session");
      return created.session.access_token;
    })().finally(() => { signingIn = null; });
  }
  return signingIn;
}

/** After a 401: ask Supabase for a fresh token once. */
export async function refreshedToken(): Promise<string> {
  const sb = getSupabase();
  if (!sb) throw new AuthError("AUTH_NOT_CONFIGURED", "Supabase is not configured");
  const { data, error } = await sb.auth.refreshSession();
  if (error || !data.session) return accessToken();
  return data.session.access_token;
}

/** Shown until the traveler picks a nickname: "여행자" + the first 4 characters of the user ID (US-003). */
export function guestTag(userId: string): string {
  return userId.replace(/-/g, "").slice(0, 4);
}
