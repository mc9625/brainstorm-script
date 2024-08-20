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

def get_summaries_without_haiku():
    with connect_to_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT s.id, s.conversation_id, s.topic, s.summary
                FROM summary s
                WHERE s.haiku IS NULL OR s.haiku = ''
                ORDER BY s.id DESC
            """)
            return cur.fetchall()

def generate_haiku(summary):
    prompt = f"""Based on the following summary, create a haiku that strictly adheres to the traditional 5-7-5 syllable structure.
The haiku should evoke a moment in nature or a reflection on a season, with a clear juxtaposition or contrast between two images or ideas. 
Ensure the haiku is inspired by the content of the summary below:

Summary:
{summary}

Haiku:"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a poetic assistant that creates haikus based on summaries."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=50
    )
    
    return response.choices[0].message.content.strip()

def save_haiku(summary_id, haiku):
    with connect_to_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE summary
                SET haiku = %s
                WHERE id = %s
            """, (haiku, summary_id))
        conn.commit()

def main():
    summaries = get_summaries_without_haiku()
    total = len(summaries)
    
    for i, summary in enumerate(summaries, 1):
        print(f"Processing summary {i} of {total} (ID: {summary['id']})")
        
        try:
            haiku = generate_haiku(summary['summary'])
            save_haiku(summary['id'], haiku)
            print(f"Haiku generated and saved for summary ID {summary['id']}")
            print(f"Haiku: {haiku}")
        except Exception as e:
            print(f"Error processing summary {summary['id']}: {str(e)}")
        
        # Sleep to avoid rate limiting
        time.sleep(1)

if __name__ == "__main__":
    main()