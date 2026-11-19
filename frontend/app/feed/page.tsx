"use client";
// tasks/prd-random-jeju-merge.md US-025: everyone's Jeju photos, newest first, by category, 20 at a time.
// Readable without signing in (Android showed an empty board when logged out).
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { PostCard } from "@/components/PostCard";
import { TabBar, TabBarSpacer } from "@/components/TabBar";
import { V9Header } from "@/components/V9Header";
import { api } from "@/lib/api";
import { MESSAGES, useLocale } from "@/lib/i18n";
import { POST_CATEGORIES, type Post, type PostCategory } from "@/lib/types";

type Load = "idle" | "loading" | "error";

function categoryFromUrl(): PostCategory | null {
  try {
    const c = new URLSearchParams(window.location.search).get("category");
    return POST_CATEGORIES.includes(c as PostCategory) ? (c as PostCategory) : null;
  } catch {
    return null;
  }
}

export default function FeedPage() {
  const t = MESSAGES[useLocale().locale].social;
  const [category, setCategory] = useState<PostCategory | null | undefined>(undefined);   // undefined: URL not read yet
  const [posts, setPosts] = useState<Post[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [load, setLoad] = useState<Load>("idle");
  const [posted, setPosted] = useState<"" | "posted" | "checkedIn">("");
  const generation = useRef(0);
  const sentinel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCategory(categoryFromUrl());
    try {
      const q = new URLSearchParams(window.location.search);
      setPosted(q.has("checkin") ? "checkedIn" : q.has("posted") ? "posted" : "");
    } catch { /* no toast */ }
  }, []);

  const loadMore = useCallback(async (reset = false) => {
    if (category === undefined) return;
    const gen = reset ? ++generation.current : generation.current;
    setLoad("loading");
    try {
      const page = await api.feed(category, reset ? null : cursor);
      if (gen !== generation.current) return;            // the category changed while this page was loading
      setPosts((prev) => (reset ? page.posts : [...prev, ...page.posts.filter((p) => !prev.some((q) => q.post_id === p.post_id))]));
      setCursor(page.next_cursor);
      setDone(page.next_cursor === null);
      setLoad("idle");
    } catch {
      if (gen === generation.current) setLoad("error");
    }
  }, [category, cursor]);

  // a new category starts over (and is kept in the URL so a reload or a shared link keeps it)
  useEffect(() => {
    if (category === undefined) return;
    setPosts([]);
    setCursor(null);
    setDone(false);
    loadMore(true);
    try {
      const url = new URL(window.location.href);
      if (category) url.searchParams.set("category", category); else url.searchParams.delete("category");
      url.searchParams.delete("posted");
      url.searchParams.delete("checkin");
      window.history.replaceState(null, "", url.toString());
    } catch { /* URL stays as it was */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category]);

  // the next 20 when the end of the list scrolls into view
  useEffect(() => {
    const el = sentinel.current;
    if (!el || done || load !== "idle" || posts.length === 0) return;
    const io = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) loadMore(); }, { rootMargin: "600px" });
    io.observe(el);
    return () => io.disconnect();
  }, [done, load, posts.length, loadMore]);

  const update = (next: Post) => setPosts((prev) => prev.map((p) => (p.post_id === next.post_id ? next : p)));
  const chip = (value: PostCategory | null, label: string) => (
    <button key={label} type="button" onClick={() => setCategory(value)} aria-pressed={category === value}
      className={`shrink-0 rounded-full border px-4 py-2 text-sm font-bold ${category === value ? "border-[var(--sea)] bg-[var(--sea)] text-white" : "border-[var(--line)] bg-white text-[#143136]"}`}>
      {label}
    </button>
  );

  return (
    <main className="v9-site min-h-[100dvh]">
      <V9Header />
      <TabBar />
      <div className="mx-auto max-w-[620px] px-4 pt-5">
        <h1 className="text-2xl font-extrabold text-[#143136]">{t.feedTitle}</h1>
        {posted && (
          <p role="status" className="mt-3 rounded-xl bg-[#eff7f3] px-4 py-3 text-sm font-bold text-[#1f5a52]">
            {posted === "checkedIn" ? `🎲 ${t.checkedIn}` : `✓ ${t.posted}`}
          </p>
        )}
        <div className="-mx-4 mt-4 flex gap-2 overflow-x-auto px-4 pb-1" role="group" aria-label={t.category}>
          {chip(null, t.all)}
          {POST_CATEGORIES.map((c) => chip(c, t.categories[c]))}
        </div>

        <div className="mt-4 grid gap-4">
          {posts.map((p, i) => <PostCard key={p.post_id} post={p} onChange={update} priority={i < 2} />)}
        </div>

        {load === "loading" && posts.length === 0 && (
          <div className="mt-4 grid gap-4" aria-busy="true">
            {[0, 1].map((i) => <div key={i} className="skeleton aspect-square rounded-[20px]" />)}
          </div>
        )}
        {load === "error" && (
          <div role="alert" className="mt-6 text-center">
            <p className="text-sm text-[#b3261e]">{t.loadFailed}</p>
            <button type="button" onClick={() => loadMore(posts.length === 0)} className="v9-outline mt-3">{t.retry}</button>
          </div>
        )}
        {load === "idle" && done && posts.length === 0 && (
          <div className="mt-10 text-center">
            <p className="text-[15px] text-[var(--muted)]">{t.empty}</p>
            <Link href="/upload" className="v9-primary mt-4 inline-flex">{t.emptyCta}</Link>
          </div>
        )}
        {done && posts.length > 0 && <p className="py-8 text-center text-sm text-[var(--muted)]">{t.end}</p>}
        <div ref={sentinel} aria-hidden="true" className="h-4" />
        <TabBarSpacer />
      </div>
    </main>
  );
}
