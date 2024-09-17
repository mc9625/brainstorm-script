# newchatbot1.py

import argparse
import requests
import json
import random
import difflib
from postgres_operations import save_message_to_postgres, get_last_messages
import utils
import paho.mqtt.client as mqtt
from postgres_operations import get_bot_personality

# Ollama server URL
OLLAMA_URL = "http://aibook.nuvolaproject.cloud:11434/api/chat"

# MQTT broker parameters
MQTT_BROKER = "cheshirecatai.ddns.net"
MQTT_PORT = 1883

# Initialize MQTT client
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()  # Aggiungi questa linea

def is_too_similar(text1, text2, threshold=0.6):
    """Returns True if the texts are too similar, False otherwise."""
    s = difflib.SequenceMatcher(None, text1, text2)
    return s.ratio() > threshold

def generate_response(prompt, topic, conversation_id, counter, last_message, conversation_history, language):
    headers = {"Content-Type": "application/json"}
    bot_number = 1  # Use 2 for newchatbot2.py
    system_message, bot_bio = get_bot_personality(conversation_id, bot_number, language)
    
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
    6. Consider the context of the conversation and directly address points made in previous messages.
    7. Respond in {'Italian' if language == 'ita' else 'English'}.
    """

    messages = [
        {"role": "system", "content": full_system_message},
    ]
    
    # Add conversation history
    for msg in conversation_history[-5:]:  # Include last 5 messages for context
        messages.append({"role": "user" if msg['speaker'] != f"AI{bot_number}" else "assistant", "content": msg['message']})
    
    messages.append({"role": "user", "content": prompt})

    data = {
        "model": "gemma2:2b",
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "max_tokens": 60
        }
    }
    try:
        response = requests.post(OLLAMA_URL, headers=headers, json=data)
        if response.status_code == 200:
            output = response.json()['message']['content']
            
            # Check for similarity with last AI2 message
            if last_ai2_message and is_too_similar(output, last_ai2_message):
                output = utils.get_prompt(topic)
                print("ATTENTION: Repeated response from newchatbot1.py.")
            
            return output
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return utils.get_prompt(topic)
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return utils.get_prompt(topic)

def main():
    parser = argparse.ArgumentParser(description='Chatbot 1')
    parser.add_argument('--prompt', required=True, help='The conversation prompt')
    parser.add_argument('--topic', required=True, help='The conversation topic')
    parser.add_argument('--conversation_id', required=True, help='The ID of the current conversation')
    parser.add_argument('--counter', required=True, help='The counter of the current conversation')
    args = parser.parse_args()

    counter = int(args.counter)

    # Get the last messages from AI1 and AI2
    last_ai1_message, last_ai2_message = get_last_messages(args.conversation_id) if counter != 0 else ("", "")

    # Generate the response
    response = generate_response(args.prompt, args.topic, args.conversation_id, counter, last_ai2_message)

    # Update MQTT feeds
    mqtt_client.publish("AI1/status", 'speaking')
    print("Published 'speaking' to AI1/status", flush=True)
    
    # Print the AI's response to stdout
    print(f"AI1 dice:{response}")

    # Save the message to PostgreSQL
    save_message_to_postgres(args.conversation_id, "AI1", response)

    # Publish message to MQTT
    mqtt_client.publish(f'conversations/{args.conversation_id}', json.dumps({"speaker": "AI1", "message": response}))

    # Update MQTT feeds to 'stop' after speaking
    mqtt_client.publish("AI1/status", 'stop')

if __name__ == "__main__":
    main()
    mqtt_client.loop_stop()  # Ferma il loop di rete
    mqtt_client.disconnect()  # Disconnette il client