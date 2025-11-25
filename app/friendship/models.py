from sqlalchemy import Column, Integer, String

friendship_sql = """
CREATE TYPE Mystatus AS ENUM ('Pending', 'Accepted', 'Declined', 'Cancelled');

create table friend_requests (
  id uuid primary key,
  sender_id  uuid references auth.users(id) on delete cascade,
  receiver_id  uuid references auth.users(id) on delete cascade,
  status Mystatus NOT NULL,
  created_at timestamp with time zone default now()
);
"""


class Item:
    __tablename__ = "friend_requests"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = ...
    receiver_id = ...
    status = ...
    created_at = ...
    updated_at = ...
