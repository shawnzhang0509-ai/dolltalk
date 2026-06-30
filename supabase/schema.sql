-- DollWorldwide / DollTalk
-- 在 Supabase Dashboard → SQL Editor 粘贴运行即可，零额外部署
-- 本地 YAML 字段与此表一一对应，后期迁移只需改 image_path → image_url

create extension if not exists "pgcrypto";

-- 娃娃
create table if not exists dolls (
  id          uuid primary key default gen_random_uuid(),
  slug        text unique not null,
  name        text not null,
  personality text,
  default_scale real default 0.5,
  created_at  timestamptz default now()
);

-- 娃娃姿势图
create table if not exists doll_poses (
  id         uuid primary key default gen_random_uuid(),
  doll_id    uuid not null references dolls(id) on delete cascade,
  sort_order int not null default 0,
  image_url  text not null,
  unique (doll_id, sort_order)
);

-- 背景
create table if not exists backgrounds (
  id         uuid primary key default gen_random_uuid(),
  slug       text unique not null,
  name       text not null,
  tags       text[] default '{}',
  image_url  text not null,
  created_at timestamptz default now()
);

-- 剧集
create table if not exists dramas (
  id         uuid primary key default gen_random_uuid(),
  title      text not null,
  doll_id    uuid not null references dolls(id),
  status     text not null default 'draft'
             check (status in ('draft', 'rendering', 'done', 'failed')),
  created_at timestamptz default now()
);

-- 场景（一幕）
create table if not exists scenes (
  id            uuid primary key default gen_random_uuid(),
  drama_id      uuid not null references dramas(id) on delete cascade,
  sort_order    int not null,
  background_id uuid not null references backgrounds(id),
  title         text,
  unique (drama_id, sort_order)
);

-- 台词节拍（一帧）
create table if not exists beats (
  id         uuid primary key default gen_random_uuid(),
  scene_id   uuid not null references scenes(id) on delete cascade,
  sort_order int not null,
  start_sec  int not null,
  end_sec    int not null,
  subtitle   text not null default '',
  position   text not null default 'center'
             check (position in ('center', 'left', 'right')),
  scale      real not null default 0.5,
  pose_index int not null default 0,
  unique (scene_id, sort_order)
);

-- 渲染任务（后期 Worker 轮询此表）
create table if not exists render_jobs (
  id         uuid primary key default gen_random_uuid(),
  drama_id   uuid not null references dramas(id) on delete cascade,
  status     text not null default 'pending'
             check (status in ('pending', 'running', 'done', 'failed')),
  output_url text,
  error      text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_scenes_drama on scenes(drama_id);
create index if not exists idx_beats_scene on beats(scene_id);
create index if not exists idx_render_jobs_status on render_jobs(status);

-- 开发阶段开放读写；上线前在 Supabase 配置 RLS
alter table dolls enable row level security;
alter table doll_poses enable row level security;
alter table backgrounds enable row level security;
alter table dramas enable row level security;
alter table scenes enable row level security;
alter table beats enable row level security;
alter table render_jobs enable row level security;

create policy "dev_all_dolls" on dolls for all using (true) with check (true);
create policy "dev_all_doll_poses" on doll_poses for all using (true) with check (true);
create policy "dev_all_backgrounds" on backgrounds for all using (true) with check (true);
create policy "dev_all_dramas" on dramas for all using (true) with check (true);
create policy "dev_all_scenes" on scenes for all using (true) with check (true);
create policy "dev_all_beats" on beats for all using (true) with check (true);
create policy "dev_all_render_jobs" on render_jobs for all using (true) with check (true);
