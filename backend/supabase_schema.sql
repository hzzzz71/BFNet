create extension if not exists pgcrypto;

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create table if not exists patients (
  id text primary key default gen_random_uuid()::text,
  name varchar(100) not null,
  gender varchar(10),
  age integer,
  phone varchar(20),
  medical_history text,
  allergies text,
  family_history text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists patients add column if not exists allergies text;
alter table if exists patients add column if not exists family_history text;

create index if not exists idx_patients_name on patients (name);

drop trigger if exists trg_patients_updated_at on patients;
create trigger trg_patients_updated_at
before update on patients
for each row
execute function set_updated_at();

create table if not exists examinations (
  id text primary key default gen_random_uuid()::text,
  patient_id text not null references patients(id),
  exam_date timestamptz not null,
  exam_type varchar(50) default 'colonoscopy',
  image_path varchar(500),
  result_path varchar(500),
  report_path varchar(500),
  polyp_count integer default 0,
  risk_level varchar(20),
  pathology_type varchar(100),
  recommended_followup integer,
  llm_analysis jsonb,
  doctor_notes text,
  created_at timestamptz not null default now()
);

create index if not exists idx_examinations_patient_id on examinations (patient_id);
create index if not exists idx_examinations_exam_date on examinations (exam_date desc);

create table if not exists polyps (
  id text primary key default gen_random_uuid()::text,
  examination_id text not null references examinations(id) on delete cascade,
  polyp_number integer,
  location varchar(200),
  size_mm numeric(5,2),
  boundary_score numeric(3,2),
  shape_type varchar(50),
  surface_pattern varchar(100),
  pathology_pred varchar(100),
  confidence_score numeric(3,2),
  bbox_coords jsonb
);

create index if not exists idx_polyps_examination_id on polyps (examination_id);

create table if not exists followup_plans (
  id text primary key default gen_random_uuid()::text,
  patient_id text not null references patients(id),
  examination_id text not null references examinations(id),
  next_exam_date timestamptz not null,
  status varchar(20) default 'pending',
  reminder_sent boolean default false,
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists idx_followup_plans_patient_id on followup_plans (patient_id);
create index if not exists idx_followup_plans_examination_id on followup_plans (examination_id);
