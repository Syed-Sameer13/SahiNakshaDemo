-- SahiNaksha API standardization migration.
-- Safe/additive for an existing prototype database.

alter table public.processing_jobs
  add column if not exists model_used text;

alter table public.processing_jobs
  add column if not exists input jsonb not null default '{}'::jsonb;

alter table public.processing_jobs
  add column if not exists output jsonb not null default '{}'::jsonb;

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
  set
    geom_native = case
      when p_geometry is null then null
      else ST_SetSRID(
        ST_GeomFromGeoJSON(p_geometry::text),
        coalesce(p_srid, 0)
      )
    end,
    geom_crs = case
      when coalesce(p_srid, 0) = 0 then geom_crs
      else 'EPSG:' || p_srid::text
    end
  where id = p_parcel_id;
end;
$$;

grant execute on function public.set_parcel_native_geometry(uuid, jsonb, integer) to authenticated;


create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  survey_id uuid references public.surveys(id) on delete cascade,
  parcel_record_id uuid references public.parcels(id) on delete set null,
  actor_id uuid not null references auth.users(id) on delete cascade,
  event_type text not null,
  entity_type text,
  entity_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists audit_events_survey_created_idx on public.audit_events(survey_id, created_at desc);
alter table public.audit_events enable row level security;

drop policy if exists "project owners can access audit events" on public.audit_events;
create policy "project owners can access audit events" on public.audit_events for all
using (exists (select 1 from public.surveys s join public.projects p on p.id=s.project_id where s.id=survey_id and p.owner_id=auth.uid()))
with check (actor_id=auth.uid() and exists (select 1 from public.surveys s join public.projects p on p.id=s.project_id where s.id=survey_id and p.owner_id=auth.uid()));

create or replace function public.get_survey_export_rows(p_survey_id uuid)
returns table (
  parcel_record_id uuid,
  parcel_id text,
  geometry jsonb,
  area_sq_m double precision,
  perimeter_m double precision,
  review_score double precision,
  review_priority text,
  review_status text,
  properties jsonb,
  ai_evidence jsonb,
  reference_comparison jsonb,
  provenance jsonb,
  reviewer uuid,
  reviewed_at timestamptz,
  updated_at timestamptz
)
language sql
security invoker
set search_path=public
as $$
  select p.id,p.parcel_id,
    case when p.geom_native is null then null else ST_AsGeoJSON(p.geom_native)::jsonb end,
    p.area_sq_m,p.perimeter_m,p.review_score,p.review_priority,p.status,
    p.properties,p.ai_evidence,p.reference_comparison,p.provenance,p.reviewer,p.reviewed_at,p.updated_at
  from public.parcels p
  where p.survey_id=p_survey_id
  order by p.parcel_id;
$$;

grant execute on function public.get_survey_export_rows(uuid) to authenticated;
