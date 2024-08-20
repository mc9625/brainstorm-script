# postgres_operations.py

import psycopg2
from psycopg2 import pool
from datetime import datetime
from bot_personality_generator import generate_bot_personalities

# Use the same DB_PARAMS as in main.py
DB_PARAMS = {
    "dbname": "brainstorm2",
    "user": "massimo",
    "password": "Mc96256coj1!",
    "host": "cheshirecatai.ddns.net",
    "port": "5432"
}

# Create a connection pool
connection_pool = psycopg2.pool.SimpleConnectionPool(1, 20, **DB_PARAMS)

def create_tables():
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            # Create conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Conversations table created")

            # Create messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER NOT NULL,
                    speaker TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Messages table created")

            # Create summary table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summary (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER REFERENCES conversations(id),
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    topic TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    hashtags TEXT,
                    title TEXT NOT NULL,
                    haiku TEXT
                )
            """)
            print("Summary table created")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_personalities (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER REFERENCES conversations(id),
                    bot_number INTEGER CHECK (bot_number IN (1, 2)),
                    prompt TEXT NOT NULL,
                    description TEXT NOT NULL
                )
            """)
            print("Bot personalities table created")

            # Add foreign key constraint only if it doesn't already exist
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints
                        WHERE constraint_type='FOREIGN KEY' AND constraint_name='fk_conversation'
                    ) THEN
                        ALTER TABLE messages 
                        ADD CONSTRAINT fk_conversation
                        FOREIGN KEY (conversation_id) 
                        REFERENCES conversations(id);
                    END IF;
                END $$;
            """)
            print("Foreign key constraint added to messages table (if not exists)")

            connection.commit()
    except Exception as e:
        print(f"An error occurred while creating tables: {e}")
        connection.rollback()
    finally:
        connection_pool.putconn(connection)

def save_bot_personalities(conversation_id, bot1_prompt, bot1_description, bot2_prompt, bot2_description):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO bot_personalities (conversation_id, bot_number, prompt, description)
                VALUES (%s, 1, %s, %s), (%s, 2, %s, %s)
            """, (conversation_id, bot1_prompt, bot1_description, conversation_id, bot2_prompt, bot2_description))
        connection.commit()
        print(f"Bot personalities saved for conversation {conversation_id}")
    except Exception as e:
        print(f"An error occurred while saving bot personalities: {e}")
        connection.rollback()
    finally:
        connection_pool.putconn(connection)

def get_bot_personality(conversation_id, bot_number):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT prompt, description
                FROM bot_personalities
                WHERE conversation_id = %s AND bot_number = %s
            """, (conversation_id, bot_number))
            result = cursor.fetchone()
            return result if result else (None, None)
    finally:
        connection_pool.putconn(connection)

def init_db():
    create_tables()
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            # Initialize counters if not already initialized
            cursor.execute("INSERT INTO counters (total_conversations, total_messages) VALUES (0, 0) ON CONFLICT DO NOTHING")
            # Initialize controls if not already initialized
            cursor.execute("INSERT INTO controls (user_message_sent) VALUES (false) ON CONFLICT DO NOTHING")
        connection.commit()
        print("Database initialized successfully")
    except Exception as e:
        print(f"An error occurred during database initialization: {e}")
        connection.rollback()
    finally:
        connection_pool.putconn(connection)

# Add this function to ensure bot_status table exists
def ensure_bot_status_table():
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_status (
                    id SERIAL PRIMARY KEY,
                    status TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        connection.commit()
        print("Bot status table checked/created")
    except Exception as e:
        print(f"An error occurred while ensuring bot_status table: {e}")
        connection.rollback()
    finally:
        connection_pool.putconn(connection)


def start_new_conversation(topic, prompt, conversation):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO conversations (title, topic) VALUES (%s, %s) RETURNING id",
                (conversation['title'], topic)
            )
            conversation_id = cursor.fetchone()[0]
            
            cursor.execute(
                "INSERT INTO messages (conversation_id, speaker, message) VALUES (%s, %s, %s)",
                (conversation_id, "AI0", prompt)
            )
            
            # Update counters
            cursor.execute("UPDATE counters SET total_conversations = total_conversations + 1, total_messages = total_messages + 1")

        # Commit the conversation and initial message
        connection.commit()
        print(f"New conversation started with id: {conversation_id}")

        # Generate and save bot personalities after committing the conversation
        personalities = generate_bot_personalities(topic)
        if personalities:
            save_bot_personalities(conversation_id, 
                                   personalities['bot1_prompt'], personalities['bot1_bio'],
                                   personalities['bot2_prompt'], personalities['bot2_bio'])
        else:
            print("Failed to generate bot personalities. Using default prompts.")
            save_bot_personalities(conversation_id,
                                   "You are an AI assistant discussing the topic.",
                                   "You are an AI with general knowledge.",
                                   "You are an AI assistant discussing the topic.",
                                   "You are an AI with general knowledge.")

        return conversation_id
    except Exception as e:
        print(f"An error occurred while starting a new conversation: {e}")
        connection.rollback()
        return None
    finally:
        connection_pool.putconn(connection)

def save_bot_personalities(conversation_id, bot1_prompt, bot1_description, bot2_prompt, bot2_description):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO bot_personalities (conversation_id, bot_number, prompt, description)
                VALUES (%s, 1, %s, %s), (%s, 2, %s, %s)
            """, (conversation_id, bot1_prompt, bot1_description, conversation_id, bot2_prompt, bot2_description))
        connection.commit()
        print(f"Bot personalities saved for conversation {conversation_id}")
    except Exception as e:
        print(f"An error occurred while saving bot personalities: {e}")
        connection.rollback()
    finally:
        connection_pool.putconn(connection)

def get_bot_status():
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT status FROM bot_status ORDER BY timestamp DESC LIMIT 1")
            result = cursor.fetchone()
            return result[0] if result else "asleep"
    finally:
        connection_pool.putconn(connection)

def set_bot_status(status):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO bot_status (status, timestamp) VALUES (%s, NOW())", (status,))
        connection.commit()
    finally:
        connection_pool.putconn(connection)


def save_message_to_postgres(conversation_id, speaker, message):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO messages (conversation_id, speaker, message) VALUES (%s, %s, %s)",
                (conversation_id, speaker, message)
            )
        connection.commit()
    finally:
        connection_pool.putconn(connection)

def get_last_response(conversation_id, speaker):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT message FROM messages WHERE conversation_id = %s AND speaker = %s ORDER BY timestamp DESC LIMIT 1",
                (conversation_id, speaker)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    finally:
        connection_pool.putconn(connection)

def get_and_remove_latest_user_message(conversation_id):
    if conversation_id is None:
        print("Error: conversation_id is None")
        return None

    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            # Check if the messages table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'messages'
                )
            """)
            if not cursor.fetchone()[0]:
                print("Messages table does not exist. Creating it now.")
                init_db()
                return None

            cursor.execute(
                "SELECT id, message FROM messages WHERE conversation_id = %s AND speaker = 'User' ORDER BY timestamp DESC LIMIT 1",
                (conversation_id,)
            )
            result = cursor.fetchone()
            if result:
                message_id, message = result
                cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
                connection.commit()
                return message
            return None
    except Exception as e:
        print(f"An error occurred while getting/removing user message: {e}")
        connection.rollback()
        return None
    finally:
        connection_pool.putconn(connection)

def get_last_n_messages(conversation_id, n=5):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT speaker, message FROM messages WHERE conversation_id = %s ORDER BY timestamp DESC LIMIT %s",
                (conversation_id, n)
            )
            return cursor.fetchall()
    finally:
        connection_pool.putconn(connection)

def get_recent_conversations(limit=10):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, topic, created_at FROM conversations ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            return cursor.fetchall()
    finally:
        connection_pool.putconn(connection)

# Call this function before init_db()
create_tables()
init_db()
ensure_bot_status_table()


