create table if not exists source_request_cache (
  request_key text primary key,
  source text not null,
  method text not null,
  url text not null,
  sanitized_params jsonb not null default '{}'::jsonb,
  sanitized_body_hash text,
  status_code integer not null,
  request_headers jsonb not null default '{}'::jsonb,
  response_headers jsonb not null default '{}'::jsonb,
  rate_limit_headers jsonb not null default '{}'::jsonb,
  response_hash text not null,
  response_body text,
  fetched_at timestamptz not null default now(),
  expires_at timestamptz,
  latency_ms integer,
  cache_hit boolean not null default false,
  raw_public_metadata jsonb not null default '{}'::jsonb
);

create table if not exists document_chunks (
  chunk_id text primary key,
  source_doc_id text not null references source_documents(source_doc_id),
  chunk_index integer not null,
  chunk_hash text not null,
  source text not null,
  title text not null,
  section_title text,
  text text not null,
  char_start integer not null,
  char_end integer not null,
  published_at timestamptz,
  fetched_at timestamptz,
  raw_public_metadata jsonb not null default '{}'::jsonb,
  unique (source_doc_id, chunk_index, chunk_hash)
);

alter table evidence_items
  add column if not exists raw_public_metadata jsonb not null default '{}'::jsonb;

alter table source_request_cache enable row level security;
alter table document_chunks enable row level security;

create index if not exists idx_source_request_cache_source_fetched_at
  on source_request_cache (source, fetched_at desc);
create index if not exists idx_source_request_cache_expires_at
  on source_request_cache (expires_at);
create index if not exists idx_document_chunks_source_doc_id
  on document_chunks (source_doc_id, chunk_index);
create index if not exists idx_document_chunks_chunk_hash
  on document_chunks (chunk_hash);

create or replace view v_evidence_items as
select
  e.evidence_id,
  e.source_doc_id,
  e.provision,
  p.name as provision_name,
  e.evidence_type,
  e.snippet,
  e.normalized_signal,
  e.score_dimension,
  e.confidence,
  e.extractor_version,
  e.created_at,
  coalesce(e.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers' as raw_public_metadata,
  d.source,
  d.source_name,
  d.source_type,
  d.title as source_title,
  d.agency,
  d.url,
  d.published_at,
  d.fetched_at
from evidence_items e
left join source_documents d on d.source_doc_id = e.source_doc_id
left join provisions p on p.code = e.provision;

grant all on source_request_cache to service_role;
grant all on document_chunks to service_role;
grant all on evidence_items to service_role;
grant select on v_evidence_items to anon, authenticated;
