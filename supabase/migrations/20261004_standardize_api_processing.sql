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
