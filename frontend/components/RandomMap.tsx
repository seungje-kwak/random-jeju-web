"use client";
// tasks/prd-random-jeju-merge.md US-013: the whole island, and a dice dropped on the drawn point.
// FR-3a: the point's example course on top, as numbered stops joined in visiting order.
// Kakao map when the SDK loads; otherwise the stylized island picture with the dice placed on it.
import { useEffect, useMemo, useRef, useState } from "react";
import { spread } from "@/components/FallbackMap";
import { MAP_CONFIG, toPercent } from "@/config/map";
import { loadKakaoMaps, type KakaoMaps, type KLayer, type KMap } from "@/lib/kakao";
import { ISLAND_MAP_BOUNDS } from "@/lib/landmarks";

const ISLAND_CENTER = { lat: 33.375, lng: 126.55 };
const ISLAND_LEVEL = 11;   // the whole main island on a phone
const POINT_LEVEL = 8;     // a few kilometres around the point
const MOVE_MS = 600;
const STOP_PX = 26;
const FIT_PAD = 44;        // px kept free around the dice and the stops
const DICE_HALF_PX = 17;   // half the dice marker's height (.rj-dice-marker is 34px)

export type MapStop = { order: number; lat: number; lng: number; label: string };

function reducedMotion(): boolean {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
}

function stopMarker(s: MapStop): HTMLElement {
  const el = document.createElement("div");
  el.className = "rj-stop-marker";
  el.textContent = String(s.order);
  el.title = s.label;
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", s.label);
  el.style.cssText = [
    "display:flex", "align-items:center", "justify-content:center",
    `width:${STOP_PX}px`, `height:${STOP_PX}px`, "border-radius:9999px", "border:2px solid #fff",
    "background:#217981", "color:#fff", "font:800 13px/1 system-ui,sans-serif",
    "box-shadow:0 4px 6px rgba(0,0,0,.22)",
  ].join(";");
  return el;
}

export function RandomMap({ point, stops, label, markerLabel }: {
  point: { lat: number; lng: number } | null;
  stops?: MapStop[] | null;
  label: string;
  markerLabel: string;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const mapsRef = useRef<KakaoMaps | null>(null);
  const mapRef = useRef<KMap | null>(null);
  const markerRef = useRef<KLayer | null>(null);
  const stopLayersRef = useRef<KLayer[]>([]);
  const flyUntilRef = useRef(0);   // when the fly to a new dice ends; fitting the course before that is undone
  const [mode, setMode] = useState<"loading" | "kakao" | "fallback">("loading");
  const fallbackBoxRef = useRef<HTMLDivElement>(null);
  const [fallbackWidth, setFallbackWidth] = useState(0);

  // The island picture cannot zoom, so a day's stops a few km apart would sit on top of each other:
  // push them apart for the box's width, as the course page's fallback map does (7.10).
  useEffect(() => {
    const el = fallbackBoxRef.current;
    if (mode !== "fallback" || !el) return;
    setFallbackWidth(el.clientWidth);
    const ro = new ResizeObserver(() => setFallbackWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, [mode]);
  const fallback = useMemo(() => {
    const at = point ? toPercent(point.lat, point.lng, ISLAND_MAP_BOUNDS) : null;
    const dice = at?.inBounds ? at : null;
    const inside = (stops ?? []).map((s) => ({ s, pct: toPercent(s.lat, s.lng, ISLAND_MAP_BOUNDS) })).filter((x) => x.pct.inBounds);
    // the dice stands above its point, so it takes part in the pushing by its middle
    const heightPx = fallbackWidth / MAP_CONFIG.aspectRatio;
    const lift = dice && heightPx ? (DICE_HALF_PX / heightPx) * 100 : 0;
    const pushed = spread([...(dice ? [{ x: dice.x, y: dice.y - lift }] : []), ...inside.map((x) => x.pct)], fallbackWidth);
    const first = dice ? 1 : 0;
    return {
      dice: dice ? { x: pushed[0].x, y: pushed[0].y + lift } : null,
      stops: inside.map((x, i) => ({ s: x.s, pct: pushed[i + first] })),
    };
  }, [point, stops, fallbackWidth]);
  const fallbackStops = fallback.stops;

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
    return () => {
      alive = false;
      markerRef.current?.setMap(null);
      stopLayersRef.current.forEach((l) => l.setMap(null));
    };
  }, []);

  // The dice: dropped on the point, the map flies there.
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
      flyUntilRef.current = Date.now() + MOVE_MS + 80;
    }
  }, [mode, point, markerLabel]);

  // The example course: a dashed line in visiting order, numbered stops, and a view that holds them all.
  useEffect(() => {
    const maps = mapsRef.current;
    const map = mapRef.current;
    if (mode !== "kakao" || !maps || !map) return;
    stopLayersRef.current.forEach((l) => l.setMap(null));
    stopLayersRef.current = [];
    if (!point || !stops?.length) return;
    const ll = (s: { lat: number; lng: number }) => new maps.LatLng(s.lat, s.lng);
    const layers: KLayer[] = [];
    if (stops.length > 1) {
      layers.push(new maps.Polyline({
        map, path: stops.map(ll), strokeWeight: 3, strokeColor: MAP_CONFIG.routeColor, strokeOpacity: 0.9,
        strokeStyle: "shortdash",
      }));
    }
    for (const s of stops) {
      layers.push(new maps.CustomOverlay({ map, position: ll(s), content: stopMarker(s), xAnchor: 0.5, yAnchor: 0.5, zIndex: 4 }));
    }
    stopLayersRef.current = layers;
    const b = new maps.LatLngBounds();
    stops.forEach((s) => b.extend(ll(s)));
    b.extend(ll(point));
    // a little more room on top: the dice stands up from its point
    const fit = () => map.setBounds(b, FIT_PAD + 20, FIT_PAD, FIT_PAD, FIT_PAD);
    const wait = flyUntilRef.current - Date.now();
    if (wait <= 0) {
      fit();
      return;
    }
    const timer = window.setTimeout(fit, wait);
    return () => window.clearTimeout(timer);
  }, [mode, point, stops]);

  return (
    <div className="relative h-full w-full overflow-hidden bg-[#d5eeed]" role="region" aria-label={label}>
      <div ref={boxRef} className="absolute inset-0" style={{ visibility: mode === "kakao" ? "visible" : "hidden" }} />
      {mode === "fallback" && (
        <div className="absolute inset-0 grid place-items-center p-3">
          <div ref={fallbackBoxRef} className="relative w-full max-w-[900px]" style={{ aspectRatio: "10 / 7" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/map/jeju-island-fallback.svg" alt="" className="absolute inset-0 h-full w-full" draggable={false} />
            {fallbackStops.length > 1 && (
              <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                <polyline points={fallbackStops.map((x) => `${x.pct.x},${x.pct.y}`).join(" ")} fill="none"
                  stroke={MAP_CONFIG.routeColor} strokeWidth={2.5} strokeDasharray="5 4" vectorEffect="non-scaling-stroke" />
              </svg>
            )}
            {fallbackStops.map(({ s, pct }) => (
              <span key={s.order} className="absolute grid -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 border-white bg-[#217981] text-xs font-extrabold text-white shadow"
                style={{ left: `${pct.x}%`, top: `${pct.y}%`, width: STOP_PX, height: STOP_PX }} role="img" aria-label={s.label} title={s.label}>
                {s.order}
              </span>
            ))}
            {fallback.dice && (
              <span key={`${point!.lat},${point!.lng}`} className="rj-dice-marker absolute -translate-x-1/2 -translate-y-full"
                style={{ left: `${fallback.dice.x}%`, top: `${fallback.dice.y}%` }} role="img" aria-label={markerLabel}>🎲</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
