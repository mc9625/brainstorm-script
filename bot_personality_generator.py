import requests
import json
import sys

OLLAMA_URL = "http://aibook.nuvolaproject.cloud:11434/api/chat"

def generate_bot_personalities(topic):
    headers = {"Content-Type": "application/json"}
    prompt = f"""
    Create two contrasting AI bot personalities for a discussion about {topic}. 
    For each bot, provide:
    1. A brief prompt describing their perspective and communication style (2-3 sentences)
    2. A concise bio including their background and expertise (3-4 sentences)
    
    Ensure the personalities are:
    - Strongly contrasting in their views and communication styles
    - Relevant to the topic of {topic}
    - Realistic in their approach, avoiding overly enthusiastic or complimentary language
    - Knowledgeable but with distinct viewpoints that may lead to disagreement
    
    Format the response as a JSON object with keys: bot1_prompt, bot1_bio, bot2_prompt, bot2_bio
    Do not include any markdown formatting or code block indicators in your response.
    """

    data = {
        "model": "gemma2:2b",
        "messages": [
            {"role": "system", "content": "You are an AI assistant tasked with creating contrasting bot personalities for discussions."},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "max_tokens": 500
        }
    }

    try:
        response = requests.post(OLLAMA_URL, headers=headers, json=data)
        if response.status_code == 200:
            content = response.json()['message']['content']
            print(f"Raw content from Ollama:\n{content}\n")  # Debug print
            
            # Remove any markdown formatting if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.endswith("```"):
                content = content[:-3]  # Remove ```
            content = content.strip()
            
            try:
                personalities = json.loads(content)
                return personalities
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Content causing the error: {content}")
                return None
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error generating bot personalities: {e}")
        return None

def print_personalities(personalities):
    if personalities:
        for bot in ['bot1', 'bot2']:
            print(f"\n{bot.upper()}:")
            print(f"Prompt: {personalities[f'{bot}_prompt']}")
            print(f"Bio: {personalities[f'{bot}_bio']}")
    else:
        print("Failed to generate personalities.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python bot_personality_generator.py \"topic\"")
        sys.exit(1)
    
    topic = sys.argv[1]
    print(f"Generating personalities for topic: {topic}\n")
    personalities = generate_bot_personalities(topic)
    print_personalities(personalities)