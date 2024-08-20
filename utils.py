# utils.py

import psutil
import requests
import json
from textblob import TextBlob
import random

# Ollama server URL
OLLAMA_URL = "http://aibook.nuvolaproject.cloud:11434/api/chat"

# Define your list of backup topics and prompts
backup_topics = ["green economy", "global warming", "smart city", "sustainability", "smart grid"]
backup_prompts = ["Can you elaborate on that?", "What do you think about the current situation?", "How can we improve this?"]

def generate_ngrams(text, n):
    words = text.split()
    ngrams = set()
    for i in range(len(words) - n + 1):
        ngram = tuple(words[i:i+n])
        ngrams.add(ngram)
    return ngrams

def get_prompt(topic):
    topic_prompts = [f"What are your thoughts on {topic}?", f"How can we apply {topic} in our daily life?", f"What are the challenges and opportunities in {topic}?", f"How can {topic} change the world for the better?"]
    all_prompts = backup_prompts + topic_prompts
    return random.choice(all_prompts)

def determine_mood(prompt):
    moods = ["positive", "neutral", "angry"]
    current_mood = "neutral"
    if prompt:
        sentiment = TextBlob(prompt).sentiment.polarity
        if sentiment > 0.5:
            current_mood = "positive"
        elif sentiment < -0.5:
            current_mood = "angry"
    if random.random() < 0.3:
        moods.remove(current_mood)
        current_mood = random.choice(moods)
    return current_mood

def print_memory_usage():
    memory_info = psutil.virtual_memory()
    print('Percent of memory used: ', memory_info.percent)

def run_chatbot(chatbot_name, prompt, topic, conversation_id, counter):
    print(f"utils.py Running {chatbot_name}...")
    print_memory_usage()
    
    system_message = ""
    if chatbot_name == "AI1":
        system_message = "You are an optimistic futurist. You believe in the power of technology to solve global problems. Respond with short, concise sentences."
    else:  # AI2
        system_message = "You are a cautious skeptic. You're concerned about the unintended consequences of new technologies. Respond with short, concise sentences."

    headers = {"Content-Type": "application/json"}
    data = {
        "model": "gemma2:2b",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
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
            output = response.json()['message']['content']
            return output
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return get_prompt(topic)
    except requests.exceptions.RequestException as e:
        print(f"Connection error: {e}")
        return get_prompt(topic)

# Remove the generate_response_gpt function as we're now using Ollama