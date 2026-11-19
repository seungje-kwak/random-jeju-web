-- Random Jeju M3: random points on land, away from empty corners (tasks/prd-random-jeju-merge.md FR-0, FR-1).
-- Safe to run again. After it, run backend/scripts/mark_grids.py to fill grids.blacklist.
set local statement_timeout = 0;

alter table grids add column if not exists land_share real;                          -- land area / cell area
alter table grids add column if not exists land_lat double precision;                -- a point on the land part
alter table grids add column if not exists land_lng double precision;

-- Clip every cell to the 43 eup/myeon/dong boundaries once (the boundaries do not change).
with land as (select st_union(geom) as g from admin_areas),
clipped as (
  select gr.id, st_collectionextract(st_intersection(gr.cell, land.g), 3) as part, st_area(gr.cell) as cell_area
    from grids gr, land
   where gr.land_cell is null
)
update grids gr
   set land_cell  = case when st_isempty(c.part) then null else c.part end,
       land_share = case when st_isempty(c.part) then 0 else (st_area(c.part) / c.cell_area)::real end,
       land_lat   = case when st_isempty(c.part) then null else st_y(st_pointonsurface(c.part)) end,
       land_lng   = case when st_isempty(c.part) then null else st_x(st_pointonsurface(c.part)) end
  from clipped c
 where gr.id = c.id;

-- FR-1: one cell, all usable cells equally likely, then one uniform point on its land part.
create or replace function random_point()
returns table (grid_id bigint, lat double precision, lng double precision, adm_nm text)
language sql volatile
set search_path = public, extensions
as $$
  with g as (
    select id, adm_nm, land_cell from grids
     where not coalesce(blacklist, false) and land_cell is not null
     order by random() limit 1
  ), p as (
    select g.id, g.adm_nm, (st_dump(st_generatepoints(g.land_cell, 1))).geom as pt from g
  )
  select p.id, st_y(p.pt), st_x(p.pt), p.adm_nm::text from p;
$$;

-- FR-0: scripts/mark_grids.py decides which cells to skip and sends their ids here (one transaction).
create or replace function mark_grids(skip_ids bigint[])
returns integer
language sql volatile
set search_path = public
as $$
  -- the WHERE is required: PostgREST runs pg-safeupdate, which refuses an UPDATE without one
  update grids set blacklist = (id = any(skip_ids))
   where blacklist is distinct from (id = any(skip_ids));
  select count(*)::integer from grids where blacklist;
$$;

-- Only the backend (service role) calls these (FR-34: the browser never reads data directly).
revoke execute on function random_point() from public, anon, authenticated;
revoke execute on function mark_grids(bigint[]) from public, anon, authenticated;
grant execute on function random_point() to service_role;
grant execute on function mark_grids(bigint[]) to service_role;
