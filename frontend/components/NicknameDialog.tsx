"use client";
// US-003: asked once, before the first post or comment. Later features call `gate()` from useNicknameGate.
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { api } from "@/lib/api";
import { guestTag } from "@/lib/auth";
import { MESSAGES, useLocale } from "@/lib/i18n";
import type { Me } from "@/lib/types";

const MIN = 2;
const MAX = 12;
// \p{C}: control, format (zero-width marks), private-use and unassigned characters, like Python's category "C*".
// RegExp(String.raw...) rather than a /u literal: tsconfig targets ES5; every supported browser has Unicode properties.
const OTHER_CHARS = new RegExp(String.raw`\p{C}`, "u");

/** Same rule as the server (main.clean_nickname); the server still has the last word. */
export function nicknameOk(raw: string): boolean {
  const name = raw.trim();
  return name.length >= MIN && name.length <= MAX && !OTHER_CHARS.test(name);
}

export function displayName(me: Me, guestName: (tag: string) => string): string {
  return me.nickname ?? guestName(guestTag(me.user_id));
}

export function NicknameDialog({ onSaved, onCancel }: { onSaved: (me: Me) => void; onCancel: () => void }) {
  const t = MESSAGES[useLocale().locale].account;
  const [value, setValue] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "invalid" | "failed">("idle");
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelRef = useRef(onCancel);
  cancelRef.current = onCancel;

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") cancelRef.current(); };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = before;
      window.removeEventListener("keydown", onKey);
      opener?.focus({ preventScroll: true });
    };
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!nicknameOk(value)) { setState("invalid"); return; }
    setState("saving");
    try {
      onSaved(await api.saveNickname(value.trim()));
    } catch (err) {
      setState((err as { code?: string })?.code === "INVALID_NICKNAME" ? "invalid" : "failed");
    }
  }

  const message = state === "invalid" ? t.invalid(MIN, MAX) : state === "failed" ? t.failed : t.nicknameRule(MIN, MAX);
  return createPortal(
    <div role="dialog" aria-modal="true" aria-labelledby="nickname-title"
      className="fixed inset-0 z-[1000] grid place-items-center bg-black/40 p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <form onSubmit={save} className="w-full max-w-[400px] rounded-[20px] border border-[var(--line)] bg-white p-6 shadow-xl">
        <h2 id="nickname-title" className="text-xl font-extrabold text-[#143136]">{t.nicknameTitle}</h2>
        <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">{t.nicknameBody}</p>
        <label htmlFor="nickname-input" className="mt-5 block text-xs font-bold tracking-wide text-[#56767b]">{t.nicknameLabel}</label>
        <input id="nickname-input" ref={inputRef} value={value} maxLength={40} autoComplete="nickname"
          placeholder={t.nicknamePlaceholder}
          onChange={(e) => { setValue(e.target.value); if (state !== "saving") setState("idle"); }}
          aria-invalid={state === "invalid"} aria-describedby="nickname-help"
          className="mt-1.5 w-full rounded-xl border border-[var(--line)] px-3.5 py-3 text-base outline-none focus:border-[var(--sea)]" />
        <p id="nickname-help" role={state === "idle" ? undefined : "alert"}
          className={`mt-1.5 text-xs ${state === "invalid" || state === "failed" ? "text-[#b3261e]" : "text-[var(--muted)]"}`}>
          {message}
        </p>
        <div className="mt-6 grid grid-cols-2 gap-2.5">
          <button type="button" onClick={onCancel} className="rounded-xl border border-[var(--line)] bg-white py-3 font-bold">{t.cancel}</button>
          <button type="submit" disabled={state === "saving"} className="rounded-xl bg-[var(--sea)] py-3 font-bold text-white disabled:opacity-60">
            {state === "saving" ? t.saving : t.save}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  );
}

/**
 * `gate()` resolves to the traveler with a nickname, or null if they closed the dialog.
 * It signs in as a guest first when needed (the first api call does that). Render `dialog` once.
 */
export function useNicknameGate(): { gate: () => Promise<Me | null>; dialog: ReactNode } {
  const [pending, setPending] = useState<((me: Me | null) => void) | null>(null);
  const cached = useRef<Me | null>(null);

  const gate = useCallback(async () => {
    if (cached.current?.nickname) return cached.current;
    const me = await api.me();
    cached.current = me;
    if (me.nickname) return me;
    return new Promise<Me | null>((resolve) => setPending(() => resolve));
  }, []);

  const finish = (me: Me | null) => {
    if (me) cached.current = me;
    pending?.(me);
    setPending(null);
  };
  const dialog = pending ? <NicknameDialog onSaved={(me) => finish(me)} onCancel={() => finish(null)} /> : null;
  return { gate, dialog };
}
