import openai
import os
from dotenv import load_dotenv
from datetime import datetime
from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer
import psycopg2
from psycopg2 import pool
import paho.mqtt.client as mqtt
import time
from requests_oauthlib import OAuth1
import requests
import json
import argparse

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# PostgreSQL connection details
DB_PARAMS = {
    "dbname": "brainstorm2",
    "user": "massimo",
    "password": "Mc96256coj1!",
    "host": "cheshirecatai.ddns.net",
    "port": "5432"
}

OLLAMA_URL = "http://aibook.nuvolaproject.cloud:11434/api/chat"

# Create a connection pool
connection_pool = psycopg2.pool.SimpleConnectionPool(1, 20, **DB_PARAMS)

# MQTT broker parameters
MQTT_BROKER = "cheshirecatai.ddns.net"
MQTT_PORT = 1883

# Twitter API credentials
consumer_key = '6URGTLg0Gadcr9anC6lfzHPFn'
consumer_secret = 'LVQ2nWIKbVpibwAJ8GAFz7K82eVkv3j0tMQ0smOyeE3q9MC6If'
access_token = '1488203164499255297-ir1HuhCslnbqa3TQD4NfKOLhmolIJN'
access_token_secret = '0ywutWayGe4RlPi5ELZRfWKVEZbge8C4FZmlPPQsqA3wH'

def connect_to_oauth(consumer_key, consumer_secret, access_token, access_token_secret):
    url = "https://api.twitter.com/2/tweets"
    auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)
    return url, auth

def generate_haiku(summary, language):
    headers = {"Content-Type": "application/json"}
    if language == "ita":
        system_content = "Sei un assistente poetico. Sei in grado di convertire qualsiasi testo in un haiku poetico e ispiratore in italiano."
        user_content = f"""Basandoti sul seguente riassunto, crea un haiku che rispetti rigorosamente la struttura tradizionale di 5-7-5 sillabe.
        L'haiku dovrebbe evocare un momento nella natura o una riflessione su una stagione, con una chiara giustapposizione o contrasto tra due immagini o idee. 
        Assicurati che l'haiku sia ispirato al contenuto del seguente riassunto:

        Riassunto:
        {summary}"""
    else:
        system_content = "You are a poetic assistant. You are able to convert any text into a poetic and inspiring haiku."
        user_content = f"""Based on the following summary, create a haiku that strictly adheres to the traditional 5-7-5 syllable structure.
        The haiku should evoke a moment in nature or a reflection on a season, with a clear juxtaposition or contrast between two images or ideas. 
        Ensure the haiku is inspired by the content of the summary below:

        Summary:
        {summary}"""

    data = {
        "model": "gemma2:2b",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "max_tokens": 50
        }
    }

    try:
        response = requests.post(OLLAMA_URL, headers=headers, json=data)
        if response.status_code == 200:
            haiku = response.json()['message']['content']
        else:
            print(f"Error: {response.status_code} - {response.text}")
            haiku = "Error generating haiku"
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        haiku = "Error generating haiku"

    return haiku

def get_summary_prompt(language):
    if language == "ita":
        return "Scrivi un riassunto conciso e coinvolgente della sessione di brainstorming. Il riassunto dovrebbe essere fluido e discorsivo, evitando elenchi puntati. Concentrati sulla cattura dell'essenza della discussione, evidenziando le intuizioni chiave, le conclusioni e il tono generale della conversazione in una singola narrazione coerente."
    else:
        return "Write a concise and engaging summary of the brainstorming session. The summary should be fluid and discursive, avoiding bullet points or lists. Focus on capturing the essence of the discussion, highlighting key insights, conclusions, and the overall tone of the conversation in a single, coherent narrative."


def generate_hashtags(text, num_hashtags, language):
    if language == "ita":
        stop_words = ['il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'uno', 'una', 'e', 'ed', 'a', 'al', 'alla', 'di', 'da', 'in', 'su', 'per', 'tra', 'fra']
    else:
        stop_words = 'english'

    vectorizer = CountVectorizer(stop_words=stop_words)
    X = vectorizer.fit_transform([text])
    words = vectorizer.get_feature_names_out()
    counts = X.toarray().sum(axis=0)
    word_counts = list(zip(words, counts))
    word_counts.sort(key=lambda x: x[1], reverse=True)
    hashtags = [f"#{word}" for word, _ in word_counts[:num_hashtags]]
    return hashtags

def generate_summarizer(max_tokens, temperature, top_p, frequency_penalty, conversation, topic, conversation_id, language):
    current_time = datetime.now().strftime("%Y%m%d%H%M")
    sanitized_topic = topic.replace(" ", "_").lower()
    title = f"brainstorming-{sanitized_topic}-{current_time}"

    if language == "ita":
        system_content = "Sei un abile scrittore e sintetizzatore. Rispondi in italiano."
        user_content = f"Scrivi un riassunto conciso e coinvolgente della sessione di brainstorming su {topic}. Il riassunto dovrebbe essere fluido e discorsivo, evitando elenchi puntati. Concentrati sulla cattura dell'essenza della discussione, evidenziando le intuizioni chiave, le conclusioni e il tono generale della conversazione in una singola narrazione coerente: {conversation}"
    else:
        system_content = "You are a skilled writer and summarizer."
        user_content = f"Write a concise and engaging summary of the brainstorming session about {topic}. The summary should be fluid and discursive, avoiding bullet points or lists. Focus on capturing the essence of the discussion, highlighting key insights, conclusions, and the overall tone of the conversation in a single, coherent narrative: {conversation}"

    headers = {"Content-Type": "application/json"}
    data = {
        "model": "gemma2:2b",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    }

    try:
        response = requests.post(OLLAMA_URL, headers=headers, json=data)
        if response.status_code == 200:
            summary = response.json()['message']['content']
        else:
            print(f"Error: {response.status_code} - {response.text}")
            summary = "Error generating summary"
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        summary = "Error generating summary"

    hashtags = generate_hashtags(summary, 5, language)
    haiku = generate_haiku(summary, language)  # Passa il parametro 'language' qui

    final_summary = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "topic": topic,
        "summary": summary,
        "hashtags": hashtags,
        "haiku": haiku,
        "title": title,
        "conversation_id": conversation_id,
    }

    # Write the summary and haiku to PostgreSQL
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO summary (date, topic, summary, hashtags, title, conversation_id, haiku)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (conversation_id) DO UPDATE
                SET summary = EXCLUDED.summary,
                    hashtags = EXCLUDED.hashtags,
                    haiku = EXCLUDED.haiku,
                    date = EXCLUDED.date
            """, (
                final_summary["date"],
                final_summary["topic"],
                final_summary["summary"],
                ','.join(final_summary["hashtags"]),
                final_summary["title"],
                final_summary["conversation_id"],
                final_summary["haiku"]
            ))
        connection.commit()
        print(f"Summary and haiku inserted/updated for conversation ID {conversation_id}")
    except Exception as e:
        print(f"Error inserting/updating summary and haiku: {e}")
        connection.rollback()
    finally:
        connection_pool.putconn(connection)

    return final_summary

def post_tweet(text, hashtags, topic):
    try:
        if len(text) <= 280:
            tweet_text = f"{text} {hashtags[0]} {hashtags[1]} #{topic.replace(' ', '')}"
            payload = {"text": tweet_text}
            url, auth = connect_to_oauth(consumer_key, consumer_secret, access_token, access_token_secret)
            response = requests.post(
                auth=auth, url=url, json=payload, headers={"Content-Type": "application/json"}
            )
            print("Status code:", response.status_code)
            print("Response:", response.text)
        else:
            tweets = [text[i:i + 280] for i in range(0, len(text), 280)]
            for i, tweet in enumerate(tweets):
                tweet_text = f"{tweet} {hashtags[0]} {hashtags[1]} #{topic.replace(' ', '')}"
                payload = {"text": tweet_text}
                url, auth = connect_to_oauth(consumer_key, consumer_secret, access_token, access_token_secret)
                response = requests.post(
                    auth=auth, url=url, json=payload, headers={"Content-Type": "application/json"}
                )
                print(f"Tweet {i+1}/{len(tweets)}")
                print("Status code:", response.status_code)
                print("Response:", response.text)
    except Exception as e:
        print(f"Error posting tweet: {str(e)}")

def main(conversation_id, language):
    # Get the last conversation from PostgreSQL
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.id, c.topic, string_agg(m.message, ' ' ORDER BY m.timestamp) as conversation_text
                FROM conversations c
                JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id, c.topic
                ORDER BY c.timestamp DESC
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                conversation_id, topic, conversation_text = result
            else:
                print("No conversations found.")
                return
    finally:
        connection_pool.putconn(connection)

    # Generate the summary, haiku, and hashtags
    summary_prompt = get_summary_prompt(language)
    summary = generate_summarizer(
        max_tokens=300,
        temperature=0.7,
        top_p=0.5,
        frequency_penalty=0.5,
        conversation=conversation_text,
        topic=topic,
        conversation_id=conversation_id,
        language=language  # Aggiungi questa riga
    )

    # Publish haiku to MQTT
    mqtt_client = mqtt.Client()
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.publish('conversations/haiku', json.dumps({"haiku": summary["haiku"]}))
    mqtt_client.disconnect()

    print(summary["haiku"])

    # Post tweet every 4th summary
    global tweet_counter
    if tweet_counter % 4 == 0:
        post_tweet(summary["haiku"], summary['hashtags'], summary['topic'])
    tweet_counter += 1

    print(summary)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a conversation summary")
    parser.add_argument("--conversation_id", required=True, help="The ID of the conversation to summarize")
    parser.add_argument("--language", default="eng", choices=["eng", "ita"], help="Language of the summary (eng or ita)")
    args = parser.parse_args()
    tweet_counter = 0
    main(args.conversation_id, args.language)
