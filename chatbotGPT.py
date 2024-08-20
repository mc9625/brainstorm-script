# chatbotGPT.py

import argparse
import requests
import json
from postgres_operations import save_message_to_postgres, get_last_messages
import utils
from langdetect import detect
import paho.mqtt.client as mqtt

# Ollama server URL
OLLAMA_URL = "http://aibook.nuvolaproject.cloud:11434/api/chat"

# MQTT broker parameters
MQTT_BROKER = "cheshirecatai.ddns.net"
MQTT_PORT = 1883

# Initialize MQTT client
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

def update_mqtt_feeds(status):
    mqtt_client.publish("AI1/status", status)
    mqtt_client.publish("AI2/status", status)

def generate_ollama_response(system_content, user_content):
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "gemma2:2b",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "max_tokens": 150
        }
    }

    try:
        response = requests.post(OLLAMA_URL, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['message']['content']
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return None

def generate_ontopic_response(topic, prompt):
    return generate_ollama_response(
        f"You are an AI that determines if a prompt is on-topic with respect to {topic}. Respond with 'yes' or 'no'.",
        prompt
    )

def generate_translation(prompt):
    return generate_ollama_response(
        "You are a translator. Translate the following text to English if it's not already in English. If it's already in English, return it as is.",
        prompt
    )

def generate_answer(topic, prompt):
    return generate_ollama_response(
        f"You are an AI assistant knowledgeable about {topic}. Provide a helpful response to the following prompt.",
        prompt
    )

def process_user_response(args, counter):
    ontopic = generate_ontopic_response(args.topic, args.prompt)
    
    if detect(args.prompt) != 'en':
        translation = generate_translation(args.prompt)
    else:
        translation = args.prompt
    
    answer = generate_answer(args.topic, translation)   

    # Save messages to PostgreSQL
    save_message_to_postgres(args.conversation_id, "User", translation)
    save_message_to_postgres(args.conversation_id, "AI1", answer)

    # Update MQTT feed
    mqtt_client.publish(f'conversations/{args.conversation_id}', json.dumps({"speaker": "User", "message": translation}))
    mqtt_client.publish(f'conversations/{args.conversation_id}', json.dumps({"speaker": "AI1", "message": answer}))

    # Update controls (replace this with appropriate PostgreSQL operation if needed)
    # For now, we'll just print a message
    print("User message processed. Ready for next message.")

    return translation, answer

def main():
    parser = argparse.ArgumentParser(description='ChatbotGPT')
    parser.add_argument('--prompt', required=True, help='The conversation prompt')
    parser.add_argument('--topic', required=True, help='The conversation topic')
    parser.add_argument('--conversation_id', required=True, help='The ID of the current conversation')
    parser.add_argument('--counter', required=True, help='The counter of the current conversation')
    args = parser.parse_args()

    counter = int(args.counter)

    # Update MQTT feeds
    update_mqtt_feeds('happy')

    # Process user response
    translation, answer = process_user_response(args, counter)
    
    print(f"User (translated if needed): {translation}")
    print(f"AI1: {answer}")

if __name__ == "__main__":
    main()