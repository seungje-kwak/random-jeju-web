-- Random Jeju merge, part 1 (M1). PRD tasks/prd-random-jeju-merge.md FR-30.
-- Only additions that the running Ktor server (random-jeju-api) does not notice:
-- new nullable columns, a new table, and dropping a duplicate constraint.
-- Safe to run again. Deferred to M7, when Ktor is off:
--   * FR-32 timestamp -> timestamptz (Ktor still writes naive timestamps into these columns)
--   * FR-34 dropping the posts/comments/post_likes policies and the temporary users policies

-- Random points: who drew them and which course came from them
alter table locations add column if not exists user_id uuid references auth.users(id) on delete set null;
alter table locations add column if not exists course_id uuid references courses(id) on delete set null;

-- Courses: owner (anonymous or signed-in user), how it was made, the random point it came from
alter table courses add column if not exists owner_id uuid references auth.users(id) on delete set null;
alter table courses add column if not exists kind text not null default 'pick';
alter table courses add column if not exists origin_location_id integer references locations(location_id) on delete set null;
do $$ begin
  alter table courses add constraint courses_kind_check check (kind in ('pick', 'random'));
exception when duplicate_object then null;
end $$;

-- Korean text (M6)
alter table course_items add column if not exists reason_ko text;
alter table places add column if not exists description_ko text;
alter table places add column if not exists description_ko_status text;
do $$ begin
  alter table places add constraint places_description_ko_status_check
    check (description_ko_status in ('reviewed', 'machine'));
exception when duplicate_object then null;
end $$;

-- Photos: where the location came from (FR-11)
alter table photos add column if not exists location_source text;
do $$ begin
  alter table photos add constraint photos_location_source_check
    check (location_source in ('exif', 'device', 'manual'));
exception when duplicate_object then null;
end $$;

-- Visit check-ins (FR-19 - FR-21)
create table if not exists visits (
  id           bigint generated always as identity primary key,
  user_id      uuid not null references auth.users(id) on delete cascade,
  course_id    uuid not null references courses(id) on delete cascade,
  kind         text not null check (kind in ('random_point', 'course_place')),
  place_id     integer references places(id),
  location_id  integer references locations(location_id),
  post_id      uuid not null references posts(id) on delete cascade,
  created_at   timestamptz not null default now()
);
create unique index if not exists visits_once on visits (course_id, kind, coalesce(place_id, 0));
alter table visits enable row level security;

-- Land-only part of each grid cell (FR-0). Filled by scripts/mark_grids.py in M3.
alter table grids add column if not exists land_cell geometry(Geometry, 4326);

-- post_likes already has primary key (post_id, user_id); this unique constraint repeats it
alter table post_likes drop constraint if exists post_likes_unique_post_user;

-- admin_areas has two identical GiST indexes on geom
drop index if exists idx_admin_geom;

-- Indexes for the new lookups
create index if not exists courses_owner_idx on courses (owner_id, created_at desc);
create index if not exists locations_user_idx on locations (user_id);
create index if not exists visits_post_idx on visits (post_id);
