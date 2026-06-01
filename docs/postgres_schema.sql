-- Safety Engine Reference Pack v0.1
-- PostgreSQL starter schema
-- Notes:
-- 1) JSON files in /data are the source of truth for the starter pack
-- 2) This SQL schema is a recommended normalized relational model for production
-- 3) Arrays in the JSON files (evidence_chunk_ids, source_ids, alias lists) should be exploded into child tables at ingest

create extension if not exists pg_trgm;

create table if not exists source_registry (
    source_id text primary key,
    title text not null,
    source_type text not null,
    organization text,
    jurisdiction text,
    publication_year int,
    publication_date text,
    url text,
    doi text,
    pmid text,
    authors jsonb,
    journal text,
    evidence_tier text,
    access_model text,
    ingestion_status text,
    notes_ko text,
    created_at timestamptz default now()
);

create table if not exists ingredients (
    ingredient_id text primary key,
    ingredient_name_ko text not null,
    ingredient_name_en text,
    category text,
    forms jsonb default '[]'::jsonb,
    quality_notes_ko text,
    created_at timestamptz default now()
);

create table if not exists ingredient_aliases (
    alias_id bigserial primary key,
    ingredient_id text not null references ingredients(ingredient_id) on delete cascade,
    alias_text text not null,
    alias_lang text not null check (alias_lang in ('ko','en','other')),
    alias_kind text default 'matching',
    unique (ingredient_id, alias_text, alias_lang)
);

create index if not exists idx_ingredient_aliases_alias_text_trgm
on ingredient_aliases using gin (alias_text gin_trgm_ops);

create table if not exists evidence_chunks (
    chunk_id text primary key,
    source_id text not null references source_registry(source_id) on delete cascade,
    locator_type text not null,
    locator_value text not null,
    excerpt_summary_ko text not null,
    claim_type text,
    structured_claim jsonb,
    confidence text,
    notes_ko text,
    created_at timestamptz default now()
);

create table if not exists evidence_chunk_ingredients (
    chunk_id text not null references evidence_chunks(chunk_id) on delete cascade,
    ingredient_id text not null references ingredients(ingredient_id) on delete cascade,
    primary key (chunk_id, ingredient_id)
);

create table if not exists safety_rules (
    rule_id text primary key,
    rule_group_id text,
    ingredient_id text not null references ingredients(ingredient_id) on delete cascade,
    rule_name_ko text not null,
    rule_category text not null,
    severity text not null,
    priority int not null default 50,
    jurisdiction text,
    applies_when jsonb not null default '{}'::jsonb,
    threshold_operator text,
    threshold_value numeric,
    threshold_unit text,
    threshold_scope text,
    action_text_ko text not null,
    rationale_ko text not null,
    monitoring_ko text,
    exception_ko text,
    review_status text not null,
    schema_note text,
    created_at timestamptz default now()
);

create index if not exists idx_safety_rules_ingredient on safety_rules (ingredient_id);
create index if not exists idx_safety_rules_category on safety_rules (rule_category);
create index if not exists idx_safety_rules_severity on safety_rules (severity);
create index if not exists idx_safety_rules_jurisdiction on safety_rules (jurisdiction);
create index if not exists idx_safety_rules_applies_when on safety_rules using gin (applies_when jsonb_path_ops);

create table if not exists safety_rule_evidence_chunks (
    rule_id text not null references safety_rules(rule_id) on delete cascade,
    chunk_id text not null references evidence_chunks(chunk_id) on delete cascade,
    primary key (rule_id, chunk_id)
);

create table if not exists safety_rule_sources (
    rule_id text not null references safety_rules(rule_id) on delete cascade,
    source_id text not null references source_registry(source_id) on delete cascade,
    primary key (rule_id, source_id)
);

-- Optional runtime tables for service operation

create table if not exists evaluation_runs (
    evaluation_id text primary key,
    evaluated_at timestamptz not null,
    engine_version text,
    jurisdiction_preference jsonb,
    strictest_mode_for_conflicts boolean default true,
    user_profile jsonb not null,
    candidate_stack jsonb not null,
    created_at timestamptz default now()
);

create table if not exists evaluation_run_rule_hits (
    evaluation_id text not null references evaluation_runs(evaluation_id) on delete cascade,
    ingredient_id text not null references ingredients(ingredient_id),
    rule_id text not null references safety_rules(rule_id),
    decision text,
    warning_text_ko text,
    monitoring_ko text,
    primary key (evaluation_id, ingredient_id, rule_id)
);

create table if not exists evaluation_run_output (
    evaluation_id text primary key references evaluation_runs(evaluation_id) on delete cascade,
    overall_decision text not null,
    summary_ko text,
    blocked_ingredients jsonb,
    dose_adjust_required_ingredients jsonb,
    manual_review_required_ingredients jsonb,
    top_risks jsonb,
    ingredient_results jsonb,
    reference_bundle jsonb,
    created_at timestamptz default now()
);
