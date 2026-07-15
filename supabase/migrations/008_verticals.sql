create table if not exists verticals (
  id text primary key,
  name text not null,
  coverage_note text not null,
  display_order integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists vertical_provisions (
  vertical_id text not null references verticals(id) on delete cascade,
  provision_code text not null references provisions(code),
  weight numeric not null default 1.0 check (weight > 0),
  primary key (vertical_id, provision_code)
);

alter table verticals enable row level security;
alter table vertical_provisions enable row level security;

create or replace view v_vertical_pci as
with latest_pci as (
  select distinct on (w.provision)
    w.provision,
    w.week_start,
    w.pci,
    w.delta_this_week
  from pci_weekly w
  order by w.provision, w.week_start desc, w.week desc
),
last_changes as (
  select
    w.provision,
    max(w.week_start) as last_change_week_start
  from pci_weekly w
  where w.delta_this_week <> 0
  group by w.provision
)
select
  v.id,
  v.name,
  v.coverage_note,
  v.display_order,
  round(
    sum(lp.pci * vp.weight)
      / nullif(sum(vp.weight) filter (where lp.pci is not null), 0),
    2
  ) as vertical_pci,
  round(sum(p.baseline_pci * vp.weight) / nullif(sum(vp.weight), 0), 2)
    as baseline_pci,
  round(
    sum(lp.delta_this_week * vp.weight)
      / nullif(sum(vp.weight) filter (where lp.pci is not null), 0),
    2
  ) as weekly_delta,
  max(lp.week_start) as as_of_week_start,
  max(lc.last_change_week_start) as last_change_week_start,
  array_agg(vp.provision_code order by vp.provision_code) as provisions
from verticals v
join vertical_provisions vp on vp.vertical_id = v.id
join provisions p on p.code = vp.provision_code
left join latest_pci lp on lp.provision = vp.provision_code
left join last_changes lc on lc.provision = vp.provision_code
group by v.id, v.name, v.coverage_note, v.display_order;

revoke all on verticals, vertical_provisions from anon, authenticated;
grant select on v_vertical_pci to anon;

grant all on verticals to service_role;
grant all on vertical_provisions to service_role;
