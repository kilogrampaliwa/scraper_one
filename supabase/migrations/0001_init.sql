-- 0001_init.sql
-- Schema, RPC functions and read-only views for the cloud scraper pipeline.
-- See AI/01_database.md for the design this implements.

-- ============================================================================
-- Tables
-- ============================================================================

create table if not exists tasks (
    task_id bigserial primary key,
    name text not null unique,
    type text not null check (type in ('api', 'html')),
    target_url text not null,
    request_params jsonb not null default '{}'::jsonb,
    parse_config jsonb not null default '{}'::jsonb,
    llm_schema jsonb not null default '{}'::jsonb,
    output_table text not null check (output_table in ('price_history', 'job_postings')),
    enabled boolean not null default true,
    schedule_interval_minutes int not null default 60,
    created_at timestamptz not null default now()
);

create table if not exists queue (
    id bigserial primary key,
    task_id bigint not null references tasks (task_id),
    url text not null,
    priority int not null default 0,
    status text not null default 'raw'
        check (status in ('raw', 'in_progress', 'ready', 'analyzed', 'rejected')),
    retry_count int not null default 0,
    max_retries int not null default 3,
    last_checked timestamptz,
    raw_data jsonb,
    clean_data jsonb,
    error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_queue_claim on queue (status, priority desc, id);
create index if not exists idx_queue_task_id on queue (task_id);

create table if not exists price_history (
    id bigserial primary key,
    task_id bigint not null references tasks (task_id),
    queue_id bigint references queue (id) on delete cascade,
    product_name text,
    brand text,
    category text,
    price numeric,
    currency char(3),
    in_stock boolean,
    source_url text,
    scraped_at timestamptz not null default now()
);

create index if not exists idx_price_history_scraped_at on price_history (scraped_at);

create table if not exists job_postings (
    id bigserial primary key,
    task_id bigint not null references tasks (task_id),
    queue_id bigint references queue (id) on delete cascade,
    job_title text,
    company text,
    seniority text,
    tech_stack text[],
    salary_min numeric,
    salary_max numeric,
    currency char(3),
    location text,
    remote boolean,
    source_url text,
    scraped_at timestamptz not null default now()
);

create index if not exists idx_job_postings_scraped_at on job_postings (scraped_at);

-- ============================================================================
-- RPC functions (SECURITY DEFINER, called by the worker via the service role)
-- ============================================================================

-- Atomically claim up to p_limit queue rows in p_from_status, for enabled
-- tasks, and flip them to 'in_progress'.
create or replace function claim_batch(p_limit int, p_from_status text default 'raw')
returns setof queue
language plpgsql
security definer
set search_path = public
as $$
begin
    return query
    update queue
    set status = 'in_progress',
        last_checked = now(),
        updated_at = now()
    where id in (
        select q.id
        from queue q
        join tasks t on t.task_id = q.task_id
        where q.status = p_from_status
          and t.enabled = true
        order by q.priority desc, q.id asc
        limit p_limit
        for update of q skip locked
    )
    returning *;
end;
$$;

-- Mark a queue row as successfully scraped, storing raw_data.
create or replace function mark_ready(p_id bigint, p_raw_data jsonb)
returns void
language sql
security definer
set search_path = public
as $$
    update queue
    set raw_data = p_raw_data,
        status = 'ready',
        last_checked = now(),
        updated_at = now()
    where id = p_id;
$$;

-- Mark a queue row as failed: increments retry_count, and either reverts to
-- 'raw' for another attempt or moves to 'rejected' once max_retries is hit.
create or replace function mark_rejected(p_id bigint, p_error text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_retry_count int;
    v_max_retries int;
begin
    update queue
    set retry_count = retry_count + 1,
        last_checked = now(),
        updated_at = now()
    where id = p_id
    returning retry_count, max_retries into v_retry_count, v_max_retries;

    if v_retry_count >= v_max_retries then
        update queue
        set status = 'rejected',
            error = p_error,
            updated_at = now()
        where id = p_id;
    else
        update queue
        set status = 'raw',
            error = p_error,
            updated_at = now()
        where id = p_id;
    end if;
end;
$$;

-- Store the LLM-normalized clean_data, mark the row 'analyzed', and insert
-- one row per item into the task's output_table (allow-listed).
create or replace function finalize_analysis(p_id bigint, p_clean_data jsonb)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_task_id bigint;
    v_output_table text;
    v_source_url text;
    v_items jsonb;
    v_item jsonb;
begin
    select q.task_id, t.output_table, q.url
    into v_task_id, v_output_table, v_source_url
    from queue q
    join tasks t on t.task_id = q.task_id
    where q.id = p_id;

    if v_output_table not in ('price_history', 'job_postings') then
        raise exception 'finalize_analysis: invalid output_table %', v_output_table;
    end if;

    if jsonb_typeof(p_clean_data) = 'array' then
        v_items := p_clean_data;
    else
        v_items := jsonb_build_array(p_clean_data);
    end if;

    update queue
    set clean_data = p_clean_data,
        status = 'analyzed',
        error = null,
        updated_at = now()
    where id = p_id;

    for v_item in select * from jsonb_array_elements(v_items)
    loop
        if v_output_table = 'price_history' then
            execute format(
                'insert into %I (task_id, queue_id, product_name, brand, category, price, currency, in_stock, source_url) '
                'values ($1, $2, $3, $4, $5, $6, $7, $8, $9)',
                v_output_table
            )
            using
                v_task_id,
                p_id,
                v_item ->> 'product_name',
                v_item ->> 'brand',
                v_item ->> 'category',
                nullif(v_item ->> 'price', '')::numeric,
                v_item ->> 'currency',
                nullif(v_item ->> 'in_stock', '')::boolean,
                v_source_url;
        elsif v_output_table = 'job_postings' then
            execute format(
                'insert into %I (task_id, queue_id, job_title, company, seniority, tech_stack, salary_min, salary_max, currency, location, remote, source_url) '
                'values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)',
                v_output_table
            )
            using
                v_task_id,
                p_id,
                v_item ->> 'job_title',
                v_item ->> 'company',
                v_item ->> 'seniority',
                case
                    when v_item ? 'tech_stack' and jsonb_typeof(v_item -> 'tech_stack') = 'array'
                        then coalesce(
                            (select array_agg(x) from jsonb_array_elements_text(v_item -> 'tech_stack') as x),
                            array[]::text[]
                        )
                    else null
                end,
                nullif(v_item ->> 'salary_min', '')::numeric,
                nullif(v_item ->> 'salary_max', '')::numeric,
                v_item ->> 'currency',
                v_item ->> 'location',
                nullif(v_item ->> 'remote', '')::boolean,
                v_source_url;
        end if;
    end loop;

    -- Data minimization: once a job posting is normalized, drop the original
    -- scraped text (may contain personal data). See AI/08_compliance.md.
    if v_output_table = 'job_postings' then
        update queue set raw_data = null where id = p_id;
    end if;
end;
$$;

-- Delete stale price_history / job_postings rows and their associated queue
-- rows (analyzed/rejected only). Returns the total number of rows deleted.
create or replace function purge_old_data(p_days int default 90)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
    v_total int := 0;
    v_count int;
begin
    delete from price_history where scraped_at < now() - (p_days || ' days')::interval;
    get diagnostics v_count = row_count;
    v_total := v_total + v_count;

    delete from job_postings where scraped_at < now() - (p_days || ' days')::interval;
    get diagnostics v_count = row_count;
    v_total := v_total + v_count;

    delete from queue
    where status in ('analyzed', 'rejected')
      and updated_at < now() - (p_days || ' days')::interval;
    get diagnostics v_count = row_count;
    v_total := v_total + v_count;

    return v_total;
end;
$$;

-- For each enabled task that is "due" (no queue rows yet, or its most recent
-- row is older than schedule_interval_minutes and not raw/in_progress),
-- insert a fresh 'raw' queue row. Returns the number of rows inserted.
create or replace function enqueue_due_tasks(p_default_max_retries int default 3)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
    v_task tasks%rowtype;
    v_last_status text;
    v_last_created_at timestamptz;
    v_inserted int := 0;
begin
    for v_task in select * from tasks where enabled = true loop
        select status, created_at
        into v_last_status, v_last_created_at
        from queue
        where task_id = v_task.task_id
        order by id desc
        limit 1;

        if not found
           or (
               v_last_created_at < now() - (v_task.schedule_interval_minutes || ' minutes')::interval
               and v_last_status not in ('raw', 'in_progress')
           )
        then
            insert into queue (task_id, url, status, priority, max_retries)
            values (v_task.task_id, v_task.target_url, 'raw', 0, p_default_max_retries);
            v_inserted := v_inserted + 1;
        end if;
    end loop;

    return v_inserted;
end;
$$;

-- Recover rows left 'in_progress' by a crashed run: revert to 'raw' if no
-- raw_data was captured yet, or 'ready' if scraping had already completed.
create or replace function reset_stale_in_progress(p_minutes int default 10)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count int;
begin
    update queue
    set status = case when raw_data is null then 'raw' else 'ready' end,
        updated_at = now()
    where status = 'in_progress'
      and updated_at < now() - (p_minutes || ' minutes')::interval;

    get diagnostics v_count = row_count;
    return v_count;
end;
$$;

-- ============================================================================
-- Read-only views for the dashboard (anon key)
-- ============================================================================

create or replace view v_pipeline_status as
select status, count(*) as count
from queue
group by status;

create or replace view v_price_history as
select
    product_name,
    brand,
    category,
    price,
    currency,
    in_stock,
    source_url,
    scraped_at
from price_history;

create or replace view v_job_postings as
select
    job_title,
    company,
    seniority,
    tech_stack,
    salary_min,
    salary_max,
    currency,
    location,
    remote,
    source_url,
    scraped_at
from job_postings;

-- ============================================================================
-- Security: RLS on base tables, anon access only via the views above
-- ============================================================================

alter table tasks enable row level security;
alter table queue enable row level security;
alter table price_history enable row level security;
alter table job_postings enable row level security;

-- No policies are defined for anon/authenticated on base tables: the worker
-- uses the service role key, which bypasses RLS entirely.

-- RLS bypass does not imply table grants: the worker (service_role) still
-- needs explicit privileges for direct PostgREST table access (e.g.
-- db.get_task()'s SELECT on tasks), since "automatically expose new tables"
-- is disabled for this project.
grant select, insert, update, delete on tasks, queue, price_history, job_postings to service_role;
grant usage, select on all sequences in schema public to service_role;

grant select on v_pipeline_status to anon;
grant select on v_price_history to anon;
grant select on v_job_postings to anon;
