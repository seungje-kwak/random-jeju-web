-- Random Jeju M5: visit check-ins (tasks/prd-random-jeju-merge.md FR-19 - FR-21, US-031). Safe to run again.
-- The rule itself (distance, time, which courses) is in backend/app/visits.py; these only store and read.
set local statement_timeout = 0;

-- FR-21: one check-in per course and place (or per course's random point). A second photo of the same
-- spot returns the first check-in instead of adding one.
create or replace function add_visit(p_user uuid, p_course uuid, p_kind text, p_place integer,
                                     p_location integer, p_post uuid)
returns table (course_id uuid, kind text, place_id integer, post_id uuid, is_new boolean)
language plpgsql volatile
set search_path = public
as $$
declare
  made bigint;
begin
  insert into visits (user_id, course_id, kind, place_id, location_id, post_id)
  values (p_user, p_course, p_kind, p_place, p_location, p_post)
  on conflict do nothing
  returning id into made;
  return query
    select v.course_id, v.kind, v.place_id, v.post_id, made is not null
      from visits v
     where v.course_id = p_course and v.kind = p_kind and coalesce(v.place_id, 0) = coalesce(p_place, 0);
end;
$$;

-- FR-10 `visits` of a course, with the photo that checked in.
create or replace function course_visits(p_course uuid)
returns table (kind text, place_id integer, post_id uuid, thumb_path text, file_path text)
language sql stable
set search_path = public
as $$
  select v.kind, v.place_id, v.post_id, ph.thumb_path, ph.file_path
    from visits v
    join posts p on p.id = v.post_id
    left join photos ph on ph.photo_id = p.photo_id
   where v.course_id = p_course
   order by v.created_at;
$$;

-- FR-16 feed, now with the post's check-in for the badge (US-031): the random point first, else a stop.
drop function if exists feed_posts(post_category, timestamptz, uuid, integer, uuid);
create or replace function feed_posts(p_category post_category default null, p_before timestamptz default null,
                                      p_before_id uuid default null, p_limit integer default 20,
                                      p_post_id uuid default null)
returns table (post_id uuid, user_id uuid, nickname text, created_at timestamptz, content text,
               category post_category, file_path text, thumb_path text, lat double precision,
               lng double precision, like_count integer, comment_count integer,
               visit_kind text, visit_place_name_ko text, visit_place_name_en text)
language sql stable
set search_path = public
as $$
  select p.id, p.user_id, u.nickname, p.created_at, p.content, p.category, ph.file_path, ph.thumb_path,
         ph.gps_lat, ph.gps_lng, coalesce(p.like_count, 0), coalesce(p.comment_count, 0),
         v.kind, pl.name_ko, pl.name_en
    from posts p
    left join photos ph on ph.photo_id = p.photo_id
    left join users u on u.id = p.user_id
    left join lateral (
      select vv.kind, vv.place_id from visits vv where vv.post_id = p.id
       order by (vv.kind = 'random_point') desc, vv.created_at limit 1
    ) v on true
    left join places pl on pl.id = v.place_id
   where (p_post_id is null or p.id = p_post_id)
     and (p_category is null or p.category = p_category)
     and (p_before is null or (p.created_at, p.id) < (p_before, coalesce(p_before_id, 'ffffffff-ffff-ffff-ffff-ffffffffffff'::uuid)))
   order by p.created_at desc, p.id desc
   limit greatest(1, least(coalesce(p_limit, 20), 50));
$$;

create index if not exists visits_course_idx on visits (course_id);

do $$
declare f text;
begin
  foreach f in array array[
    'add_visit(uuid,uuid,text,integer,integer,uuid)',
    'course_visits(uuid)',
    'feed_posts(post_category,timestamptz,uuid,integer,uuid)'
  ] loop
    execute format('revoke execute on function %s from public, anon, authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $$;
