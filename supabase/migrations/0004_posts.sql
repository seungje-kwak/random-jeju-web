-- Random Jeju M4: photo posts, feed, likes, comments, photo map (tasks/prd-random-jeju-merge.md FR-11 - FR-18, FR-31).
-- Safe to run again. Only the backend (service role) may call these functions.
set local statement_timeout = 0;

-- posts.like_count / comment_count were never kept up to date by the old server (all 0 on 2026-11-19).
-- From now on the functions below keep them; this sets them once from the real rows.
update posts p set
  like_count    = (select count(*) from post_likes l where l.post_id = p.id),
  comment_count = (select count(*) from comments c where c.post_id = p.id)
where like_count    is distinct from (select count(*) from post_likes l where l.post_id = p.id)
   or comment_count is distinct from (select count(*) from comments c where c.post_id = p.id);

create index if not exists posts_feed_idx on posts (created_at desc, id desc);
create index if not exists posts_category_feed_idx on posts (category, created_at desc, id desc);
create index if not exists comments_post_idx on comments (post_id, created_at);
create index if not exists photos_user_time_idx on photos (user_id, "timestamp" desc);

-- FR-13: one photo and its post in one transaction. Paths are bucket-qualified ("photos/<uuid>.jpg").
-- p_image_time is Korea time without a zone, like the existing photos.image_time values (Q-09).
create or replace function create_photo_post(
  p_user uuid, p_file_path text, p_thumb_path text, p_lat double precision, p_lng double precision,
  p_image_time timestamp, p_location_source text, p_content text, p_category post_category)
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

-- FR-16: the feed, newest first, by keyset (created_at, id). One post with p_post_id.
create or replace function feed_posts(p_category post_category default null, p_before timestamptz default null,
                                      p_before_id uuid default null, p_limit integer default 20,
                                      p_post_id uuid default null)
returns table (post_id uuid, user_id uuid, nickname text, created_at timestamptz, content text,
               category post_category, file_path text, thumb_path text, lat double precision,
               lng double precision, like_count integer, comment_count integer)
language sql stable
set search_path = public
as $$
  select p.id, p.user_id, u.nickname, p.created_at, p.content, p.category, ph.file_path, ph.thumb_path,
         ph.gps_lat, ph.gps_lng, coalesce(p.like_count, 0), coalesce(p.comment_count, 0)
    from posts p
    left join photos ph on ph.photo_id = p.photo_id
    left join users u on u.id = p.user_id
   where (p_post_id is null or p.id = p_post_id)
     and (p_category is null or p.category = p_category)
     and (p_before is null or (p.created_at, p.id) < (p_before, coalesce(p_before_id, 'ffffffff-ffff-ffff-ffff-ffffffffffff'::uuid)))
   order by p.created_at desc, p.id desc
   limit greatest(1, least(coalesce(p_limit, 20), 50));
$$;

-- FR-14: photo markers in a box, newest first. Uses idx_photos_geom (the old server filtered on gps_lat).
create or replace function photos_in_bbox(min_lat double precision, min_lng double precision,
                                          max_lat double precision, max_lng double precision, max_rows integer default 300)
returns table (photo_id integer, post_id uuid, lat double precision, lng double precision, thumb_path text)
language sql stable
set search_path = public, extensions
as $$
  select ph.photo_id, p.id, ph.gps_lat, ph.gps_lng, ph.thumb_path
    from photos ph
    join posts p on p.photo_id = ph.photo_id
   where ph.geom && st_makeenvelope(min_lng, min_lat, max_lng, max_lat, 4326)
     and ph.thumb_path is not null
   order by p.created_at desc
   limit greatest(1, least(coalesce(max_rows, 300), 300));
$$;

-- FR-15: one cluster per eup/myeon/dong (admin_area_id, not the last word of the name as before).
-- The extent (min/max of its photos) lets a tap on the cluster zoom to where its photos actually are:
-- zooming to the average point showed none of Aewol's 5 spread-out photos (2026-11-19).
drop function if exists photo_clusters(double precision, double precision, double precision, double precision);
create or replace function photo_clusters(min_lat double precision, min_lng double precision,
                                          max_lat double precision, max_lng double precision)
returns table (admin_area_id integer, name text, count integer, lat double precision, lng double precision,
               thumb_path text, south double precision, west double precision, north double precision,
               east double precision)
language sql stable
set search_path = public, extensions
as $$
  with inbox as (
    select ph.admin_area_id, ph.gps_lat, ph.gps_lng, ph.thumb_path, p.created_at
      from photos ph join posts p on p.photo_id = ph.photo_id
     where ph.geom && st_makeenvelope(min_lng, min_lat, max_lng, max_lat, 4326)
       and ph.thumb_path is not null and ph.admin_area_id is not null
  )
  select i.admin_area_id,
         (regexp_split_to_array(max(a.adm_nm), ' '))[array_length(regexp_split_to_array(max(a.adm_nm), ' '), 1)],
         count(*)::integer, avg(i.gps_lat), avg(i.gps_lng),
         (array_agg(i.thumb_path order by i.created_at desc))[1],
         min(i.gps_lat), min(i.gps_lng), max(i.gps_lat), max(i.gps_lng)
    from inbox i join admin_areas a on a.gid = i.admin_area_id
   group by i.admin_area_id
   order by count(*) desc;
$$;

-- FR-17: like / unlike in one statement each, and keep posts.like_count.
create or replace function toggle_like(p_post uuid, p_user uuid)
returns table (liked boolean, like_count integer)
language plpgsql volatile
set search_path = public
as $$
declare
  added integer;
begin
  insert into post_likes (post_id, user_id) values (p_post, p_user) on conflict do nothing;
  get diagnostics added = row_count;
  if added = 0 then
    delete from post_likes where post_id = p_post and user_id = p_user;
  end if;
  update posts set like_count = (select count(*) from post_likes where post_id = p_post) where id = p_post;
  return query select added > 0, (select posts.like_count from posts where id = p_post);
end;
$$;

-- FR-18: add a comment and keep posts.comment_count.
create or replace function add_comment(p_post uuid, p_user uuid, p_content text)
returns table (id uuid, created_at timestamptz)
language plpgsql volatile
set search_path = public
as $$
declare
  new_id uuid;
  made timestamptz;
begin
  insert into comments (post_id, user_id, content) values (p_post, p_user, p_content)
  returning comments.id, comments.created_at into new_id, made;
  update posts set comment_count = (select count(*) from comments where post_id = p_post) where posts.id = p_post;
  return query select new_id, made;
end;
$$;

do $$
declare f text;
begin
  foreach f in array array[
    'create_photo_post(uuid,text,text,double precision,double precision,timestamp,text,text,post_category)',
    'feed_posts(post_category,timestamptz,uuid,integer,uuid)',
    'photos_in_bbox(double precision,double precision,double precision,double precision,integer)',
    'photo_clusters(double precision,double precision,double precision,double precision)',
    'toggle_like(uuid,uuid)',
    'add_comment(uuid,uuid,text)'
  ] loop
    execute format('revoke execute on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $$;
