create table if not exists scored_deltas (
  week text not null,
  doc_id text not null,
  provision text not null references provisions(code),
  specificity_delta numeric not null,
  durability_delta numeric not null,
  enforceability_delta numeric not null,
  rationale text,
  confidence numeric,
  model text,
  prompt_version text,
  temperature numeric,
  scored_at timestamptz,
  cached boolean not null default false,
  cost_usd numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (week, doc_id, provision)
);

alter table scored_deltas enable row level security;

grant all on scored_deltas to service_role;

