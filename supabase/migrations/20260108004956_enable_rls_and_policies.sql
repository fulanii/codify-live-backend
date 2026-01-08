-- Enable RLS
alter table profiles enable row level security;
alter table friendships enable row level security;
alter table friendships_requests enable row level security;
alter table conversations enable row level security;
alter table conversation_members enable row level security;
alter table messages enable row level security;

-- PROFILES
create policy "public usernames readable"
on profiles for select using (true);

create policy "user manages own profile"
on profiles for update using (auth.uid() = id);

-- FRIENDSHIPS
create policy "friend reads friendship"
on friendships for select using (
  auth.uid() = user1_id or auth.uid() = user2_id
);

create policy "friend deletes friendship"
on friendships for delete using (
  auth.uid() = user1_id or auth.uid() = user2_id
);

-- FRIEND REQUESTS
create policy "sender or receiver can view request"
on friendships_requests
for select using (
  auth.uid() = sender_id or auth.uid() = receiver_id
);

create policy "sender creates request"
on friendships_requests
for insert with check (
  auth.uid() = sender_id
);

create policy "receiver updates request"
on friendships_requests
for update using (
  auth.uid() = receiver_id
);

-- CONVERSATIONS
create policy "member sees conversation"
on conversations for select using (
  exists (
    select 1 from conversation_members m
    where m.conversation_id = id
    and m.user_id = auth.uid()
  )
);

-- CONVERSATION MEMBERS
create policy "user sees own memberships"
on conversation_members for select using (
  user_id = auth.uid()
);

-- MESSAGES
create policy "members read messages"
on messages for select using (
  exists (
    select 1 from conversation_members m
    where m.conversation_id = conversation_id
    and m.user_id = auth.uid()
  )
);

create policy "members send messages"
on messages for insert with check (
  exists (
    select 1 from conversation_members m
    where m.conversation_id = conversation_id
    and m.user_id = auth.uid()
  )
);
