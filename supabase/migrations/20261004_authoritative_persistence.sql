-- SahiNaksha additive persistence migration.
-- Run after the original schema.sql. Does not drop existing application tables.

alter table public.parcels add column if not exists geom_native geometry(Geometry);
alter table public.parcels add column if not exists geom_crs text;
alter table public.parcels add column if not exists geometry_crs text;
alter table public.parcels add column if not exists perimeter_m double precision;
alter table public.parcels add column if not exists ai_evidence jsonb not null default '{}'::jsonb;
alter table public.parcels add column if not exists reference_comparison jsonb not null default '{}'::jsonb;
alter table public.parcels add column if not exists provenance jsonb not null default '{}'::jsonb;
alter table public.parcels add column if not exists reviewer uuid references auth.users(id) on delete set null;
alter table public.parcels add column if not exists reviewed_at timestamptz;
alter table public.parcels add column if not exists updated_at timestamptz not null default now();

alter table public.validation_issues add column if not exists evidence jsonb not null default '{}'::jsonb;
alter table public.validation_issues add column if not exists status text not null default 'OPEN';
alter table public.validation_issues add column if not exists updated_at timestamptz not null default now();

create unique index if not exists parcels_survey_parcel_unique on public.parcels(survey_id, parcel_id);
create index if not exists parcels_geom_native_gist on public.parcels using gist(geom_native);

create table if not exists public.processing_jobs (
  id uuid primary key default gen_random_uuid(),
  survey_id uuid not null references public.surveys(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete cascade,
  analysis_id text,
  status text not null default 'queued',
  progress integer not null default 0 check (progress between 0 and 100),
  stage text,
  error_message text,
  result_snapshot jsonb,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.reviews (
  id uuid primary key default gen_random_uuid(),
  survey_id uuid not null references public.surveys(id) on delete cascade,
  parcel_record_id uuid references public.parcels(id) on delete set null,
  parcel_id text not null,
  reviewer uuid not null references auth.users(id) on delete restrict,
  decision text not null,
  comments text,
  previous_status text,
  new_status text not null,
  edited_geometry jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.exports (
  id uuid primary key default gen_random_uuid(),
  survey_id uuid not null references public.surveys(id) on delete cascade,
  processing_job_id uuid references public.processing_jobs(id) on delete set null,
  created_by uuid not null references auth.users(id) on delete cascade,
  format text not null,
  status text not null default 'generated',
  file_name text,
  file_url text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function public.set_sahinaksha_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

drop trigger if exists parcels_set_updated_at on public.parcels;
create trigger parcels_set_updated_at before update on public.parcels for each row execute function public.set_sahinaksha_updated_at();

drop trigger if exists validation_issues_set_updated_at on public.validation_issues;
create trigger validation_issues_set_updated_at before update on public.validation_issues for each row execute function public.set_sahinaksha_updated_at();

drop trigger if exists processing_jobs_set_updated_at on public.processing_jobs;
create trigger processing_jobs_set_updated_at before update on public.processing_jobs for each row execute function public.set_sahinaksha_updated_at();

create or replace function public.set_parcel_native_geometry(
  p_parcel_id uuid,
  p_geometry jsonb,
  p_srid integer default 0
)
returns void
language plpgsql
security invoker
set search_path = public
as $$
begin
  update public.parcels
  set geom_native = case
    when p_geometry is null then null
    else ST_SetSRID(ST_GeomFromGeoJSON(p_geometry::text), coalesce(p_srid, 0))
  end,
  geom_crs = case when coalesce(p_srid, 0) = 0 then geom_crs else 'EPSG:' || p_srid::text end
  where id = p_parcel_id;
end;
$$;

grant execute on function public.set_parcel_native_geometry(uuid, jsonb, integer) to authenticated;

alter table public.processing_jobs enable row level security;
alter table public.reviews enable row level security;
alter table public.exports enable row level security;

revoke all on table public.projects, public.surveys, public.parcels, public.validation_issues,
  public.processing_jobs, public.reviews, public.exports from anon;

grant select, insert, update, delete on table public.projects, public.surveys, public.parcels,
  public.validation_issues, public.processing_jobs, public.reviews, public.exports to authenticated;

drop policy if exists "project owners can access processing jobs" on public.processing_jobs;
create policy "project owners can access processing jobs" on public.processing_jobs for all
using (exists (
  select 1 from public.surveys s join public.projects p on p.id=s.project_id
  where s.id=survey_id and p.owner_id=auth.uid()
))
with check (
  created_by=auth.uid() and exists (
    select 1 from public.surveys s join public.projects p on p.id=s.project_id
    where s.id=survey_id and p.owner_id=auth.uid()
  )
);

drop policy if exists "project owners can access reviews" on public.reviews;
create policy "project owners can access reviews" on public.reviews for all
using (exists (
  select 1 from public.surveys s join public.projects p on p.id=s.project_id
  where s.id=survey_id and p.owner_id=auth.uid()
))
with check (
  reviewer=auth.uid() and exists (
    select 1 from public.surveys s join public.projects p on p.id=s.project_id
    where s.id=survey_id and p.owner_id=auth.uid()
  )
);

drop policy if exists "project owners can access exports" on public.exports;
create policy "project owners can access exports" on public.exports for all
using (exists (
  select 1 from public.surveys s join public.projects p on p.id=s.project_id
  where s.id=survey_id and p.owner_id=auth.uid()
))
with check (
  created_by=auth.uid() and exists (
    select 1 from public.surveys s join public.projects p on p.id=s.project_id
    where s.id=survey_id and p.owner_id=auth.uid()
  )
);

drop policy if exists "project owners can access projects" on public.projects;
create policy "project owners can access projects" on public.projects for all
using (owner_id=auth.uid()) with check (owner_id=auth.uid());

drop policy if exists "project owners can access surveys" on public.surveys;
create policy "project owners can access surveys" on public.surveys for all
using (exists (select 1 from public.projects p where p.id=project_id and p.owner_id=auth.uid()))
with check (exists (select 1 from public.projects p where p.id=project_id and p.owner_id=auth.uid()));

drop policy if exists "project owners can access parcels" on public.parcels;
create policy "project owners can access parcels" on public.parcels for all
using (exists (select 1 from public.surveys s join public.projects p on p.id=s.project_id where s.id=survey_id and p.owner_id=auth.uid()))
with check (exists (select 1 from public.surveys s join public.projects p on p.id=s.project_id where s.id=survey_id and p.owner_id=auth.uid()));

drop policy if exists "project owners can access validation issues" on public.validation_issues;
create policy "project owners can access validation issues" on public.validation_issues for all
using (exists (select 1 from public.surveys s join public.projects p on p.id=s.project_id where s.id=survey_id and p.owner_id=auth.uid()))
with check (exists (select 1 from public.surveys s join public.projects p on p.id=s.project_id where s.id=survey_id and p.owner_id=auth.uid()));
