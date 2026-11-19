"use client";
// tasks/prd-random-jeju-merge.md US-013: the whole island, and a dice dropped on the drawn point.
// Kakao map when the SDK loads; otherwise the stylized island picture with the dice placed on it.
import { useEffect, useRef, useState } from "react";
import { toPercent } from "@/config/map";
import { loadKakaoMaps, type KakaoMaps, type KLayer, type KMap } from "@/lib/kakao";
import { ISLAND_MAP_BOUNDS } from "@/lib/landmarks";

const ISLAND_CENTER = { lat: 33.375, lng: 126.55 };
const ISLAND_LEVEL = 11;   // the whole main island on a phone
const POINT_LEVEL = 8;     // a few kilometres around the point
const MOVE_MS = 600;

function reducedMotion(): boolean {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
}

export function RandomMap({ point, label, markerLabel }: {
  point: { lat: number; lng: number } | null;
  label: string;
  markerLabel: string;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const mapsRef = useRef<KakaoMaps | null>(null);
  const mapRef = useRef<KMap | null>(null);
  const markerRef = useRef<KLayer | null>(null);
  const [mode, setMode] = useState<"loading" | "kakao" | "fallback">("loading");

  useEffect(() => {
    let alive = true;
    loadKakaoMaps()
      .then((maps) => {
        if (!alive || !boxRef.current) return;
        mapsRef.current = maps;
        mapRef.current = new maps.Map(boxRef.current, {
          center: new maps.LatLng(ISLAND_CENTER.lat, ISLAND_CENTER.lng), level: ISLAND_LEVEL,
        });
        setMode("kakao");
      })
      .catch(() => { if (alive) setMode("fallback"); });
    return () => { alive = false; markerRef.current?.setMap(null); };
  }, []);

  useEffect(() => {
    const maps = mapsRef.current;
    const map = mapRef.current;
    if (mode !== "kakao" || !maps || !map) return;
    markerRef.current?.setMap(null);
    markerRef.current = null;
    if (!point) return;
    const pos = new maps.LatLng(point.lat, point.lng);
    const el = document.createElement("div");
    el.className = "rj-dice-marker";
    el.textContent = "🎲";
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", markerLabel);
    markerRef.current = new maps.CustomOverlay({ position: pos, content: el, yAnchor: 1, zIndex: 5, map });
    if (reducedMotion()) {
      map.setLevel(POINT_LEVEL);
      map.setCenter(pos);
    } else {
      map.setLevel(POINT_LEVEL, { animate: { duration: MOVE_MS }, anchor: pos });
      map.panTo(pos);
    }
  }, [mode, point, markerLabel]);

  const fallbackPt = point ? toPercent(point.lat, point.lng, ISLAND_MAP_BOUNDS) : null;
  return (
    <div className="relative h-full w-full overflow-hidden bg-[#d5eeed]" role="region" aria-label={label}>
      <div ref={boxRef} className="absolute inset-0" style={{ visibility: mode === "kakao" ? "visible" : "hidden" }} />
      {mode === "fallback" && (
        <div className="absolute inset-0 grid place-items-center p-3">
          <div className="relative w-full max-w-[900px]" style={{ aspectRatio: "10 / 7" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/map/jeju-island-fallback.svg" alt="" className="absolute inset-0 h-full w-full" draggable={false} />
            {fallbackPt?.inBounds && (
              <span key={`${point!.lat},${point!.lng}`} className="rj-dice-marker absolute -translate-x-1/2 -translate-y-full"
                style={{ left: `${fallbackPt.x}%`, top: `${fallbackPt.y}%` }} role="img" aria-label={markerLabel}>🎲</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
