"use client";
// tasks/prd-random-jeju-merge.md US-021: a small Kakao map that shows where a photo will be pinned, and, while
// `picking`, sets the spot from a tap. Without the SDK it says so and nothing can be picked.
import { useEffect, useRef, useState } from "react";
import { loadKakaoMaps, type KakaoMaps, type KLayer, type KMap, type KMouseEvent } from "@/lib/kakao";

const ISLAND_CENTER = { lat: 33.375, lng: 126.55 };

export function PickMap({ point, picking, onPick, label, failedText }: {
  point: { lat: number; lng: number } | null;
  picking: boolean;
  onPick: (lat: number, lng: number) => void;
  label: string;
  failedText: string;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const mapsRef = useRef<KakaoMaps | null>(null);
  const mapRef = useRef<KMap | null>(null);
  const pinRef = useRef<KLayer | null>(null);
  const pickRef = useRef({ picking, onPick });
  pickRef.current = { picking, onPick };
  const [mode, setMode] = useState<"loading" | "ready" | "failed">("loading");

  useEffect(() => {
    let alive = true;
    const onClick = (e?: KMouseEvent) => {
      if (e && pickRef.current.picking) pickRef.current.onPick(e.latLng.getLat(), e.latLng.getLng());
    };
    loadKakaoMaps()
      .then((maps) => {
        if (!alive || !boxRef.current) return;
        mapsRef.current = maps;
        mapRef.current = new maps.Map(boxRef.current, { center: new maps.LatLng(ISLAND_CENTER.lat, ISLAND_CENTER.lng), level: 11 });
        maps.event?.addListener(mapRef.current, "click", onClick);
        setMode("ready");
      })
      .catch(() => { if (alive) setMode("failed"); });
    return () => {
      alive = false;
      if (mapRef.current) mapsRef.current?.event?.removeListener(mapRef.current, "click", onClick);
      pinRef.current?.setMap(null);
    };
  }, []);

  useEffect(() => {
    const maps = mapsRef.current;
    const map = mapRef.current;
    if (mode !== "ready" || !maps || !map) return;
    pinRef.current?.setMap(null);
    pinRef.current = null;
    if (!point) return;
    const pos = new maps.LatLng(point.lat, point.lng);
    const pin = document.createElement("div");
    pin.textContent = "📍";
    pin.style.cssText = "font-size:30px;line-height:1;filter:drop-shadow(0 3px 4px rgba(0,0,0,.3))";
    pinRef.current = new maps.CustomOverlay({ position: pos, content: pin, yAnchor: 1, zIndex: 5, map });
    if (map.getLevel() > 8) map.setLevel(7);
    map.panTo(pos);
  }, [mode, point]);

  return (
    <div className={`relative h-[220px] overflow-hidden rounded-2xl border ${picking ? "border-[var(--sea)] ring-2 ring-[var(--sea)]/30" : "border-[var(--line)]"} bg-[#d5eeed]`}
      role="region" aria-label={label}>
      <div ref={boxRef} className="absolute inset-0" style={{ visibility: mode === "ready" ? "visible" : "hidden", cursor: picking ? "crosshair" : undefined }} />
      {mode === "failed" && <p className="absolute inset-0 grid place-items-center p-4 text-center text-sm text-[var(--muted)]">{failedText}</p>}
    </div>
  );
}
