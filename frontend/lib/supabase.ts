"use client";
// Supabase is used for sign-in only (tasks/prd-random-jeju-merge.md FR-34). All data goes through FastAPI (lib/api.ts).
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const URL = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").trim();
// The anon (publishable) key is meant to be public. RLS has no policies for it, so it reads no data.
const ANON_KEY = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "").trim();

let client: SupabaseClient | null = null;

/** null when the two NEXT_PUBLIC_SUPABASE_* variables are missing. */
export function getSupabase(): SupabaseClient | null {
  if (!URL || !ANON_KEY || typeof window === "undefined") return null;
  if (!client) {
    client = createClient(URL, ANON_KEY, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, storageKey: "rj.auth" },
    });
  }
  return client;
}
