-- Offing : classement du Défi du jour
-- À exécuter une fois dans Supabase : SQL Editor > New query > coller > Run
-- Accès : uniquement via les fonctions Vercel (clé secrète). RLS activée sans policy = aucun accès avec la clé publique.

create extension if not exists pgcrypto;

-- Joueurs (pseudo + empreinte du jeton secret gardé dans le navigateur)
create table if not exists public.players (
  id          uuid primary key default gen_random_uuid(),
  name        text not null check (char_length(name) between 3 and 20),
  token_hash  text not null,
  ip_hash     text,
  created_at  timestamptz not null default now()
);
create unique index if not exists players_name_ci on public.players (lower(name));
create index if not exists players_ip_day on public.players (ip_hash, created_at);

-- Meilleur chrono vérifié par joueur, jour, parcours et classe (+ trace fantôme et journal d'ordres)
create table if not exists public.bests (
  player_id   uuid not null references public.players(id) on delete cascade,
  day         date not null,
  course      text not null,
  cls         text not null,
  time_s      integer not null check (time_s > 0),
  pens        smallint not null default 0,
  engine      smallint not null,
  attempts    integer not null default 1,
  trace       jsonb not null,
  log         jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  primary key (player_id, day, course, cls)
);
create index if not exists bests_board on public.bests (day, course, cls, time_s);

alter table public.players enable row level security;
alter table public.bests   enable row level security;
revoke all on public.players, public.bests from anon, authenticated;

-- Enregistre un essai : garde le meilleur temps, compte les envois (atomique)
create or replace function public.submit_best(
  p_player uuid, p_day date, p_course text, p_cls text,
  p_time integer, p_pens integer, p_engine integer, p_trace jsonb, p_log jsonb
) returns table (improved boolean, best integer, attempts integer)
language plpgsql security definer set search_path = public as $$
declare cur record;
begin
  select b.time_s, b.attempts into cur from bests b
   where b.player_id = p_player and b.day = p_day and b.course = p_course and b.cls = p_cls for update;
  if not found then
    insert into bests (player_id, day, course, cls, time_s, pens, engine, trace, log)
    values (p_player, p_day, p_course, p_cls, p_time, p_pens, p_engine, p_trace, p_log);
    return query select true, p_time, 1;
  elsif p_time < cur.time_s then
    update bests set time_s = p_time, pens = p_pens, engine = p_engine, trace = p_trace, log = p_log,
           attempts = cur.attempts + 1, updated_at = now()
     where player_id = p_player and day = p_day and course = p_course and cls = p_cls;
    return query select true, p_time, cur.attempts + 1;
  else
    update bests set attempts = cur.attempts + 1, updated_at = now()
     where player_id = p_player and day = p_day and course = p_course and cls = p_cls;
    return query select false, cur.time_s, cur.attempts + 1;
  end if;
end $$;
revoke execute on function public.submit_best from public, anon, authenticated;

-- Ménage quotidien (appelé par le cron Vercel)
create or replace function public.purge_old(p_keep_days integer default 30)
returns integer language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  -- journaux d'ordres gardés 14 jours (preuve), traces et chronos gardés p_keep_days jours
  update bests set log = null where log is not null and day < current_date - 14;
  delete from bests where day < current_date - p_keep_days;
  get diagnostics n = row_count;
  return n;
end $$;
revoke execute on function public.purge_old from public, anon, authenticated;
