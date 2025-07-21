import requests
import json
from typing import Dict, Any, Optional
import re
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ATCMessageProcessor:
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434/api/chat",
                 model: str = "gemma3:4b"):
        self.ollama_url = ollama_url
        self.model = model

    def generate_classification_prompt(self, message: str, sender_type: str = "AUTO") -> str:
        """Generate the classification prompt for the ATC message."""
        if sender_type == "AUTO":
            sender_instruction = "1. Determine if the message is from a PILOT or from ATC (Air Traffic Control). ATC messages often contain instructions, clearances, or information directed at an aircraft (e.g., 'cleared for takeoff', 'squawk 7700', 'contact tower'). Pilot messages are often read-backs of instructions, requests, or reports (e.g., 'ready for departure', 'requesting higher altitude', 'Mayday')."
            response_instruction = "4. Provide appropriate response (if from PILOT, give ATC response; if from ATC, give PILOT response)"
        elif sender_type == "PILOT":
            sender_instruction = "1. This message is from a PILOT"
            response_instruction = "4. Provide appropriate ATC response to this pilot message"
        else:  # ATC
            sender_instruction = "1. This message is from ATC (Air Traffic Control)"
            response_instruction = "4. Provide appropriate PILOT response to this ATC message"

        return f"""
You are an ATC Message Classification System. Analyze this aviation communication message and classify it.

Message: "{message}"
Sender Type: {sender_type}

Your task:
{sender_instruction}
2. Classify the message type (EMERGENCY, NORMAL, WEATHER, TRAFFIC, etc.)
3. Extract key information (aircraft ID, runway, altitude, etc.)
{response_instruction}

PILOT RESPONSE FORMAT:
ALways put flight number at the end while generating flight response.
When generating a PILOT response, it must be a concise read-back of the key instruction. It should not be a long sentence.
The flight number should come at end (this is must).
If you do not know the answer just say COPY along with flight number.
For example:

- ATC: Airbus AI101 San Francisco Tower. Altimeter 2992 Make straight in.
- PILOT: Fly straight in runway 28R Airbus AI101.
- ATC: Cessna VT-YSU Approach Squawk 4307
- PILOT: Squawk 4307 Cessna YSU
- ATC: N300EP radio check
- PILOT:N300EP 5 by 5
- ATC: Boeing BA202 Altimeter 2992 departure to the west approved.
- PILOT: Cleared for takeoff runway 28R
- ATC: Delta 789, contact departure on 121.9.
- PILOT: Copied Delta 789.
- ATC: United 456, climb and maintain one zero thousand feet.
- PILOT: Climbing to one zero thousand, United 456.
- ATC: Southwest 123, turn right heading two five zero.
- PILOT: Right heading two five zero, Southwest 123.
- ATC: American 789, hold short of runway two eight right.
- PILOT: Holding short two eight right, American 789.
-ATC:N350KA you are off course Correct and resume own navigation
-PILOT:Correcting and resuming own navigation N350KA
-ATC:N750BG you are off course Correct and resume own navigation
-PILOT:Correcting and resuming own navigation N750BG

Respond in this exact format:
SENDER: [PILOT/ATC]
TYPE: [EMERGENCY/NORMAL/WEATHER/TRAFFIC/NAVIGATION/FUEL/RUNWAY/COMMUNICATION]
AIRCRAFT: [Call sign if mentioned]
DETAILS: [Brief description]
RESPONSE: [Appropriate response - ATC response if sender is PILOT, PILOT response if sender is ATC]
"""

    def call_ollama_api(self, prompt: str) -> Optional[str]:
        """Make API call to Ollama and return the response."""
        logger.info(f"Making API call to: {self.ollama_url}")
        logger.info(f"Using model: {self.model}")
        logger.info(f"Prompt length: {len(prompt)} characters")

        try:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False
            }

            logger.info(f"Payload prepared: {json.dumps(payload, indent=2)[:500]}...")

            response = requests.post(
                self.ollama_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            logger.info(f"Response status code: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Response JSON keys: {list(result.keys())}")
                content = result.get("message", {}).get("content", "")
                logger.info(f"Content length: {len(content)} characters")
                logger.info(f"Content preview: {content[:200]}...")
                return content
            else:
                error_msg = f"Error: HTTP {response.status_code} - {response.text}"
                logger.error(error_msg)
                return error_msg

        except requests.exceptions.RequestException as e:
            error_msg = f"Connection Error: {str(e)}"
            logger.error(error_msg)
            return error_msg
        except json.JSONDecodeError as e:
            error_msg = f"JSON Error: {str(e)}"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Unexpected Error: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def parse_response(self, response: str) -> Dict[str, str]:
        """Parse the structured response from the AI model."""
        logger.info(f"Parsing response of length: {len(response) if response else 0}")
        logger.info(f"Response content: {response[:500]}...")

        parsed = {
            "sender": "Unknown",
            "type": "Unknown",
            "aircraft": "Not specified",
            "details": "No details provided",
            "response": "No response generated"
        }

        if not response or "Error:" in response:
            parsed["details"] = response or "No response received"
            logger.warning(f"No valid response to parse: {response}")
            return parsed

        # Extract information using regex
        patterns = {
            "sender": r"SENDER:\s*(.+?)(?:\n|$)",
            "type": r"TYPE:\s*(.+?)(?:\n|$)",
            "aircraft": r"AIRCRAFT:\s*(.+?)(?:\n|$)",
            "details": r"DETAILS:\s*(.+?)(?:\n|RESPONSE:|$)",
            "response": r"RESPONSE:\s*(.+?)(?:\n|$)"
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                if value and value != "[Not specified]" and value != "N/A":
                    parsed[key] = value
                    logger.info(f"Extracted {key}: {value}")

        logger.info(f"Final parsed data: {parsed}")
        return parsed

    def classify_message(self, message: str, sender_type: str = "AUTO") -> Dict[str, Any]:
        """Main method to classify an ATC message."""
        logger.info(f"Starting message classification for: '{message[:100]}...'")
        logger.info(f"Sender type specified: {sender_type}")

        if not message.strip():
            logger.warning("Empty message provided")
            return {
                "success": False,
                "error": "Please enter a message to classify",
                "data": {}
            }

        # Generate prompt
        logger.info("Generating classification prompt")
        prompt = self.generate_classification_prompt(message, sender_type)
        logger.info(f"Generated prompt length: {len(prompt)}")

        # Call Ollama API
        logger.info("Calling Ollama API")
        raw_response = self.call_ollama_api(prompt)
        logger.info(f"Received raw response: {raw_response is not None}")

        if raw_response is None:
            logger.error("No response from Ollama API")
            return {
                "success": False,
                "error": "No response from Ollama API",
                "data": {}
            }

        # Parse response
        logger.info("Parsing response")
        parsed_data = self.parse_response(raw_response)

        logger.info("Classification completed successfully")
        return {
            "success": True,
            "error": None,
            "data": parsed_data,
            "raw_response": raw_response
        }

    def get_message_examples(self) -> Dict[str, Dict[str, str]]:
        """Return example ATC messages for testing."""
        return {
            "Emergency (Pilot)": {
                "message": "Mayday, Mayday, Mayday, Airbus A320, engine fire, returning to airport.",
                "sender": "PILOT"
            },
            "Normal Request (Pilot)": {
                "message": "San Francisco Tower, United 456, ready for takeoff runway 28R.",
                "sender": "PILOT"
            },
            "Weather Request (Pilot)": {
                "message": "Approach, Delta 890, request weather at destination.",
                "sender": "PILOT"
            },
            "Fuel Priority (Pilot)": {
                "message": "Declaring minimum fuel, JetBlue 456, need priority handling.",
                "sender": "PILOT"
            },
            "Runway Clearance (ATC)": {
                "message": "United 456, runway 28R, cleared for takeoff.",
                "sender": "ATC"
            },
            "Traffic Alert (ATC)": {
                "message": "Southwest 123, traffic, 2 o'clock, 5 miles, Boeing 737.",
                "sender": "ATC"
            },
            "Landing Clearance (ATC)": {
                "message": "United 456, cleared to land runway 09L.",
                "sender": "ATC"
            },
            "Frequency Change (ATC)": {
                "message": "Delta 789, contact departure on 121.9.",
                "sender": "ATC"
            }
        }

    def validate_connection(self) -> Dict[str, Any]:
        """Test connection to Ollama API."""
        logger.info("Testing connection to Ollama")
        logger.info(f"URL: {self.ollama_url}")
        logger.info(f"Model: {self.model}")

        try:
            test_payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False
            }

            logger.info("Sending test request")
            response = requests.post(
                self.ollama_url,
                json=test_payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            logger.info(f"Test response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Test response keys: {list(result.keys())}")
                logger.info("Connection test successful")
                return {"success": True, "message": "Connection successful"}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Connection test failed: {error_msg}")
                return {"success": False, "message": error_msg}

        except Exception as e:
            error_msg = f"Connection failed: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}