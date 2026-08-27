-- Sincroniza phone/name/full_name/email de auth.users (raw_user_meta_data)
-- para public.profiles automaticamente a cada novo cadastro.
--
-- Hoje o signup() em auth.py manda phone/name/full_name só como metadata
-- do supabase.auth.sign_up() (vira auth.users.raw_user_meta_data). Sem
-- este trigger, public.profiles.phone/name nunca são preenchidos e:
--   - alertas.py não encontra telefone e não envia WhatsApp (falha
--     silenciosa, só loga "Sem telefone para user ...")
--   - dashboard.py e auth.py (get_display_name) caem no fallback via
--     user_metadata em vez de usar o profile
--
-- Rodar manualmente no Supabase SQL Editor (não há deploy automático de
-- migrations neste projeto).

-- 1) Garante que as colunas existem (idempotente).
alter table public.profiles add column if not exists phone text;
alter table public.profiles add column if not exists name text;
alter table public.profiles add column if not exists full_name text;
alter table public.profiles add column if not exists email text;

-- 1b) Verificação defensiva: o "on conflict (id)" do passo 2 exige uma
--     PRIMARY KEY ou UNIQUE constraint cobrindo exatamente a coluna id.
--     Sem isso, o INSERT do trigger quebra (ou pior, deixa de detectar
--     conflito) toda vez que um usuário se cadastra. Aborta a migration
--     inteira com uma mensagem clara em vez de falhar silenciosamente
--     mais adiante.
do $$
begin
  if not exists (
    select 1
    from pg_constraint c
    join pg_class t      on t.oid = c.conrelid
    join pg_namespace n  on n.oid = t.relnamespace
    where n.nspname = 'public'
      and t.relname = 'profiles'
      and c.contype in ('p', 'u')          -- primary key ou unique
      and c.conkey = array[
        (select attnum from pg_attribute
         where attrelid = t.oid and attname = 'id')
      ]
  ) then
    raise exception
      'public.profiles não tem PRIMARY KEY/UNIQUE em "id". '
      'Rode antes: alter table public.profiles add primary key (id); '
      '(ou adicione uma constraint unique em id) e execute esta migration de novo.';
  end if;
end;
$$;

-- 2) Função + trigger: preenche public.profiles quando um usuário novo é
--    criado em auth.users. security definer é necessário porque o INSERT
--    em auth.users roda como supabase_auth_admin, que não tem acesso a
--    public.profiles por padrão.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, name, full_name, phone)
  values (
    new.id,
    new.email,
    new.raw_user_meta_data ->> 'name',
    new.raw_user_meta_data ->> 'full_name',
    new.raw_user_meta_data ->> 'phone'
  )
  on conflict (id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

-- 3) Backfill: usuários que já se cadastraram antes deste trigger existir
--    e que ficaram com profiles.phone/name vazios.
update public.profiles p
set
  phone     = coalesce(nullif(p.phone, ''), u.raw_user_meta_data ->> 'phone'),
  name      = coalesce(nullif(p.name, ''), u.raw_user_meta_data ->> 'name'),
  full_name = coalesce(nullif(p.full_name, ''), u.raw_user_meta_data ->> 'full_name'),
  email     = coalesce(p.email, u.email)
from auth.users u
where p.id = u.id
  and (
    coalesce(nullif(p.phone, ''), '') = ''
    or coalesce(nullif(p.name, ''), '') = ''
    or p.email is null
  );
