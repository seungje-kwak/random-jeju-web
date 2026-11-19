-- Random Jeju M7: after the Ktor server (random-jeju-api) stopped serving on 2026-11-19.
-- tasks/prd-random-jeju-merge.md FR-32 (time columns) and FR-34 (no direct-access policies). Safe to run again.
set local statement_timeout = 0;

-- FR-32: columns without a time zone become timestamptz. The DB runs in UTC, so values written by the
-- CURRENT_TIMESTAMP default are UTC; photos.image_time came from EXIF and is Korea time (Q-09: photo 109 was
-- taken 19:02:55 and uploaded 10:03:38, nine hours apart). Each column converts only once.
do $$
declare
  c record;
begin
  for c in
    select * from (values ('locations', 'created_at', 'UTC'), ('photos', 'timestamp', 'UTC'),
                          ('users', 'join_date', 'UTC'), ('photos', 'image_time', 'Asia/Seoul')) v(tbl, col, zone)
  loop
    if exists (select 1 from information_schema.columns
                where table_schema = 'public' and table_name = c.tbl and column_name = c.col
                  and data_type = 'timestamp without time zone') then
      execute format('alter table public.%I alter column %I type timestamptz using %I at time zone %L',
                     c.tbl, c.col, c.col, c.zone);
    end if;
  end loop;
end $$;

-- create_photo_post now takes the capture time with its zone (the backend sends +09:00).
drop function if exists create_photo_post(uuid, text, text, double precision, double precision, timestamp, text, text, post_category);
create or replace function create_photo_post(
  p_user uuid, p_file_path text, p_thumb_path text, p_lat double precision, p_lng double precision,
  p_image_time timestamptz, p_location_source text, p_content text, p_category post_category)
returns table (post_id uuid, photo_id integer)
language plpgsql volatile
set search_path = public, extensions
as $$
declare
  pt geometry := case when p_lat is null or p_lng is null then null
                      else st_setsrid(st_makepoint(p_lng, p_lat), 4326) end;
  new_photo integer;
  new_post uuid;
  cell bigint;
begin
  select g.id into cell from grids g where pt is not null and st_contains(g.cell, pt) limit 1;
  insert into photos (file_path, thumb_path, gps_lat, gps_lng, image_time, user_id, geom, admin_area_id,
                      grid_id, location_source)
  values (p_file_path, p_thumb_path, p_lat, p_lng, p_image_time, p_user, pt,
          (select a.gid from admin_areas a where pt is not null and st_contains(a.geom, pt) limit 1),
          cell, p_location_source)
  returning photos.photo_id into new_photo;
  insert into posts (user_id, photo_id, grid_id, category, content)
  values (p_user, new_photo, cell, p_category, nullif(btrim(p_content), ''))
  returning posts.id into new_post;
  return query select new_post, new_photo;
end;
$$;
revoke execute on function create_photo_post(uuid, text, text, double precision, double precision, timestamptz, text, text, post_category)
  from public, anon, authenticated;
grant execute on function create_photo_post(uuid, text, text, double precision, double precision, timestamptz, text, text, post_category)
  to service_role;

-- FR-34: every write goes through the backend (service role). These let a signed-in browser write straight
-- to the tables, past the backend's checks; only the Android app used them. RLS stays on everywhere.
drop policy if exists "posts are public" on posts;
drop policy if exists "users can create posts" on posts;
drop policy if exists "users can delete own posts" on posts;
drop policy if exists "users can modify own posts" on posts;
drop policy if exists "comments are readable" on comments;
drop policy if exists "users can comment" on comments;
drop policy if exists "users can delete own comments" on comments;
drop policy if exists "likes are readable" on post_likes;
drop policy if exists "users can like" on post_likes;
drop policy if exists "users can unlike" on post_likes;
-- the temporary ones added on 2026-11-19 so the Android sign-up and profile kept working (PRD 8.6)
drop policy if exists "own row read" on users;
drop policy if exists "own row insert" on users;
