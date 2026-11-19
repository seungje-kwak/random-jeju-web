// The frontend only talks to FastAPI (1.3). Base URL comes from NEXT_PUBLIC_API_URL.
import { accessToken, existingToken, refreshedToken } from "./auth";
import type {
  Area, CheckIn, Comment, Course, FeedPage, Me, Place, PhotoCluster, PhotoMarker, Post, PostCategory, PostMeta, RandomPoint,
  ReplanReason, UserProfileInput,
} from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TIMEOUT_MS = 45_000; // 11.1

export class ApiError extends Error {
  status: number;
  code: string | null;
  constructor(status: number, code: string | null, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      // FormData (photo upload) sets its own multipart Content-Type with the boundary
      headers: { ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...(init?.headers || {}) },
      signal: ctrl.signal,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, null, "Network error");
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let code: string | null = null;
    let message = res.statusText;
    try {
      const body = await res.json();
      // 9.2: branch on detail.code only when it is a string (422 has an array)
      if (body?.detail && typeof body.detail.code === "string") {
        code = body.detail.code;
        message = body.detail.message;
      }
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, code, message);
  }
  return res.json() as Promise<T>;
}

/** For reads anyone may do: adds the token only when a session already exists (is_liked, is_mine). */
async function readRequest<T>(path: string): Promise<T> {
  const token = await existingToken();
  try {
    return await request<T>(path, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined);
  } catch (e) {
    // an expired session must not block reading: ask again without it
    if (token && e instanceof ApiError && e.status === 401) return request<T>(path);
    throw e;
  }
}

type Box = { min_lat: number; min_lng: number; max_lat: number; max_lng: number };
const boxQuery = (b: Box) =>
  `min_lat=${b.min_lat}&min_lng=${b.min_lng}&max_lat=${b.max_lat}&max_lng=${b.max_lng}`;

/** For endpoints that need the traveler (US-004): sends the Supabase access token, retries once after a 401. */
async function authedRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const send = (token: string) =>
    request<T>(path, { ...init, headers: { ...(init?.headers || {}), Authorization: `Bearer ${token}` } });
  try {
    return await send(await accessToken());
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return send(await refreshedToken());
    throw e;
  }
}

export const api = {
  areas: () => request<{ areas: Area[] }>("/areas"),
  // With area_id: only that area's places (the course map). Without: every place in Jeju.
  places: (area_id?: string) =>
    request<{ places: Place[] }>(area_id ? `/places?area_id=${encodeURIComponent(area_id)}` : "/places"),
  createCourse: (user_profile: UserProfileInput, area_id: string, start_time: string, end_time: string) =>
    request<Course>("/courses", {
      method: "POST",
      body: JSON.stringify({ user_profile, area_id, start_time, end_time }),
    }),
  getCourse: (id: string) => request<Course>(`/courses/${encodeURIComponent(id)}`),
  replan: (id: string, reason: ReplanReason, current_order: number) =>
    request<Course>(`/courses/${encodeURIComponent(id)}/replan`, {
      method: "POST",
      body: JSON.stringify({ reason, current_order }),
    }),
  // prd-recommendation-p1 US-P15: a new course with the same choices (201). The old course stays.
  shuffleCourse: (id: string) =>
    request<Course>(`/courses/${encodeURIComponent(id)}/shuffle`, { method: "POST" }),
  purchase: (course_id: string) =>
    request<Course>("/purchase", { method: "POST", body: JSON.stringify({ course_id }) }),
  // tasks/prd-random-jeju-merge.md FR-3, FR-9: rolling the dice is the first action that needs a guest session
  drawPoint: () => authedRequest<RandomPoint>("/random-points", { method: "POST" }),
  createRandomCourse: (location_id: number, user_profile: UserProfileInput, start_time: string, end_time: string) =>
    authedRequest<Course>("/random-courses", {
      method: "POST",
      body: JSON.stringify({ location_id, user_profile, start_time, end_time }),
    }),
  // tasks/prd-random-jeju-merge.md FR-11 - FR-18: photo posts, feed, likes, comments, photo map
  feed: (category?: PostCategory | null, cursor?: string | null) => {
    const q = new URLSearchParams();
    if (category) q.set("category", category);
    if (cursor) q.set("cursor", cursor);
    const s = q.toString();
    return readRequest<FeedPage>(`/posts${s ? `?${s}` : ""}`);
  },
  post: (id: string) => readRequest<Post>(`/posts/${encodeURIComponent(id)}`),
  createPost: (image: Blob, meta: PostMeta) => {
    const form = new FormData();
    form.append("image", image, "photo.jpg");
    form.append("meta", JSON.stringify(meta));
    return authedRequest<{ post: Post; visit: CheckIn | null; visits: CheckIn[] }>("/posts", { method: "POST", body: form });
  },
  like: (id: string) =>
    authedRequest<{ liked: boolean; like_count: number }>(`/posts/${encodeURIComponent(id)}/like`, { method: "POST" }),
  comments: (id: string) => readRequest<{ comments: Comment[] }>(`/posts/${encodeURIComponent(id)}/comments`),
  addComment: (id: string, content: string) =>
    authedRequest<Comment>(`/posts/${encodeURIComponent(id)}/comments`, { method: "POST", body: JSON.stringify({ content }) }),
  photoMap: (b: Box) => request<{ photos: PhotoMarker[] }>(`/photos/map?${boxQuery(b)}`),
  photoClusters: (b: Box) => request<{ clusters: PhotoCluster[] }>(`/photos/clusters?${boxQuery(b)}`),
  // tasks/prd-random-jeju-merge.md FR-35
  me: () => authedRequest<Me>("/me"),
  saveNickname: (nickname: string) =>
    authedRequest<Me>("/me", { method: "POST", body: JSON.stringify({ nickname }) }),
};
