conversations_sql = """
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    is_group BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now()
);
"""

conversation_members_sql = """
CREATE TABLE conversation_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (conversation_id, user_id)
);
"""

messages_sql = """
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
"""

direct_conversations_sql = """
CREATE TABLE direct_conversations (
    conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,

    user1_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    user2_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    created_at TIMESTAMPTZ DEFAULT now(),

    -- Enforce canonical ordering
    CONSTRAINT user1_less_than_user2 CHECK (user1_id < user2_id),

    -- Ensure only one conversation per user pair
    CONSTRAINT unique_direct_pair UNIQUE (user1_id, user2_id)
);

"""
