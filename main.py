import time
import random
import subprocess
from datetime import datetime, time as dtime, timedelta
from utils import run_chatbot, print_memory_usage, get_prompt
from postgres_operations import start_new_conversation, save_message_to_postgres, get_last_response, get_latest_user_message, get_and_remove_latest_user_message, get_bot_status, set_bot_status, get_bot_personality
import psycopg2
from psycopg2 import pool
import requests
import json
import paho.mqtt.client as mqtt
from postgres_operations import get_bot_personality
import argparse
from bot_personality_generator import generate_bot_personalities

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

def save_bot_personalities(conversation_id, bot1_prompt, bot1_bio, bot2_prompt, bot2_bio):
    connection = connection_pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO bot_personalities (conversation_id, bot_number, prompt, description)
                VALUES (%s, 1, %s, %s), (%s, 2, %s, %s)
            """, (conversation_id, bot1_prompt, bot1_bio, conversation_id, bot2_prompt, bot2_bio))
        connection.commit()
        print(f"Bot personalities saved for conversation {conversation_id}")
    except Exception as e:
        print(f"An error occurred while saving bot personalities: {e}")
        connection.rollback()
    finally:
        connection_pool.putconn(connection)

def get_topics(language):
    if language == "ita":
        return [
            "energie rinnovabili", "pianificazione urbana", "neutralità carbonica",
            "conservazione dell'acqua", "adattamento al cambiamento climatico",
            "edifici verdi", "trasporto sostenibile", "politica ambientale",
            "impronta ecologica", "gestione dei rifiuti", "Internet delle cose (IoT)",
            "tecnologia pulita", "economia circolare", "agricoltura sostenibile",
            "conservazione della biodiversità", "miglioramento della qualità dell'aria",
            "efficienza energetica", "case intelligenti", "turismo sostenibile",
            "infrastrutture verdi"
        ]
    else:
        return [
            "renewable energy", "urban planning", "carbon neutrality",
            "water conservation", "climate change adaptation", "green buildings",
            "sustainable transportation", "environmental policy", "ecological footprint",
            "waste management", "Internet of Things (IoT)", "clean technology",
            "circular economy", "sustainable agriculture", "biodiversity conservation",
            "air quality improvement", "energy efficiency", "smart homes",
            "sustainable tourism", "green infrastructure"
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

def on_disconnect(client, userdata, rc):
    print("Disconnected with result code "+str(rc))
    while True:
        try:
            client.reconnect()
            break
        except:
            print("Reconnection failed, retrying in 3 seconds")
            time.sleep(3)

mqtt_client.on_disconnect = on_disconnect

def process_chatbot_response(chatbot_name, prompt, topic, conversation_id, counter, conversation_history, language):
    print(f"Asking {chatbot_name}: {prompt}")
    
    bot_number = 1 if chatbot_name == "AI1" else 2
    system_message, bot_bio = get_bot_personality(conversation_id, bot_number, language)
    
    if not system_message:
        system_message = f"You are an AI assistant discussing {topic}. Respond with short, concise sentences."
        bot_bio = "You are an AI with general knowledge."

    # Pubblica lo stato 'speaking' sul topic AI1/status o AI2/status
    mqtt_client.publish(f"{chatbot_name}/status", "speaking")
    print(f"Published 'speaking' to {chatbot_name}/status")

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
    8. Respond in {'Italian' if language == 'ita' else 'English'}.
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
            # Pubblica lo stato 'stop' sul topic AI1/status o AI2/status
            mqtt_client.publish(f"{chatbot_name}/status", "stop")
            print(f"Published 'stop' to {chatbot_name}/status")
            
            # Update MQTT feed (replacing Adafruit)
            mqtt_client.publish(f'conversations/{conversation_id}', json.dumps({"speaker": chatbot_name, "message": output}))
            
            return output
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return get_prompt(topic, language)
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return get_prompt(topic, language)

def is_within_work_hours():
    current_time = datetime.now().time()
    start_time = dtime(hour=21, minute=0)
    end_time = dtime(hour=9, minute=0)
    if start_time < end_time:
        return start_time <= current_time < end_time
    else:
        return current_time >= start_time or current_time < end_time

def analyze_user_message(message, conversation_history, topic, language):
    prompt = f"""
    Analyze this message: "{message}"
    
    Is it coherent with the ongoing discussion about "{topic}"?
    Conversation history: {conversation_history}
    
    If it's coherent and not offensive, respond with a JSON:
    {{"analysis": "good"}}
    
    If it's not coherent and not offensive, respond with a JSON:
    {{"analysis": "no good"}}

    If it's offensive, respond with a JSON:
    {{"analysis": "bad"}}

    Respond in {'Italian' if language == 'ita' else 'English'}.
    """

    headers = {"Content-Type": "application/json"}
    data = {
        "model": "gemma2:2b",
        "messages": [
            {"role": "system", "content": "You are an assistant for message analysis."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, headers=headers, json=data)
        if response.status_code == 200:
            content = response.json()['message']['content']
            # Cerchiamo di estrarre solo la parte JSON dalla risposta
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_content = content[json_start:json_end]
                result = json.loads(json_content)
                return result
            else:
                print(f"Risposta non valida da Ollama: {content}")
                return {"analysis": "bad", "message": "Errore nell'analisi del messaggio"}
        else:
            print(f"Errore nella richiesta a Ollama: {response.status_code} - {response.text}")
            return {"analysis": "bad", "message": "Errore nella richiesta a Ollama"}
    except json.JSONDecodeError as e:
        print(f"Errore nel parsing JSON: {e}")
        print(f"Contenuto che ha causato l'errore: {content}")
        return {"analysis": "bad", "message": "Errore nel parsing della risposta"}
    except Exception as e:
        print(f"Errore nell'analisi del messaggio utente: {e}")
        return {"analysis": "bad", "message": "Errore generico nell'analisi del messaggio"}

def handle_user_message(message, conversation_id, conversation_history, topic, language):
    analysis = analyze_user_message(message, conversation_history, topic, language)
    
    print(f"Analisi del messaggio utente: {analysis}")
    
    if analysis['analysis'] == 'good':
        save_message_to_postgres(conversation_id, 'User', message)
        prompt = message
        return True, None, prompt  # Restituisce sempre tre valori
    else:
        system_message = "Il messaggio non è pertinente alla discussione." if analysis['analysis'] == 'bad' else "Il messaggio non è valido."
        save_message_to_postgres(conversation_id, 'System', system_message)
        return False, system_message, None

def main(language):
    global counter
    counter = 0  # Inizializza il contatore
    CONVERSATION_LENGTH = 10  # Definisci la lunghezza della conversazione
    topics = get_topics(language)
    topic = random.choice(topics)
    if language == "ita":
        prompt = f"Iniziamo una conversazione interessante su {topic} ed esploriamo nuove prospettive?"
        title = f"Brainstorming su {topic} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    else:
        prompt = f"How about diving into a captivating conversation about {topic} and exploring fresh perspectives?"
        title = f"Brainstorming on {topic} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

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

    conversation_id = start_new_conversation(topic, prompt, conversation, language)
    if conversation_id is None:
        print("Failed to start a new conversation. Exiting.")
        return

    """ # Genera le personalità dei bot
    personalities = generate_bot_personalities(topic, language)
    if personalities:
        save_bot_personalities(conversation_id, personalities['bot1_prompt'], personalities['bot1_bio'],
                               personalities['bot2_prompt'], personalities['bot2_bio'])
    else:
        print("Failed to generate bot personalities. Using default prompts.")
        save_bot_personalities(conversation_id,
                               "You are an AI assistant discussing the topic.",
                               "You are an AI with general knowledge.",
                               "You are an AI assistant discussing the topic.",
                               "You are an AI with general knowledge.")
 """
    conversation_history = []
    last_user_message = None

    while True:
        if get_bot_status() != "awake":
            set_bot_status("awake")
        print("Good morning! Let's start a new conversation.")
        print(f"Conversation ID: {conversation_id}")
        
        user_message = get_and_remove_latest_user_message(conversation_id)
        if user_message and len(user_message.strip()) > 0 and user_message != last_user_message:
            print(f"User: {user_message}")
            is_valid, system_message, user_prompt = handle_user_message(user_message, conversation_id, conversation_history, topic, language)
            if not is_valid:  # Se il messaggio non è valido, ignora e continua
                continue
            if system_message:  # Se c'è un messaggio di sistema, mostralo
                conversation_history.append({"speaker": "System", "message": system_message})
            if user_prompt:  # Se il messaggio è valido, invialo come prompt al bot
                conversation_history.append({"speaker": "User", "message": user_message})
                prompt = user_prompt
                last_user_message = user_message 

        
        bot1_prompt, bot1_bio = get_bot_personality(conversation_id, 1, language)
        print(f"\nAI1 Personality: {bot1_prompt}")
        response1 = process_chatbot_response("AI1", prompt, topic, conversation_id, counter, conversation_history, language)
        conversation_history.append({"speaker": "AI1", "message": response1})
        
        bot2_prompt, bot2_bio = get_bot_personality(conversation_id, 2, language)
        print(f"\nAI2 Personality: {bot2_prompt}")
        response2 = process_chatbot_response("AI2", response1, topic, conversation_id, counter, conversation_history, language)
        conversation_history.append({"speaker": "AI2", "message": response2})
        prompt = response2

        counter += 1

        if counter % CONVERSATION_LENGTH == 0:
            counter = 0
            subprocess.call(["python3", "new_conversation_summary.py", "--conversation_id", str(conversation_id), "--language", language])

            topics = get_topics(language)  # Aggiorna la lista dei topic
            topic = random.choice(topics)
            if language == "ita":
                prompt = f"Che ne dici di immergerci in una conversazione avvincente su {topic} ed esplorare nuove prospettive?"
            else:
                prompt = f"How about diving into a captivating conversation about {topic} and exploring fresh perspectives?"
            
            print(f"New Prompt: {prompt}")

            conversation = {
                "title": f"Brainstorming on {topic} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "dialogue": []
            }
            conversation_id = start_new_conversation(topic, prompt, conversation, language)
            conversation_history = []  # Reset conversation history for new topic
            last_user_message = None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an AI conversation")
    parser.add_argument("language", nargs="?", default="eng", choices=["eng", "ita"], help="Language for the conversation (eng or ita)")
    parser.add_argument("--conversation_id", type=int, help="ID of the existing conversation")
    parser.add_argument("--user_message", help="Message from the user")
    args = parser.parse_args()

    if args.conversation_id and args.user_message:
        print(f"Processing user message for conversation {args.conversation_id}")
        handle_user_message(args.user_message, args.conversation_id, args.language)
    else:
        print(f"Starting conversation in {args.language}...")
        main(args.language)