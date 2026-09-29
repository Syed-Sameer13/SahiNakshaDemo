-- SahiNaksha Supabase/PostGIS foundation.
-- Run in Supabase SQL editor after enabling the PostGIS extension.

create extension if not exists postgis;

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  description text,
  created_at timestamptz not null default now()
);

create table if not exists public.surveys (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  name text not null,
  source_image_url text,
  source_crs text,
  status text not null default 'uploaded',
  created_at timestamptz not null default now()
);

create table if not exists public.parcels (
  id uuid primary key default gen_random_uuid(),
  survey_id uuid not null references public.surveys(id) on delete cascade,
  parcel_id text not null,
  geom geometry(Geometry, 4326),
  area_sq_m double precision,
  review_score double precision,
  review_priority text,
  status text not null default 'candidate',
  properties jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.validation_issues (
  id uuid primary key default gen_random_uuid(),
  survey_id uuid not null references public.surveys(id) on delete cascade,
  parcel_id text,
  issue_type text not null,
  severity text not null default 'medium',
  description text not null,
  resolved boolean not null default false,
  created_at timestamptz not null default now()
);

alter table public.projects enable row level security;
alter table public.surveys enable row level security;
alter table public.parcels enable row level security;
alter table public.validation_issues enable row level security;

create policy "project owners can manage projects"
on public.projects for all
using (owner_id = auth.uid())
with check (owner_id = auth.uid());

create policy "project owners can access surveys"
on public.surveys for all
using (exists (select 1 from public.projects p where p.id = project_id and p.owner_id = auth.uid()))
with check (exists (select 1 from public.projects p where p.id = project_id and p.owner_id = auth.uid()));

create policy "project owners can access parcels"
on public.parcels for all
using (exists (
  select 1 from public.surveys s join public.projects p on p.id = s.project_id
  where s.id = survey_id and p.owner_id = auth.uid()
))
with check (exists (
  select 1 from public.surveys s join public.projects p on p.id = s.project_id
  where s.id = survey_id and p.owner_id = auth.uid()
));

create policy "project owners can access validation issues"
on public.validation_issues for all
using (exists (
  select 1 from public.surveys s join public.projects p on p.id = s.project_id
  where s.id = survey_id and p.owner_id = auth.uid()
))
with check (exists (
  select 1 from public.surveys s join public.projects p on p.id = s.project_id
  where s.id = survey_id and p.owner_id = auth.uid()
));
