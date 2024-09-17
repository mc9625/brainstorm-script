import requests
import json
import sys
import argparse
import re
import logging

OLLAMA_URL = "http://aibook.nuvolaproject.cloud:11434/api/chat"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_json_string(json_string):
    """
    Clean and prepare the JSON string for proper parsing.
    """
    # Replace smart quotes with standard quotes
    json_string = json_string.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    
    # Remove backslashes preceding double quotes (escape sequences)
    json_string = re.sub(r'\\+"', '"', json_string)  # Replace escaped quotes with regular quotes
    
    # Fix JSON keys and values (ensure quotes are consistent)
    json_string = re.sub(r'"([a-zA-Z0-9_]+)":', r'"\1":', json_string)

    # Remove trailing commas before } or ]
    json_string = re.sub(r',(\s*[}\]])', r'\1', json_string)

    return json_string.strip()

def is_valid_json(json_str):
    """
    Validates if a string is a valid JSON.
    """
    try:
        json.loads(json_str)
        return True
    except ValueError:
        return False

def extract_personalities_from_text(content):
    """
    Extracts bot personalities from text using regular expressions.
    """
    # Regular expressions to find the prompts and bios
    bot1_prompt_match = re.search(r'bot1_prompt\s*:\s*"(.*?)"', content, re.DOTALL | re.IGNORECASE)
    bot1_bio_match = re.search(r'bot1_bio\s*:\s*"(.*?)"', content, re.DOTALL | re.IGNORECASE)
    bot2_prompt_match = re.search(r'bot2_prompt\s*:\s*"(.*?)"', content, re.DOTALL | re.IGNORECASE)
    bot2_bio_match = re.search(r'bot2_bio\s*:\s*"(.*?)"', content, re.DOTALL | re.IGNORECASE)

    personalities = {}

    if bot1_prompt_match:
        personalities['bot1_prompt'] = bot1_prompt_match.group(1).strip()
    if bot1_bio_match:
        personalities['bot1_bio'] = bot1_bio_match.group(1).strip()
    if bot2_prompt_match:
        personalities['bot2_prompt'] = bot2_prompt_match.group(1).strip()
    if bot2_bio_match:
        personalities['bot2_bio'] = bot2_bio_match.group(1).strip()

    # Check if all required keys are present
    required_keys = ['bot1_prompt', 'bot1_bio', 'bot2_prompt', 'bot2_bio']
    if all(key in personalities for key in required_keys):
        return personalities
    else:
        return None

def generate_bot_personalities(topic, language="eng"):
    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        if language == "ita":
            prompt = f"""
Crea due personalità contrastanti di bot AI per una discussione su "{topic}" in italiano.
Per ciascun bot, fornisci:
1. Un breve prompt che descriva la loro prospettiva e lo stile di comunicazione (2-3 frasi)
2. Una concisa biografia che includa il loro background e competenze (3-4 frasi)

Assicurati che le personalità siano:
- Fortemente contrastanti nelle loro opinioni e stili di comunicazione
- Rilevanti per l'argomento di "{topic}"
- Realistiche nel loro approccio, evitando un linguaggio eccessivamente entusiasta o elogiativo
- Competenti ma con punti di vista distinti che possono portare a disaccordi
- I due bot non devono mai avere una identitá sessuale (es. maschio o femmina) e non avere mai nomi propri

IMPORTANTE:
- Usa le virgolette doppie `"` per tutte le chiavi e valori delle stringhe.
- Non includere virgole finali.
- Assicurati che l'intera risposta sia un oggetto JSON ben formattato e analizzabile.

Esempio di formato:
{{
  "bot1_prompt": "Bot 1 è un ingegnere pragmatico...",
  "bot1_bio": "Bot 1 ha lavorato nell'ingegneria sostenibile per decenni...",
  "bot2_prompt": "Bot 2 è un attivista entusiasta...",
  "bot2_bio": "Bot 2 ha dedicato la sua vita a sensibilizzare..."
}}
"""
            system_content = "Sei un assistente AI incaricato di creare personalità contrastanti di bot per le discussioni in italiano."
        else:
            prompt = f"""
Create two contrasting AI bot personalities for a discussion about "{topic}" in English.
For each bot, provide:
1. A brief prompt describing their perspective and communication style (2-3 sentences)
2. A concise bio including their background and expertise (3-4 sentences)

Ensure the personalities are:
- Strongly contrasting in their views and communication styles
- Relevant to the topic of "{topic}"
- Realistic in their approach, avoiding overly enthusiastic or complimentary language
- Knowledgeable but with distinct viewpoints that may lead to disagreement
- The two personalities should never ever have a gender (es. male or female) and never have a name

IMPORTANT:
- Use double quotes `"` for all keys and string values.
- Do not include any trailing commas.
- Ensure that the entire response is a well-formatted and parsable JSON object.

Example format:
{{
  "bot1_prompt": "Bot 1 is a pragmatic engineer...",
  "bot1_bio": "Bot 1 has worked in sustainable engineering for decades...",
  "bot2_prompt": "Bot 2 is an enthusiastic activist...",
  "bot2_bio": "Bot 2 has dedicated their life to raising awareness..."
}}
"""
            system_content = "You are an AI assistant tasked with creating contrasting bot personalities for discussions in English."

        data = {
            "model": "gemma2:2b",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.7,
                "max_tokens": 500
            }
        }
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(OLLAMA_URL, headers=headers, json=data)
            if response.status_code == 200:
                content = response.json()['message']['content']
                logger.info(f"Attempt {attempt}: Raw content from Ollama:\n{content}\n")
                
                # Clean the JSON
                content = clean_json_string(content)
                
                # Extract only the JSON part
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_content = content[json_start:json_end]
                    if is_valid_json(json_content):
                        try:
                            personalities = json.loads(json_content)
                            # Check that all required keys are present
                            required_keys = ['bot1_prompt', 'bot1_bio', 'bot2_prompt', 'bot2_bio']
                            if all(key in personalities for key in required_keys):
                                logger.info("Successfully parsed bot personalities JSON.")
                                return personalities
                            else:
                                logger.error("Error: Missing required keys in the generated personalities")
                        except json.JSONDecodeError as e:
                            logger.error(f"Error decoding JSON: {e}")
                            logger.error(f"Content causing the error: {json_content}")
                    else:
                        logger.warning("Invalid JSON received. Attempting to extract data from text.")
                        # Attempt to extract personalities from text
                        personalities = extract_personalities_from_text(content)
                        if personalities:
                            logger.info("Successfully extracted bot personalities from text.")
                            return personalities
                        else:
                            logger.error("Failed to extract bot personalities from text.")
                else:
                    logger.error("Error: Could not find valid JSON in the response")
                    # Attempt to extract personalities from text
                    personalities = extract_personalities_from_text(content)
                    if personalities:
                        logger.info("Successfully extracted bot personalities from text.")
                        return personalities
                    else:
                        logger.error("Failed to extract bot personalities from text.")
            else:
                logger.error(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error generating bot personalities: {e}")

        if attempt == MAX_RETRIES:
            logger.error("Max retries reached. Using default bot personalities.")
            break

    # Fallback to default bot personalities
    if language == "ita":
        default_data = {
            "bot1_prompt": f"Bot 1 è un esperto in {topic}. Fornisci approfondimenti dettagliati.",
            "bot1_bio": f"Bot 1 ha una vasta esperienza in {topic}.",
            "bot2_prompt": f"Bot 2 ha una prospettiva diversa su {topic}. Ingaggia in un dibattito riflessivo.",
            "bot2_bio": f"Bot 2 offre punti di vista alternativi su {topic}, incoraggiando il pensiero critico."
        }
    else:
        default_data = {
            "bot1_prompt": f"Bot 1 is an expert on {topic}. Provide detailed insights.",
            "bot1_bio": f"Bot 1 has extensive experience in {topic}.",
            "bot2_prompt": f"Bot 2 has a different perspective on {topic}. Engage in thoughtful debate.",
            "bot2_bio": f"Bot 2 offers alternative views on {topic}, encouraging critical thinking."
        }
    return default_data

def print_personalities(personalities, language="eng"):
    if personalities:
        for bot in ['bot1', 'bot2']:
            print(f"\n{bot.upper()}:")
            if language == "ita":
                print(f"Prompt: {personalities[f'{bot}_prompt']}")
                print(f"Biografia: {personalities[f'{bot}_bio']}")
            else:
                print(f"Prompt: {personalities[f'{bot}_prompt']}")
                print(f"Bio: {personalities[f'{bot}_bio']}")
    else:
        if language == "ita":
            print("Impossibile generare le personalità.")
        else:
            print("Failed to generate personalities.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate bot personalities")
    parser.add_argument("topic", help="The topic for the conversation")
    parser.add_argument("--language", default="eng", choices=["eng", "ita"], help="Language for the personalities (eng or ita)")
    args = parser.parse_args()

    if args.language == "ita":
        print(f"Generazione di personalità per l'argomento: {args.topic} in {args.language}\n")
    else:
        print(f"Generating personalities for topic: {args.topic} in {args.language}\n")
    
    personalities = generate_bot_personalities(args.topic, args.language)
    print_personalities(personalities, args.language)
