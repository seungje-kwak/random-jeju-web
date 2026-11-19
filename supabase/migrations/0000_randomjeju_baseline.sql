-- RandomJeju baseline: the public schema of the RandomJeju Supabase project as it was on 2026-11-19
-- (pg_dump --schema-only, no data). Already applied there; kept as the record of what exists.
-- Needs the postgis extension. Includes the RLS changes of 2026-11-19 (PRD 8.6).

--
-- PostgreSQL database dump
--

\restrict NxNgBNPYHBxQYlQZHnEvMDGncUldNPjxqSNWHM7lXXqcgmeoGXZO0gO11fasBEL

-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: post_category; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.post_category AS ENUM (
    '맛집',
    '카페',
    '쇼핑',
    '관광',
    '문화',
    '스포츠'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admin_areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admin_areas (
    gid integer NOT NULL,
    objectid integer,
    adm_nm character varying,
    adm_cd character varying,
    adm_cd2 character varying,
    sgg character varying,
    sido character varying,
    sidonm character varying,
    sggnm character varying,
    geom public.geometry(MultiPolygon,4326)
);


--
-- Name: admin_areas_gid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.admin_areas_gid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_areas_gid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_areas_gid_seq OWNED BY public.admin_areas.gid;


--
-- Name: comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    post_id uuid NOT NULL,
    user_id uuid NOT NULL,
    content text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: grids; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.grids (
    id bigint NOT NULL,
    cell public.geometry(Polygon,4326) NOT NULL,
    weight real DEFAULT 1.0,
    blacklist boolean DEFAULT false,
    adm_nm character varying
);


--
-- Name: grids_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.grids_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: grids_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.grids_id_seq OWNED BY public.grids.id;


--
-- Name: locations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.locations (
    location_id integer NOT NULL,
    lat double precision NOT NULL,
    lng double precision NOT NULL,
    address text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    grid_id integer
);


--
-- Name: locations_location_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.locations_location_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: locations_location_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.locations_location_id_seq OWNED BY public.locations.location_id;


--
-- Name: photos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.photos (
    photo_id integer NOT NULL,
    file_path text NOT NULL,
    gps_lat double precision,
    gps_lng double precision,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    image_time timestamp without time zone,
    thumb_path text,
    user_id uuid,
    grid_id integer,
    admin_area_id integer,
    geom public.geometry(Point,4326)
);


--
-- Name: photos_photo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.photos_photo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: photos_photo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.photos_photo_id_seq OWNED BY public.photos.photo_id;


--
-- Name: post_likes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.post_likes (
    post_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: posts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.posts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    photo_id integer NOT NULL,
    grid_id integer,
    category public.post_category NOT NULL,
    content text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    like_count integer DEFAULT 0,
    comment_count integer DEFAULT 0
);


--
-- Name: preference_category_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.preference_category_map (
    preference text NOT NULL,
    category public.post_category NOT NULL,
    weight real NOT NULL,
    CONSTRAINT preference_category_map_weight_check CHECK (((weight > (0)::double precision) AND (weight <= (1)::double precision)))
);


--
-- Name: reco_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reco_config (
    key text NOT NULL,
    value real NOT NULL,
    description text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_events (
    event_id bigint NOT NULL,
    user_id uuid NOT NULL,
    session_id text,
    event_type text NOT NULL,
    item_type text NOT NULL,
    item_id text NOT NULL,
    source_tag text,
    request_id uuid,
    "position" integer,
    dwell_ms integer,
    lat double precision,
    lng double precision,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    meta jsonb
);


--
-- Name: user_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_events_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_events_event_id_seq OWNED BY public.user_events.event_id;


--
-- Name: user_profile_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_profile_settings (
    user_id uuid NOT NULL,
    notification_enabled boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_profile_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_profile_stats (
    user_id uuid NOT NULL,
    visited_count integer DEFAULT 0 NOT NULL,
    received_like_count integer DEFAULT 0 NOT NULL,
    post_count integer DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT user_profile_stats_post_count_check CHECK ((post_count >= 0)),
    CONSTRAINT user_profile_stats_received_like_count_check CHECK ((received_like_count >= 0)),
    CONSTRAINT user_profile_stats_visited_count_check CHECK ((visited_count >= 0))
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    join_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    nickname text,
    profile_image text,
    age_group text,
    home_region text,
    preferences text[],
    id uuid NOT NULL
);


--
-- Name: admin_areas gid; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_areas ALTER COLUMN gid SET DEFAULT nextval('public.admin_areas_gid_seq'::regclass);


--
-- Name: grids id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grids ALTER COLUMN id SET DEFAULT nextval('public.grids_id_seq'::regclass);


--
-- Name: locations location_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.locations ALTER COLUMN location_id SET DEFAULT nextval('public.locations_location_id_seq'::regclass);


--
-- Name: photos photo_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos ALTER COLUMN photo_id SET DEFAULT nextval('public.photos_photo_id_seq'::regclass);


--
-- Name: user_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_events ALTER COLUMN event_id SET DEFAULT nextval('public.user_events_event_id_seq'::regclass);


--
-- Name: admin_areas admin_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_areas
    ADD CONSTRAINT admin_areas_pkey PRIMARY KEY (gid);


--
-- Name: comments comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_pkey PRIMARY KEY (id);


--
-- Name: grids grids_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grids
    ADD CONSTRAINT grids_pkey PRIMARY KEY (id);


--
-- Name: locations locations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_pkey PRIMARY KEY (location_id);


--
-- Name: photos photos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_pkey PRIMARY KEY (photo_id);


--
-- Name: post_likes post_likes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_likes
    ADD CONSTRAINT post_likes_pkey PRIMARY KEY (post_id, user_id);


--
-- Name: post_likes post_likes_unique_post_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_likes
    ADD CONSTRAINT post_likes_unique_post_user UNIQUE (post_id, user_id);


--
-- Name: posts posts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_pkey PRIMARY KEY (id);


--
-- Name: preference_category_map preference_category_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.preference_category_map
    ADD CONSTRAINT preference_category_map_pkey PRIMARY KEY (preference, category);


--
-- Name: reco_config reco_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reco_config
    ADD CONSTRAINT reco_config_pkey PRIMARY KEY (key);


--
-- Name: user_events user_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_events
    ADD CONSTRAINT user_events_pkey PRIMARY KEY (event_id);


--
-- Name: user_profile_settings user_profile_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile_settings
    ADD CONSTRAINT user_profile_settings_pkey PRIMARY KEY (user_id);


--
-- Name: user_profile_stats user_profile_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile_stats
    ADD CONSTRAINT user_profile_stats_pkey PRIMARY KEY (user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: admin_areas_geom_geom_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admin_areas_geom_geom_idx ON public.admin_areas USING gist (geom);


--
-- Name: idx_admin_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_admin_geom ON public.admin_areas USING gist (geom);


--
-- Name: idx_grids_cell; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_grids_cell ON public.grids USING gist (cell);


--
-- Name: idx_photos_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_photos_geom ON public.photos USING gist (geom);


--
-- Name: idx_user_events_item; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_events_item ON public.user_events USING btree (item_type, item_id, ts DESC);


--
-- Name: idx_user_events_request; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_events_request ON public.user_events USING btree (request_id);


--
-- Name: idx_user_events_user_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_events_user_ts ON public.user_events USING btree (user_id, ts DESC);


--
-- Name: comments comments_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE;


--
-- Name: comments comments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: photos photos_admin_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_admin_area_id_fkey FOREIGN KEY (admin_area_id) REFERENCES public.admin_areas(gid);


--
-- Name: photos photos_grid_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_grid_id_fkey FOREIGN KEY (grid_id) REFERENCES public.grids(id);


--
-- Name: photos photos_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: post_likes post_likes_post_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_likes
    ADD CONSTRAINT post_likes_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE;


--
-- Name: post_likes post_likes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.post_likes
    ADD CONSTRAINT post_likes_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: posts posts_grid_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_grid_id_fkey FOREIGN KEY (grid_id) REFERENCES public.grids(id);


--
-- Name: posts posts_photo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_photo_id_fkey FOREIGN KEY (photo_id) REFERENCES public.photos(photo_id) ON DELETE CASCADE;


--
-- Name: posts posts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: user_events user_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_events
    ADD CONSTRAINT user_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_profile_settings user_profile_settings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile_settings
    ADD CONSTRAINT user_profile_settings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_profile_stats user_profile_stats_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile_stats
    ADD CONSTRAINT user_profile_stats_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users users_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: admin_areas; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.admin_areas ENABLE ROW LEVEL SECURITY;

--
-- Name: comments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.comments ENABLE ROW LEVEL SECURITY;

--
-- Name: comments comments are readable; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "comments are readable" ON public.comments FOR SELECT USING (true);


--
-- Name: grids; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.grids ENABLE ROW LEVEL SECURITY;

--
-- Name: post_likes likes are readable; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "likes are readable" ON public.post_likes FOR SELECT USING (true);


--
-- Name: locations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.locations ENABLE ROW LEVEL SECURITY;

--
-- Name: users own row insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "own row insert" ON public.users FOR INSERT TO authenticated WITH CHECK ((auth.uid() = id));


--
-- Name: users own row read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "own row read" ON public.users FOR SELECT TO authenticated USING ((auth.uid() = id));


--
-- Name: photos; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.photos ENABLE ROW LEVEL SECURITY;

--
-- Name: post_likes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.post_likes ENABLE ROW LEVEL SECURITY;

--
-- Name: posts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;

--
-- Name: posts posts are public; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "posts are public" ON public.posts FOR SELECT USING (true);


--
-- Name: preference_category_map; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.preference_category_map ENABLE ROW LEVEL SECURITY;

--
-- Name: reco_config; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.reco_config ENABLE ROW LEVEL SECURITY;

--
-- Name: user_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_events ENABLE ROW LEVEL SECURITY;

--
-- Name: user_profile_settings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_profile_settings ENABLE ROW LEVEL SECURITY;

--
-- Name: user_profile_stats; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_profile_stats ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: comments users can comment; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "users can comment" ON public.comments FOR INSERT WITH CHECK ((auth.uid() = user_id));


--
-- Name: posts users can create posts; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "users can create posts" ON public.posts FOR INSERT WITH CHECK ((auth.uid() = user_id));


--
-- Name: comments users can delete own comments; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "users can delete own comments" ON public.comments FOR DELETE USING ((auth.uid() = user_id));


--
-- Name: posts users can delete own posts; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "users can delete own posts" ON public.posts FOR DELETE USING ((auth.uid() = user_id));


--
-- Name: post_likes users can like; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "users can like" ON public.post_likes FOR INSERT WITH CHECK ((auth.uid() = user_id));


--
-- Name: posts users can modify own posts; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "users can modify own posts" ON public.posts FOR UPDATE USING ((auth.uid() = user_id));


--
-- Name: post_likes users can unlike; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "users can unlike" ON public.post_likes FOR DELETE USING ((auth.uid() = user_id));


--
-- PostgreSQL database dump complete
--

\unrestrict NxNgBNPYHBxQYlQZHnEvMDGncUldNPjxqSNWHM7lXXqcgmeoGXZO0gO11fasBEL

