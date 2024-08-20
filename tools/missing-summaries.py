import psycopg2
import openai
from psycopg2.extras import RealDictCursor
import time
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Database connection parameters
DB_PARAMS = {
    "dbname": "brainstorm2",
    "user": "massimo",
    "password": "Mc96256coj1!",
    "host": "cheshirecatai.ddns.net",
    "port": "5432"
}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def connect_to_db():
    return psycopg2.connect(**DB_PARAMS)

def get_conversations_without_summary():
    with connect_to_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT c.id, c.topic, c.title
                FROM conversations c
                LEFT JOIN summary s ON c.id = s.conversation_id
                WHERE s.id IS NULL
                ORDER BY c.timestamp DESC
            """)
            return cur.fetchall()

def get_messages_for_conversation(conversation_id):
    with connect_to_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT speaker, message
                FROM messages
                WHERE conversation_id = %s
                ORDER BY timestamp ASC
            """, (conversation_id,))
            return cur.fetchall()

def generate_summary(conversation):
    messages = get_messages_for_conversation(conversation['id'])
    conversation_text = "\n".join([f"{msg['speaker']}: {msg['message']}" for msg in messages])
    
    prompt = f"Please summarize the following conversation about {conversation['topic']}:\n\n{conversation_text}\n\nSummary:"
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes conversations."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150
    )
    
    return response.choices[0].message.content.strip()

def ensure_unique_constraint():
    with connect_to_db() as conn:
        with conn.cursor() as cur:
            # Check if the constraint exists
            cur.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'summary'
                AND constraint_type = 'UNIQUE'
                AND constraint_name = 'summary_conversation_id_key'
            """)
            if not cur.fetchone():
                # If the constraint doesn't exist, create it
                cur.execute("""
                    ALTER TABLE summary
                    ADD CONSTRAINT summary_conversation_id_key UNIQUE (conversation_id)
                """)
                conn.commit()
                print("Added unique constraint to summary table.")

def save_summary(conversation_id, topic, title, summary):
    with connect_to_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO summary (conversation_id, topic, title, summary)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (conversation_id) DO UPDATE
                SET summary = EXCLUDED.summary, topic = EXCLUDED.topic, title = EXCLUDED.title
            """, (conversation_id, topic, title, summary))
        conn.commit()

def main():
    # Ensure the unique constraint exists
    ensure_unique_constraint()

    conversations = get_conversations_without_summary()
    total = len(conversations)
    
    for i, conversation in enumerate(conversations, 1):
        print(f"Processing conversation {i} of {total} (ID: {conversation['id']})")
        
        try:
            summary = generate_summary(conversation)
            title = conversation.get('title') or f"Summary of {conversation['topic']}"
            save_summary(conversation['id'], conversation['topic'], title, summary)
            print(f"Summary generated and saved for conversation {conversation['id']}")
        except Exception as e:
            print(f"Error processing conversation {conversation['id']}: {str(e)}")
        
        # Sleep to avoid rate limiting
        time.sleep(1)

if __name__ == "__main__":
    main()