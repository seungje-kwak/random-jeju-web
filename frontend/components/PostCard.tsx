"use client";
// tasks/prd-random-jeju-merge.md US-025 - US-027: one photo post, its like button and its comment sheet.
// Shared by the feed and the photo map's bottom sheet.
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ApiError, api } from "@/lib/api";
import { MESSAGES, useLocale } from "@/lib/i18n";
import { relativeTime } from "@/lib/relative-time";
import type { Author, Comment, Post } from "@/lib/types";
import { useNicknameGate } from "./NicknameDialog";

export function useAuthorName() {
  const M = MESSAGES[useLocale().locale];
  return (a: Author) => a.nickname ?? (a.tag ? M.account.guestName(a.tag) : M.social.unknownAuthor);
}

export function PostCard({ post, onChange, priority = false }: {
  post: Post;
  onChange: (next: Post) => void;
  priority?: boolean;
}) {
  const { locale } = useLocale();
  const t = MESSAGES[locale].social;
  const name = useAuthorName();
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [likeError, setLikeError] = useState(false);
  const busy = useRef(false);

  async function toggleLike() {
    if (busy.current) return;
    busy.current = true;
    setLikeError(false);
    const before = post;
    // US-026: change the screen at once, put it back if the server says no
    onChange({ ...post, is_liked: !post.is_liked, like_count: post.like_count + (post.is_liked ? -1 : 1) });
    try {
      const r = await api.like(post.post_id);
      onChange({ ...before, is_liked: r.liked, like_count: r.like_count });
    } catch {
      onChange(before);
      setLikeError(true);
    } finally {
      busy.current = false;
    }
  }

  return (
    <article className="overflow-hidden rounded-[20px] border border-[var(--line)] bg-white">
      <header className="flex items-center gap-2 px-4 py-3">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-[#eff5f2] text-sm font-bold text-[#1f5a52]" aria-hidden="true">
          {name(post.author).slice(0, 1)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-bold text-[#143136]">{name(post.author)}</span>
          <time className="text-xs text-[var(--muted)]" dateTime={post.created_at}>{relativeTime(post.created_at, locale, t.justNow)}</time>
        </span>
        <span className="rounded-full bg-[#eff5f2] px-2.5 py-1 text-xs font-bold text-[#1f5a52]">#{t.categories[post.category]}</span>
      </header>
      {post.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={post.image_url} alt={post.content || t.categories[post.category]} loading={priority ? "eager" : "lazy"}
          className="aspect-square w-full bg-[#eef1ee] object-cover" />
      )}
      <div className="px-4 pb-4 pt-3">
        <div className="flex items-center gap-4 text-sm">
          <button type="button" onClick={toggleLike} aria-pressed={post.is_liked} aria-label={post.is_liked ? t.unlike : t.like}
            className={`flex items-center gap-1.5 font-bold ${post.is_liked ? "text-[#d6336c]" : "text-[#143136]"}`}>
            <span aria-hidden="true" className="text-lg leading-none">{post.is_liked ? "♥" : "♡"}</span>
            {t.likeCount(post.like_count)}
          </button>
          <button type="button" onClick={() => setCommentsOpen(true)} className="flex items-center gap-1.5 font-bold text-[#143136]">
            <span aria-hidden="true" className="text-lg leading-none">💬</span>
            {t.commentCount(post.comment_count)}
          </button>
        </div>
        {likeError && <p role="alert" className="mt-2 text-xs font-semibold text-[#b3261e]">{t.likeFailed}</p>}
        {post.content && <p className="mt-2 whitespace-pre-line break-words text-[15px] leading-relaxed text-[#203f37]">{post.content}</p>}
      </div>
      {commentsOpen && (
        <CommentsSheet post={post} onClose={() => setCommentsOpen(false)}
          onAdded={() => onChange({ ...post, comment_count: post.comment_count + 1 })} />
      )}
    </article>
  );
}

function CommentsSheet({ post, onClose, onAdded }: { post: Post; onClose: () => void; onAdded: () => void }) {
  const { locale } = useLocale();
  const t = MESSAGES[locale].social;
  const name = useAuthorName();
  const { gate, dialog } = useNicknameGate();
  const [list, setList] = useState<Comment[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [text, setText] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "invalid" | "failed">("idle");
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const endRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    let alive = true;
    api.comments(post.post_id).then((r) => alive && setList(r.comments)).catch(() => alive && setFailed(true));
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closeRef.current(); };
    window.addEventListener("keydown", onKey);
    return () => { alive = false; document.body.style.overflow = before; window.removeEventListener("keydown", onKey); };
  }, [post.post_id]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const body = text.trim();
    if (!body || body.length > 500) { setState("invalid"); return; }
    setState("sending");
    try {
      if (!(await gate())) { setState("idle"); return; }   // US-003: a nickname before the first comment
      const c = await api.addComment(post.post_id, body);
      setList((prev) => [...(prev ?? []), c]);
      setText("");
      setState("idle");
      onAdded();
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ block: "end" }));
    } catch (err) {
      setState(err instanceof ApiError && err.code === "INVALID_COMMENT" ? "invalid" : "failed");
    }
  }

  return createPortal(
    <div role="dialog" aria-modal="true" aria-labelledby="comments-title" className="fixed inset-0 z-[900] flex items-end justify-center bg-black/40 sm:items-center"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="flex max-h-[80dvh] w-full max-w-[520px] flex-col rounded-t-[24px] bg-white sm:rounded-[24px]">
        <div className="flex items-center justify-between border-b border-[var(--line)] px-5 py-4">
          <h2 id="comments-title" className="text-lg font-extrabold text-[#143136]">{t.commentsTitle}</h2>
          <button type="button" onClick={onClose} className="h-9 w-9 rounded-full bg-[#f2f5f2]" aria-label={t.close}>✕</button>
        </div>
        <ul className="flex-1 space-y-3 overflow-y-auto px-5 py-4" aria-live="polite">
          {list === null && !failed && <li className="text-sm text-[var(--muted)]">…</li>}
          {failed && <li className="text-sm text-[#b3261e]">{t.loadFailed}</li>}
          {list?.length === 0 && <li className="text-sm text-[var(--muted)]">{t.noComments}</li>}
          {list?.map((c) => (
            <li key={c.id} className="text-sm">
              <span className="font-bold text-[#143136]">{name(c.author)}</span>{" "}
              <time className="text-xs text-[var(--muted)]" dateTime={c.created_at}>{relativeTime(c.created_at, locale, t.justNow)}</time>
              <p className="mt-0.5 whitespace-pre-line break-words text-[#203f37]">{c.content}</p>
            </li>
          ))}
          <li ref={endRef} aria-hidden="true" />
        </ul>
        <form onSubmit={send} className="border-t border-[var(--line)] px-4 pb-[max(12px,env(safe-area-inset-bottom))] pt-3">
          <div className="flex gap-2">
            <input value={text} onChange={(e) => { setText(e.target.value); if (state !== "sending") setState("idle"); }}
              maxLength={600} placeholder={t.commentPlaceholder} aria-label={t.commentPlaceholder}
              className="min-w-0 flex-1 rounded-xl border border-[var(--line)] px-3 py-2.5 text-[15px] outline-none focus:border-[var(--sea)]" />
            <button type="submit" disabled={state === "sending" || !text.trim()} className="rounded-xl bg-[var(--sea)] px-4 font-bold text-white disabled:opacity-50">
              {state === "sending" ? t.sending : t.send}
            </button>
          </div>
          {(state === "invalid" || state === "failed") && (
            <p role="alert" className="mt-1.5 text-xs font-semibold text-[#b3261e]">{state === "invalid" ? t.commentInvalid : t.commentFailed}</p>
          )}
        </form>
      </div>
      {dialog}
    </div>,
    document.body,
  );
}
