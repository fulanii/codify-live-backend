from sqlalchemy import Column, Integer, String

friendship_request_sql = """
CREATE TYPE Mystatus AS ENUM ('Pending', 'Accepted', 'Declined', 'Cancelled');

create table friendships_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  sender_id  uuid references auth.users(id) on delete cascade,
  receiver_id  uuid references auth.users(id) on delete cascade,

  status Mystatus NOT NULL,
  
  created_at timestamp with time zone default now(),
  
  -- 1. Essential: Prevent A -> B from being sent twice by A
  CONSTRAINT unique_request_pair UNIQUE (sender_id, receiver_id),
  
  -- 2. Good Practice: Prevent a user from sending a request to themselves
  CONSTRAINT prevent_self_request CHECK (sender_id <> receiver_id)
);
"""

friendships_sql = """
CREATE TABLE friendships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user1_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    user2_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Prevent duplicates by enforcing canonical ordering
    CONSTRAINT user1_less_than_user2 CHECK (user1_id < user2_id),

    -- Prevent (A,B) OR (B,A) duplicates
    CONSTRAINT unique_friend_pair UNIQUE (user1_id, user2_id)
);
"""
