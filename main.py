import time
import random
import subprocess
from datetime import datetime, time as dtime, timedelta
from utils import run_chatbot, print_memory_usage, get_prompt
from postgres_operations import start_new_conversation, save_message_to_postgres, get_last_response, get_and_remove_latest_user_message, get_bot_status, set_bot_status
import psycopg2
from psycopg2 import pool
import requests
import json
import paho.mqtt.client as mqtt
from postgres_operations import get_bot_personality

# PostgreSQL connection details
DB_PARAMS = {
    "dbname": "brainstorm2",
    "user": "massimo",
    "password": "Mc96256coj1!",
    "host": "cheshirecatai.ddns.net",
    "port": "5432"
}

# PostgreSQL connection pool
try:
    connection_pool = psycopg2.pool.SimpleConnectionPool(
        1, 20,
        **DB_PARAMS
    )
    if connection_pool:
        print("PostgreSQL connection pool created successfully")

except (Exception, psycopg2.Error) as error:
    print("Error while connecting to PostgreSQL", error)

# Ollama server URL
OLLAMA_URL = "http://aibook.nuvolaproject.cloud:11434/api/chat"

backup_topics = [
    "renewable energy",
    "urban planning",
    "carbon neutrality",
    "water conservation",
    "climate change adaptation",
    "green buildings",
    "sustainable transportation",
    "environmental policy",
    "ecological footprint",
    "waste management",
    "Internet of Things IoT",
    "clean technology",
    "circular economy",
    "sustainable agriculture",
    "biodiversity conservation",
    "air quality improvement",
    "energy efficiency",
    "smart homes",
    "sustainable tourism",
    "green infrastructure"
]

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
    else:
        print(f"Failed to connect, return code {rc}")

# MQTT broker parameters
MQTT_BROKER = "cheshirecatai.ddns.net"
MQTT_PORT = 1883

# Initialize MQTT client
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

print("Attempting to connect to MQTT broker...")

def process_chatbot_response(chatbot_name, prompt, topic, conversation_id, counter, conversation_history):
    print(f"Asking {chatbot_name}: {prompt}")
    
    bot_number = 1 if chatbot_name == "AI1" else 2
    system_message, bot_bio = get_bot_personality(conversation_id, bot_number)
    
    if not system_message:
        system_message = f"You are an AI assistant discussing {topic}. Respond with short, concise sentences."
        bot_bio = "You are an AI with general knowledge."

    full_system_message = f"""
    {system_message}

    Your background: {bot_bio}

    Important instructions:
    1. Keep your responses brief and to the point, ideally 2-3 sentences.
    2. Avoid excessive compliments or enthusiasm. Be more measured in your responses.
    3. Stay true to your personality and background in your communication style.
    4. Focus on providing substantive input related to the topic rather than social niceties.
    5. It's okay to disagree or present contrasting viewpoints when appropriate.
    6. Consider the context of the conversation and avoid repeating information.
    7. Introduce new aspects or ideas related to the topic to keep the conversation engaging.
    """

    headers = {"Content-Type": "application/json"}
    messages = [
        {"role": "system", "content": full_system_message},
    ]
    
    # Add conversation history
    for msg in conversation_history[-5:]:  # Include last 5 messages for context
        messages.append({"role": "user" if msg['speaker'] != chatbot_name else "assistant", "content": msg['message']})
    
    messages.append({"role": "user", "content": prompt})

    data = {
        "model": "gemma2:2b",
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.8,  # Slightly increase temperature for more variety
            "max_tokens": 100  # Reduce max tokens to encourage shorter responses
        }
    }

    try:
        response = requests.post(OLLAMA_URL, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            output = response.json()['message']['content']
            print(f"{chatbot_name}: {output}")
            print_memory_usage()
            
            # Save the message to PostgreSQL
            save_message_to_postgres(conversation_id, chatbot_name, output)
            
            # Update MQTT feed (replacing Adafruit)
            mqtt_client.publish(f'conversations/{conversation_id}', json.dumps({"speaker": chatbot_name, "message": output}))
            
            return output
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return get_prompt(topic)
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return get_prompt(topic)

def is_within_work_hours():
    current_time = datetime.now().time()
    start_time = dtime(hour=21, minute=0)
    end_time = dtime(hour=9, minute=0)
    if start_time < end_time:
        return start_time <= current_time < end_time
    else:
        return current_time >= start_time or current_time < end_time

def main():
    global counter
    counter = 0  # Inizializza il contatore
    CONVERSATION_LENGTH = 10  # Definisci la lunghezza della conversazione
    topic = random.choice(backup_topics)
    prompt = "How about diving into a captivating conversation about " + topic + " and exploring fresh perspectives?"
    print(f"Prompt: {prompt}")

    conversation = {
        "title": f"Brainstorming on {topic} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "dialogue": []
    }

    # Check if tables exist before starting a new conversation
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'conversations')")
            if not cursor.fetchone()[0]:
                print("Tables do not exist. Creating tables...")
                create_tables()
                init_db()
    except Exception as e:
        print(f"An error occurred while checking tables: {e}")
    finally:
        connection_pool.putconn(connection)

    conversation_id = start_new_conversation(topic, prompt, conversation)
    if conversation_id is None:
        print("Failed to start a new conversation. Exiting.")
        return

    conversation_history = []  # Initialize conversation history here

    while True:
        if get_bot_status() != "awake":
            set_bot_status("awake")
        print("Good morning! Let's start a new conversation.")
        print(f"Conversation ID: {conversation_id}")
        
        user_message = get_and_remove_latest_user_message(conversation_id)
        if user_message and len(user_message.strip()) > 0:
            print(f"User: {user_message}")
            responseToUser = process_chatbot_response("User", user_message, topic, conversation_id, counter, conversation_history)
            conversation_history.append({"speaker": "User", "message": responseToUser})
            prompt = responseToUser
        
        bot1_prompt, bot1_bio = get_bot_personality(conversation_id, 1)
        print(f"\nAI1 Personality: {bot1_prompt}")
        response1 = process_chatbot_response("AI1", prompt, topic, conversation_id, counter, conversation_history)
        conversation_history.append({"speaker": "AI1", "message": response1})
        
        user_message = get_and_remove_latest_user_message(conversation_id)
        if user_message and len(user_message.strip()) > 0:
            print(f"User: {user_message}")
            responseToUser = process_chatbot_response("User", user_message, topic, conversation_id, counter, conversation_history)
            conversation_history.append({"speaker": "User", "message": responseToUser})
            prompt = responseToUser
        
        bot2_prompt, bot2_bio = get_bot_personality(conversation_id, 2)
        print(f"\nAI2 Personality: {bot2_prompt}")
        response2 = process_chatbot_response("AI2", response1, topic, conversation_id, counter, conversation_history)
        conversation_history.append({"speaker": "AI2", "message": response2})
        prompt = response2

        counter += 1

        if counter % CONVERSATION_LENGTH == 0:
            counter = 0
            subprocess.call("python3 new_conversation_summary.py", shell=True)

            topic = random.choice(backup_topics)
            prompt = "How about diving into a captivating conversation about " + topic + " and exploring fresh perspectives?"
            print(f"New Prompt: {prompt}")

            conversation = {
                "title": f"Brainstorming on {topic} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "dialogue": []
            }
            conversation_id = start_new_conversation(topic, prompt, conversation)
            conversation_history = []  # Reset conversation history for new topic



if __name__ == "__main__":
    print("Starting backup chatbot...")
    main()
