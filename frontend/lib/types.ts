// PRD 9.3 — keep field names identical to the API.
export type Category = "nature" | "market" | "cafe" | "food" | "culture" | "photo";
export type Tier = "free" | "premium";
export type MoveMethod = "walk" | "bus" | "taxi";
export type ItemStatus = "done" | "current" | "upcoming";
export type ReplanReason = "rain" | "closed" | "hungry" | "tired";

export type Accessibility = {
  walking_level: 1 | 2 | 3;
  terrain: "flat" | "slope" | "steep";
  has_stairs: boolean | null;
  wheelchair_ok: boolean | null;
  indoor: boolean;
  has_seating: boolean | null;
  restroom: boolean | null;
  nearest_public_restroom_m: number | null;
  fatigue_score: 1 | 2 | 3 | 4 | 5;
};

// true / false / null (not known). Badges show only for true.
export type FoodOptions = {
  solo_ok: boolean | null;
  vegan: boolean | null;
  vegetarian: boolean | null;
  halal: boolean | null;
  english_menu: boolean | null;
  signature_menu_en: string | null;
  allergens: string | null;
};

export type PhraseCard = { situation: string; text_en: string; text_ko: string };

export type Place = {
  id: number;
  source_poi_id: string | null;
  name_en: string;
  name_ko: string;
  category: Category;
  place_type: string | null; // stay-time type (oreum_hike, port, cafe, ...). Not shown on screen
  description_en: string;
  lat: number;
  lng: number;
  address_ko: string;
  area_id: string;
  image_url: string | null;
  image_source: string | null;
  avg_stay_min: number;
  opening_hours: string | null;
  open_time: string | null; // "HH:MM"; both null = always open
  close_time: string | null; // "HH:MM" or "24:00"
  closed_days: string[];
  price_level: number | null;
  last_verified_at: string | null;
  source_date: string | null;
  accessibility: Accessibility;
  food_options: FoodOptions | null;
};

// One of the 14 areas a traveler can pick (GET /areas).
export type Area = {
  id: string;
  group: "jeju" | "seogwipo";
  name_en: string;
  name_ko: string;
  description_en: string;
  center_lat: number;
  center_lng: number;
  place_count: number;
  selectable: boolean; // false while the area does not have enough places yet
};

// Courses saved before areas existed have no area_id; they are Jeju City courses.
export const DEFAULT_AREA_ID = "jeju-city";

export type UserProfileInput = {
  interests: Category[];
  fitness_level: 1 | 2 | 3;
  max_walk_min: 10 | 20 | 30;
  avoid_slopes: boolean;
  condition_today: "great" | "normal" | "tired";
  diet: "none" | "vegan" | "vegetarian" | "halal";
};

// The server adds conditions, start_time, end_time and area_id. Courses saved before the trip-time
// change have `duration` instead of the two times.
export type UserProfile = UserProfileInput & {
  conditions: { indoor_only: boolean; low_walking: boolean };
  area_id?: string;
  start_time?: string;
  end_time?: string;
  duration?: "half_day" | "full_day";
};

export type CourseItem = {
  order: number;
  place_id: number;
  start_time: string;
  stay_min: number;
  move_method: MoveMethod | null;
  move_min: number | null;
  reason_en: string;
  is_rest_stop: boolean;
  status: ItemStatus;
  place: Place;
  phrase_cards: PhraseCard[];
};

// A meal time we kept free because no restaurant fits (prd-recommendation-p1 FR-11). Not a stop:
// no place, no map marker, no move.
export type MealGap = {
  meal: "lunch" | "dinner";
  start_time: string; // "HH:MM"
  end_time: string;
  reason: "no_diet_match" | "none_nearby";
  message_en: string;
};

export type Course = {
  id: string;
  tier: Tier;
  created_at: string;
  user_profile: UserProfile;
  total_items: number;
  locked_count: number;
  items: CourseItem[];
  meal_gaps: MealGap[]; // in start_time order; a free plan only gets the ones among its visible stops
  // tasks/prd-random-jeju-merge.md FR-10
  kind: "pick" | "random";
  random_origin: RandomOrigin | null;
  visits: Visit[];
};

export type RandomOrigin = {
  location_id: number;
  lat: number;
  lng: number;
  adm_nm: string | null;       // eup / myeon / dong, e.g. "애월읍"
  area_id: string | null;      // the area the course is in (the hub's area, FR-4)
  snap_km: number | null;      // random point -> hub centre, straight line
  hub_place_id: number | null;
  hub_name_ko: string | null;
  hub_name_en: string | null;
};

export type Visit = {               // M5 check-ins; always empty before then
  kind: "random_point" | "course_place";
  place_id: number | null;
  post_id: string;
  thumb_url: string | null;
};

// POST /random-points (FR-3)
export type RandomPoint = {
  location_id: number;
  lat: number;
  lng: number;
  adm_nm: string | null;
  area_id: string | null;
  nearest_hub: { place_id: number; name_ko: string; name_en: string; km: number } | null;
  preview_places: { id: number; name_ko: string; name_en: string; category: Category; image_url: string | null; km: number }[];
};

// tasks/prd-random-jeju-merge.md FR-35
export type Me = {
  user_id: string;
  nickname: string | null; // null until the traveler picks one
  is_anonymous: boolean;
};

// tasks/prd-random-jeju-merge.md FR-11 - FR-18. The values are the DB enum post_category (Korean).
export type PostCategory = "맛집" | "카페" | "쇼핑" | "관광" | "문화" | "스포츠";
export const POST_CATEGORIES: readonly PostCategory[] = ["관광", "맛집", "카페", "쇼핑", "문화", "스포츠"];

export type Author = { nickname: string | null; tag: string | null };

export type Post = {
  post_id: string;
  author: Author;
  is_mine: boolean;
  created_at: string;
  content: string | null;
  category: PostCategory;
  image_url: string | null;
  thumb_url: string | null;
  lat: number | null;            // rounded to about 100 m by the server (FR-13a)
  lng: number | null;
  like_count: number;
  comment_count: number;
  is_liked: boolean;
  // US-031 badge: the post's check-in (the random point first)
  visit: null | { kind: "random_point" | "course_place"; place_name_ko: string | null; place_name_en: string | null };
};

export type FeedPage = { posts: Post[]; next_cursor: string | null };

/** POST /posts: what the photo checked in (FR-20). is_new false = that spot was already checked in. */
export type CheckIn = {
  kind: "random_point" | "course_place"; course_id: string; place_id: number | null;
  place_name_ko: string | null; place_name_en: string | null; is_new: boolean;
};

export type Comment = { id: string; author: Author; is_mine: boolean; content: string; created_at: string };

export type PhotoMarker = { photo_id: number; post_id: string; lat: number; lng: number; thumb_url: string | null };
export type PhotoCluster = {
  admin_area_id: number; name: string; count: number; lat: number; lng: number; thumb_url: string | null;
  extent: { south: number; west: number; north: number; east: number };   // where its photos are
};

export type LocationSource = "exif" | "device" | "manual";
export type PostMeta = {
  category: PostCategory;
  content?: string;
  lat?: number;
  lng?: number;
  location_source?: LocationSource;
  taken_at?: string;             // ISO; with an offset when known
  course_id?: string;
};
