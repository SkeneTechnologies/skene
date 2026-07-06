CREATE TABLE users (id uuid PRIMARY KEY, email text NOT NULL);
CREATE TABLE invites (id uuid PRIMARY KEY, sender_id uuid REFERENCES users(id));
