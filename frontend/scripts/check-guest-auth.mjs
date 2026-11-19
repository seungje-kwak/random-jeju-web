// End-to-end check of guest sign-in (tasks/prd-random-jeju-merge.md US-003, US-004, FR-35).
// Signs in anonymously with supabase-js (as lib/auth.ts does), then calls the FastAPI /me endpoints.
// Creates one anonymous user and its users row in the project. Run from frontend/:
//   node --env-file=.env.local scripts/check-guest-auth.mjs
import { createClient } from "@supabase/supabase-js";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
if (!URL || !ANON) throw new Error("NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY missing");

let failed = 0;
const check = (name, ok, detail = "") => { console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`); if (!ok) failed++; };
const call = async (path, token, init = {}) => {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init.headers || {}) },
  });
  let body = null;
  try { body = await res.json(); } catch { /* empty */ }
  return { status: res.status, body };
};

const sb = createClient(URL, ANON, { auth: { persistSession: false, autoRefreshToken: false } });
const { data, error } = await sb.auth.signInAnonymously();
check("anonymous sign-in", !error && !!data.session, error?.message);
if (!data.session) process.exit(1);
const token = data.session.access_token;
const uid = data.user.id;
console.log(`      guest user ${uid.slice(0, 8)}…`);

let r = await call("/me", token);
check("GET /me with the guest token", r.status === 200 && r.body.user_id === uid && r.body.is_anonymous === true && r.body.nickname === null,
  `${r.status} ${JSON.stringify(r.body)}`);

r = await call("/me");
check("GET /me without a token is 401", r.status === 401 && r.body?.detail?.code === "UNAUTHORIZED", String(r.status));

r = await call("/me", ANON);
check("the anon API key is not a user (401)", r.status === 401, String(r.status));

r = await call("/me", token.slice(0, -4) + "AAAA");
check("a tampered token is 401", r.status === 401, String(r.status));

r = await call("/me", token, { method: "POST", body: JSON.stringify({ nickname: "x" }) });
check("1-character nickname is 422 INVALID_NICKNAME", r.status === 422 && r.body?.detail?.code === "INVALID_NICKNAME", String(r.status));

const name = `검증${Math.floor(Math.random() * 9000 + 1000)}`;
r = await call("/me", token, { method: "POST", body: JSON.stringify({ nickname: `  ${name}  ` }) });
check("POST /me saves the nickname (trimmed)", r.status === 200 && r.body.nickname === name, `${r.status} ${JSON.stringify(r.body)}`);

r = await call("/me", token);
check("GET /me returns the saved nickname", r.status === 200 && r.body.nickname === name, JSON.stringify(r.body));

r = await call(`/me?user_id=00000000-0000-0000-0000-000000000000`, token);
check("a user_id in the query is ignored", r.body?.user_id === uid);

console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
console.log(`guest user id (for cleanup): ${uid}`);
process.exit(failed ? 1 : 0);
