"use client";
// tasks/prd-random-jeju-merge.md US-023: other travelers' photos on the Kakao map. Wide views group them by
// eup/myeon/dong (FR-15); close views show each photo (FR-14). Positions are rounded to about 100 m (FR-13a).
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { PostCard } from "@/components/PostCard";
import { TabBar } from "@/components/TabBar";
import { V9Header } from "@/components/V9Header";
import { MAP_CONFIG } from "@/config/map";
import { api } from "@/lib/api";
import { MESSAGES, useLocale } from "@/lib/i18n";
import { loadKakaoMaps, type KakaoMaps, type KLayer, type KMap } from "@/lib/kakao";
import type { PhotoCluster, PhotoMarker, Post } from "@/lib/types";

const ISLAND_CENTER = { lat: 33.375, lng: 126.55 };
const ISLAND_LEVEL = 10;
const IDLE_DEBOUNCE_MS = 300;

function clusterEl(c: PhotoCluster, label: string, onClick: () => void): HTMLElement {
  const b = document.createElement("button");
  b.type = "button";
  b.setAttribute("aria-label", label);
  b.title = label;
  b.style.cssText = "display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;background:none;border:0;padding:0";
  const ring = document.createElement("span");
  ring.style.cssText = "position:relative;width:56px;height:56px;border-radius:50%;border:3px solid #fff;box-shadow:0 4px 14px rgba(20,49,54,.35);background:#d5eeed center/cover no-repeat";
  if (c.thumb_url) ring.style.backgroundImage = `url("${c.thumb_url.replace(/"/g, "%22")}")`;
  const count = document.createElement("span");
  count.textContent = `+${c.count}`;
  count.style.cssText = "position:absolute;right:-8px;top:-6px;min-width:24px;padding:2px 6px;border-radius:12px;background:#176d62;color:#fff;font:700 11px/16px system-ui";
  ring.append(count);
  const name = document.createElement("span");
  name.textContent = c.name;
  name.style.cssText = "padding:1px 7px;border-radius:8px;background:rgba(255,255,255,.92);color:#143136;font:700 11px/16px system-ui";
  b.append(ring, name);
  b.addEventListener("click", onClick);
  return b;
}

function photoEl(p: PhotoMarker, label: string, onClick: () => void): HTMLElement {
  const b = document.createElement("button");
  b.type = "button";
  b.setAttribute("aria-label", label);
  b.style.cssText = "position:relative;width:52px;height:52px;padding:3px;border:0;border-radius:12px;background:#fff;box-shadow:0 4px 12px rgba(20,49,54,.35);cursor:pointer";
  const img = document.createElement("img");
  img.alt = "";
  img.loading = "lazy";
  if (p.thumb_url) img.src = p.thumb_url;
  img.style.cssText = "width:46px;height:46px;border-radius:9px;object-fit:cover;display:block;background:#d5eeed";
  const tail = document.createElement("span");
  tail.style.cssText = "position:absolute;left:50%;bottom:-7px;margin-left:-7px;border:7px solid transparent;border-top-color:#fff;border-bottom:0";
  b.append(img, tail);
  b.addEventListener("click", onClick);
  return b;
}

export default function PhotoMapPage() {
  const { locale } = useLocale();
  const t = MESSAGES[locale].social;
  const boxRef = useRef<HTMLDivElement>(null);
  const mapsRef = useRef<KakaoMaps | null>(null);
  const mapRef = useRef<KMap | null>(null);
  const shown = useRef(new Map<string, KLayer>());     // key -> overlay, so only changes are drawn
  const meRef = useRef<KLayer | null>(null);
  const [mode, setMode] = useState<"loading" | "ready" | "failed">("loading");
  const [loadError, setLoadError] = useState(false);
  const [locError, setLocError] = useState(false);
  const [open, setOpen] = useState<{ id: string; post: Post | null; failed: boolean } | null>(null);
  const request = useRef(0);
  const markersUpTo = useRef<number | null>(null);    // after a cluster tap: single photos up to this level
  const labelRef = useRef(t);
  labelRef.current = t;

  const openPost = useCallback((id: string) => {
    setOpen({ id, post: null, failed: false });
    api.post(id).then((post) => setOpen((o) => (o?.id === id ? { id, post, failed: false } : o)))
      .catch(() => setOpen((o) => (o?.id === id ? { id, post: null, failed: true } : o)));
  }, []);

  const refresh = useCallback(async () => {
    const maps = mapsRef.current;
    const map = mapRef.current;
    if (!maps || !map) return;
    const b = map.getBounds();
    const sw = b.getSouthWest();
    const ne = b.getNorthEast();
    const box = { min_lat: sw.getLat(), min_lng: sw.getLng(), max_lat: ne.getLat(), max_lng: ne.getLng() };
    const level = map.getLevel();
    if (markersUpTo.current !== null && level > markersUpTo.current) markersUpTo.current = null;   // zoomed out again
    const clustered = level >= MAP_CONFIG.clusterMinLevel && markersUpTo.current === null;
    const n = ++request.current;
    try {
      const next = new Map<string, () => KLayer>();
      if (clustered) {
        for (const c of (await api.photoClusters(box)).clusters) {
          next.set(`c${c.admin_area_id}:${c.count}`, () => new maps.CustomOverlay({
            position: new maps.LatLng(c.lat, c.lng), yAnchor: 0.6, zIndex: 3, clickable: true,
            content: clusterEl(c, labelRef.current.clusterLabel(c.name, c.count), () => {
              // zoom to where the cluster's photos are (its average point can have none of them nearby),
              // but always closer than the cluster level so the photos show one by one
              const b = new maps.LatLngBounds();
              b.extend(new maps.LatLng(c.extent.south, c.extent.west));
              b.extend(new maps.LatLng(c.extent.north, c.extent.east));
              map.setBounds(b, 70, 40, 90, 40);
              // the fitted view may still be a "cluster" level; show single photos there anyway, until the
              // traveler zooms out past it (otherwise the same cluster would come straight back)
              markersUpTo.current = Math.max(map.getLevel(), MAP_CONFIG.clusterMinLevel - 1);
            }),
          }));
        }
      } else {
        for (const p of (await api.photoMap(box)).photos) {
          next.set(`p${p.photo_id}`, () => new maps.CustomOverlay({
            position: new maps.LatLng(p.lat, p.lng), yAnchor: 1.15, zIndex: 4, clickable: true,
            content: photoEl(p, labelRef.current.openPost, () => openPost(p.post_id)),
          }));
        }
      }
      if (n !== request.current) return;          // a newer move already asked again
      shown.current.forEach((layer, key) => { if (!next.has(key)) { layer.setMap(null); shown.current.delete(key); } });
      next.forEach((make, key) => {
        if (shown.current.has(key)) return;
        const layer = make();
        layer.setMap(map);
        shown.current.set(key, layer);
      });
      setLoadError(false);
    } catch {
      if (n === request.current) setLoadError(true);
    }
  }, [openPost]);

  useEffect(() => {
    let alive = true;
    let timer = 0;
    const onIdle = () => { window.clearTimeout(timer); timer = window.setTimeout(refresh, IDLE_DEBOUNCE_MS); };
    const overlays = shown.current;
    loadKakaoMaps()
      .then((maps) => {
        if (!alive || !boxRef.current) return;
        mapsRef.current = maps;
        const map = new maps.Map(boxRef.current, { center: new maps.LatLng(ISLAND_CENTER.lat, ISLAND_CENTER.lng), level: ISLAND_LEVEL });
        mapRef.current = map;
        maps.event?.addListener(map, "idle", onIdle);
        setMode("ready");
        refresh();
      })
      .catch(() => { if (alive) setMode("failed"); });
    return () => {
      alive = false;
      window.clearTimeout(timer);
      if (mapRef.current) mapsRef.current?.event?.removeListener(mapRef.current, "idle", onIdle);
      overlays.forEach((l) => l.setMap(null));
      overlays.clear();
      meRef.current?.setMap(null);
    };
  }, [refresh]);

  function locateMe() {
    const maps = mapsRef.current;
    const map = mapRef.current;
    if (!maps || !map || !navigator.geolocation) { setLocError(true); return; }
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      const pos = new maps.LatLng(coords.latitude, coords.longitude);
      meRef.current?.setMap(null);
      const dot = document.createElement("div");
      dot.className = "map-user-location";
      dot.textContent = "●";
      meRef.current = new maps.CustomOverlay({ position: pos, content: dot, zIndex: 8, map });
      map.setLevel(5);
      map.setCenter(pos);
      setLocError(false);
    }, () => setLocError(true), { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 });
  }

  return (
    <main className="v9-site flex h-[100dvh] flex-col">
      <V9Header />
      <TabBar />
      <div className="relative flex-1 pb-[64px] lg:pb-0">
        <div ref={boxRef} className="absolute inset-0 bottom-[64px] lg:bottom-0" style={{ visibility: mode === "ready" ? "visible" : "hidden" }}
          role="region" aria-label={t.mapTitle} />
        <div className="pointer-events-none absolute inset-x-3 top-3 z-10 flex items-start justify-between gap-2">
          <div className="pointer-events-auto max-w-[320px] rounded-2xl bg-white/95 px-4 py-3 shadow">
            <h1 className="text-base font-extrabold text-[#143136]">{t.mapTitle}</h1>
            <p className="mt-0.5 text-xs leading-relaxed text-[var(--muted)]">{t.mapHint}</p>
          </div>
          {mode === "ready" && (
            <button type="button" onClick={locateMe} className="pointer-events-auto shrink-0 rounded-2xl bg-white/95 px-3 py-2.5 text-sm font-bold text-[#143136] shadow">
              ⌖ {t.myLocation}
            </button>
          )}
        </div>
        {(loadError || locError) && (
          <p role="alert" className="absolute inset-x-3 bottom-[80px] z-10 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-[#b3261e] shadow lg:bottom-4">
            {locError ? t.locationDenied : t.loadFailed}
          </p>
        )}
        {mode === "failed" && (
          <div className="absolute inset-0 grid place-items-center p-6 text-center">
            <div>
              <p className="font-bold text-[#143136]">{t.mapFailed}</p>
              <Link href="/feed" className="v9-outline mt-4 inline-flex">{t.feedTitle}</Link>
            </div>
          </div>
        )}
      </div>
      {open && createPortal(
        <div role="dialog" aria-modal="true" aria-label={t.openPost} className="fixed inset-0 z-[800] flex items-end justify-center bg-black/40 sm:items-center"
          onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(null); }}>
          <div className="max-h-[88dvh] w-full max-w-[520px] overflow-y-auto rounded-t-[24px] bg-[#fffefa] p-3 sm:rounded-[24px]">
            <div className="mb-2 flex justify-end">
              <button type="button" onClick={() => setOpen(null)} className="h-9 w-9 rounded-full bg-[#f2f5f2]" aria-label={t.close}>✕</button>
            </div>
            {open.post ? (
              <PostCard post={open.post} onChange={(p) => setOpen((o) => (o ? { ...o, post: p } : o))} priority />
            ) : open.failed ? (
              <p role="alert" className="p-6 text-center text-sm text-[#b3261e]">{t.loadFailed}</p>
            ) : (
              <div className="skeleton aspect-square rounded-[20px]" aria-busy="true" />
            )}
          </div>
        </div>,
        document.body,
      )}
    </main>
  );
}
