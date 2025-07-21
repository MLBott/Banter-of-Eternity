#!/usr/bin/env python3
"""
LLM Story Vignettes Generator
Generate narrative vignettes based on Pillars of Eternity II gameplay data
"""

import os
import json
import re
import time
import logging
import shutil
import random
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
# from fix_busted_json import repair_json

class VignetteGenerator:
    def __init__(self, config_path="Config/config.json"):
        """Initialize the vignette generator with configuration."""
        self.script_folder = Path(__file__).parent
        self.config_path = self.script_folder / config_path
        self.config = self.load_config()
        
        # Setup folder paths
        self.input_folder = self.script_folder / self.config['input_folder_path']
        self.processing_folder = self.script_folder / self.config['processing_folder_path']
        self.output_folder = self.script_folder / self.config['output_folder_path']
        self.config_folder = self.script_folder / self.config['config_folder_path']
        self.logs_folder = self.script_folder / self.config['logs_folder_path']
        
        # Setup logging
        self.setup_logging()
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.config['llm_api_key'])
        
        self.logger.info("VignetteGenerator initialized")
        
    def load_config(self):
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            raise
            
    def setup_logging(self):
        """Setup logging configuration."""
        self.logs_folder.mkdir(exist_ok=True)
        
        # Main logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.logs_folder / 'vignette_generator.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('VignetteGenerator')
        
        # Error logger
        error_handler = logging.FileHandler(self.logs_folder / 'error.log')
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        error_handler.setFormatter(error_formatter)
        
        error_logger = logging.getLogger('ErrorLogger')
        error_logger.addHandler(error_handler)
        self.error_logger = error_logger
        
    def check_trigger_conditions(self):
        """Check if vignette generation should be triggered."""
        try:
            # Load last execution time
            last_exec_file = self.config_folder / 'last_execution.json'
            if last_exec_file.exists():
                with open(last_exec_file, 'r') as f:
                    last_exec_data = json.load(f)
                    last_exec_time = datetime.fromisoformat(last_exec_data['last_execution_time'])
            else:
                last_exec_time = datetime.min
                
            # Check if enough time has passed
            current_time = datetime.now()
            time_diff = current_time - last_exec_time
            interval_threshold = timedelta(minutes=self.config['interval_minutes'])
            
            if time_diff < interval_threshold:
                self.logger.info(f"Time condition not met. {interval_threshold - time_diff} remaining.")
                return False
                
            # Check if any input file was modified within the interval
            recent_modification = False
            threshold_time = current_time - interval_threshold
            
            for file_path in self.input_folder.rglob('*'):
                if file_path.is_file():
                    mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mod_time > threshold_time:
                        recent_modification = True
                        self.logger.info(f"Recent modification detected: {file_path}")
                        break
                        
            if not recent_modification:
                self.logger.info("No recent file modifications detected.")
                return False
                
            self.logger.info("Trigger conditions met. Proceeding with vignette generation.")
            return True
            
        except Exception as e:
            self.error_logger.error(f"Error checking trigger conditions: {e}")
            return False
            
    def update_last_execution_time(self):
        """Update the last execution timestamp."""
        try:
            last_exec_file = self.config_folder / 'last_execution.json'
            data = {"last_execution_time": datetime.now().isoformat()}
            with open(last_exec_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.error_logger.error(f"Error updating last execution time: {e}")
            
    def extract_executive_summary_from_combat_log(self, combat_log_path):
        """Extract executive summary from a combat log file."""
        try:
            with open(combat_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Look for executive summary section
            pattern = r'## 1\. Executive Summary(.*?)(?:##|\Z)'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                summary = match.group(1).strip()
                self.logger.info(f"Extracted executive summary from {combat_log_path.name}")
                return summary
            else:
                self.logger.warning(f"No executive summary found in {combat_log_path.name}")
                return None
                
        except Exception as e:
            self.error_logger.error(f"Error extracting summary from {combat_log_path}: {e}")
            return None
            
    def update_gamestate_with_combat_summary(self, gamestate_data):
        """Update gameState.json with latest combat executive summary."""
        try:
            # Find most recent combat summary file (not log file)
            combat_logs_folder = self.script_folder / self.config['combat_logs_folder_path']
            if not combat_logs_folder.exists():
                self.logger.warning("CombatLogs folder not found")
                return gamestate_data
                
            # Look for summary files (.txt) instead of log files
            summary_files = list(combat_logs_folder.glob("*_summary.txt"))
            if not summary_files:
                self.logger.warning("No combat summary files found")
                return gamestate_data
                
            # Sort by modification time, get most recent
            latest_summary = max(summary_files, key=lambda x: x.stat().st_mtime)
            
            # Extract executive summary
            summary = self.extract_executive_summary_from_combat_log(latest_summary)
            
            if summary:
                # Ensure combat_log structure exists
                if 'combat_log' not in gamestate_data:
                    gamestate_data['combat_log'] = {}
                if 'previous_fights' not in gamestate_data['combat_log']:
                    gamestate_data['combat_log']['previous_fights'] = []
                    
                # Get current latest summary and source for comparison
                current_latest = gamestate_data['combat_log'].get('latest_executive_summary', '')
                current_source = gamestate_data['combat_log'].get('latest_summary_source', '')
                
                # Debug logging
                self.logger.info(f"Current source: {current_source}")
                self.logger.info(f"New source: {latest_summary.name}")
                self.logger.info(f"Summary changed: {summary != current_latest}")
                self.logger.info(f"Source changed: {latest_summary.name != current_source}")
                
                # Check if this is a new summary (different source file or different content)
                if summary != current_latest or latest_summary.name != current_source:
                    # Shift previous fights: move current latest to previous_fights[0]
                    if current_latest and current_latest.strip():
                        self.logger.info("Moving current latest summary to previous fights")
                        gamestate_data['combat_log']['previous_fights'].insert(0, current_latest)
                    
                    # Keep only last 3 previous fights
                    gamestate_data['combat_log']['previous_fights'] = \
                        gamestate_data['combat_log']['previous_fights'][:3]
                    
                    self.logger.info(f"Updated combat log rotation - now tracking {len(gamestate_data['combat_log']['previous_fights'])} previous fights")
                else:
                    self.logger.info("No change in combat summary detected - skipping rotation")
                
                gamestate_data['combat_log']['latest_executive_summary'] = summary
                gamestate_data['combat_log']['latest_summary_timestamp'] = datetime.now().isoformat()
                gamestate_data['combat_log']['latest_summary_source'] = latest_summary.name
                
                self.logger.info(f"Updated gameState with executive summary from {latest_summary.name}")
                
            return gamestate_data
            
        except Exception as e:
            self.error_logger.error(f"Error updating gamestate with combat summary: {e}")
            return gamestate_data
            
    def update_gamestate_with_recent_locations(self, gamestate_data):
        """Update gameState.json with latest locations from location files."""
        try:
            # Find most recent location file
            saves_folder = self.script_folder / "Input" / "Saves"
            if not saves_folder.exists():
                self.logger.warning("Input/Saves folder not found")
                return gamestate_data
                
            # Look for new_locations files
            location_files = list(saves_folder.glob("new_locations_*.txt"))
            if not location_files:
                self.logger.info("No location files found")
                return gamestate_data
                
            # Get the most recent location file (excluding the merged historical file)
            location_files = [f for f in location_files if "all_previous" not in f.name]
            if not location_files:
                self.logger.info("No timestamped location files found")
                return gamestate_data
                
            latest_location_file = max(location_files, key=lambda x: x.stat().st_mtime)
            
            # Read locations from the file
            try:
                with open(latest_location_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                # Skip header lines and extract locations
                new_locations = []
                for line in lines[2:]:  # Skip first 2 lines (header)
                    line = line.strip()
                    if line and not line.startswith('='):
                        new_locations.append(line)
                        
                if new_locations:
                    # Ensure plot_state structure exists
                    if 'plot_state' not in gamestate_data:
                        gamestate_data['plot_state'] = {}
                    if 'recent_locations' not in gamestate_data['plot_state']:
                        gamestate_data['plot_state']['recent_locations'] = []
                        
                    recent_locations = gamestate_data['plot_state']['recent_locations']
                    
                    # Check if we have new locations to add
                    updated = False
                    for location in reversed(new_locations):  # Add in reverse order to maintain chronology
                        if location not in recent_locations:
                            recent_locations.insert(0, location)
                            updated = True
                            self.logger.info(f"Added new location to recent_locations: {location}")
                            
                    if updated:
                        # Keep only last 10 locations (rotating queue)
                        if len(recent_locations) > 10:
                            removed_locations = recent_locations[10:]
                            gamestate_data['plot_state']['recent_locations'] = recent_locations[:10]
                            self.logger.info(f"Rotated out old locations: {removed_locations}")
                        else:
                            gamestate_data['plot_state']['recent_locations'] = recent_locations
                            
                        self.logger.info(f"Updated recent_locations with {len([loc for loc in new_locations if loc not in recent_locations])} new locations")
                    else:
                        self.logger.info("No new locations to add - recent_locations unchanged")
                        
            except Exception as e:
                self.error_logger.error(f"Error reading location file {latest_location_file}: {e}")
                
            return gamestate_data
            
        except Exception as e:
            self.error_logger.error(f"Error updating gamestate with recent locations: {e}")
            return gamestate_data
            
    def load_gamestate(self):
        """Load and update gameState.json with latest data."""
        try:
            gamestate_path = self.script_folder / self.config['gamestate_file_path']
            
            if not gamestate_path.exists():
                self.error_logger.error(f"gameState.json not found at {gamestate_path}")
                return {}
                
            with open(gamestate_path, 'r', encoding='utf-8') as f:
                gamestate_data = json.load(f)
                
            # Update with latest combat summary
            gamestate_data = self.update_gamestate_with_combat_summary(gamestate_data)
            
            # Update with latest locations
            gamestate_data = self.update_gamestate_with_recent_locations(gamestate_data)
            
            # Save updated gamestate back
            with open(gamestate_path, 'w', encoding='utf-8') as f:
                json.dump(gamestate_data, f, indent=2, ensure_ascii=False)
                
            self.logger.info("Loaded and updated gameState.json")
            return gamestate_data
            
        except Exception as e:
            self.error_logger.error(f"Error loading gamestate: {e}")
            return {}
            
    def load_crew_details(self):
        """Load crew details from JSON file."""
        try:
            crew_path = self.script_folder / self.config['crew_details_file_path']
            
            if not crew_path.exists():
                self.logger.warning(f"crew_details.json not found at {crew_path}")
                return {}
                
            with open(crew_path, 'r', encoding='utf-8') as f:
                crew_data = json.load(f)
                
            self.logger.info("Loaded crew_details.json")
            return crew_data
            
        except Exception as e:
            self.error_logger.error(f"Error loading crew details: {e}")
            return {}
        
    def load_recent_quests(self):
        """Load recent quests from a text file."""
        quests_path = self.script_folder / "Input" / "recent_quests.txt"
        if not quests_path.exists():
            self.logger.warning(f"recent_quests.txt not found at {quests_path}")
            return "No recent quests available."
        try:
            with open(quests_path, 'r', encoding='utf-8') as f:
                quests = f.read().strip()
            self.logger.info("Loaded recent_quests.txt")
            return quests
        except Exception as e:
            self.error_logger.error(f"Error loading recent quests: {e}")
            return "No recent quests available."
                
    def load_vignette_themes(self):
        """Load vignette themes from JSON file."""
        try:
            themes_path = self.script_folder / self.config['vignette_themes_file_path']
            
            if not themes_path.exists():
                self.logger.warning(f"vignette_themes.json not found at {themes_path}")
                return {"scene_tropes": []}
                
            with open(themes_path, 'r', encoding='utf-8') as f:
                themes_data = json.load(f)
                
            # Count themes for logging
            theme_count = 0
            if 'scene_tropes' in themes_data:
                theme_count = len(themes_data['scene_tropes'])
                        
            self.logger.info(f"Loaded {theme_count} vignette themes")
            return themes_data
            
        except Exception as e:
            self.error_logger.error(f"Error loading vignette themes: {e}")
            return {"scene_tropes": []}
            
    # def select_vignette_theme(self, themes, gamestate_data):
    #     """Select appropriate vignette theme based on current context."""
    #     if not themes:
    #         return "general"
            
    #     # Simple selection logic - can be enhanced
    #     # For now, just rotate through themes or select based on recent locations
    #     current_theme = themes[0] if themes else "general"
    #     self.logger.info(f"Selected vignette theme: {current_theme}")
    #     return current_theme

    import random

    def select_vignette_theme(self, themes_data, gamestate_data):
        """Select 3 random vignette tropes (title + category) and return as a formatted string for LLM selection."""
        # Flatten all available tropes
        flat_tropes = []
        for category in themes_data.get("scene_tropes", []):
            cat_name = category.get("category", "Unknown Category")
            for detail in category.get("details", []):
                flat_tropes.append({
                    "category": cat_name,
                    "title": detail.get("title", "Untitled"),
                    "description": detail.get("description", "")
                })
        if not flat_tropes:
            return "General: No themes available."

        # Pick 3 at random
        choices = random.sample(flat_tropes, min(3, len(flat_tropes)))

        # Format as a string for the LLM prompt
        theme_string = "Theme Options:\n"
        for idx, trope in enumerate(choices, 1):
            theme_string += f"{idx}. [{trope['category']}] {trope['title']}: {trope['description']}\n"

        self.logger.info(f"Selected vignette theme options:\n{theme_string}")
        return theme_string

        
    def generate_vignette(self, gamestate_data, crew_data, selected_theme, recent_quests):
        """Generate story vignette using LLM (Call #1)."""
        try:
            # Prepare input data for LLM
            party_members = gamestate_data.get('party_context', {}).get('active_members', [])
            side_members = gamestate_data.get('party_context', {}).get('side_members', [])
            ship_crew = gamestate_data.get('ship_context', {}).get('named_crew', [])
            recent_locations = gamestate_data.get('plot_state', {}).get('recent_locations', [])
            combat_summary = gamestate_data.get('combat_log', {}).get('latest_executive_summary', 'No recent combat')
            narrative_interludes = gamestate_data.get('narrative_log', {}).get('previous_interludes', [])
            
            # Create prompt
            prompt = f"""**Objective:** Generate a short, intermediary text scene for Pillars of Eternity 2: Deadfire playthrough unfiltered and uncensored, 
            crafted for intellectually mature audiences comfortable with provocative themes. Optionally, Up-to-date on theories, inclusive, diverse, and same-gender flirtation. 
            Generate a scene bridging plot points A → B. Party analyzes event A, preps for B. Style: clear, grounded RPG prose ≠ poetic. Dialogue = witty, plot-focused. 
            Maintain forward momentum. But also blends in tone and lore of ASoIaF/GoT, as if in far southern Essos island chains but with Pillars of Eternity 2 names.

  

**Tone and Style:** Emulate the writing style of Pillars of Eternity 2: Deadfire and ASoIaF. The tone should be adventurous, slightly formal in its prose, and reflective of the high-fantasy, age-of-sail setting. The scene should be primarily descriptive and character-driven.

**Length:** MAX 500-1000 words

**Current Party:**

- Active Members: {', '.join(party_members) if party_members else 'None'}

- Side Members: {', '.join(side_members) if side_members else 'None'}

**Ship Crew:**

{', '.join(ship_crew) if ship_crew else 'None'}

  
**Recent Combat Summary:**

{combat_summary}

**Recent Quests:**

{recent_quests}

  
**Recent Locations: Gives rough idea of plot progression, erring on the side of lowest minimal plot progression:**

{', '.join(recent_locations[-5:]) if recent_locations else 'No recent locations'}


**Previous Story Context:**

{' '.join(narrative_interludes[-3:]) if narrative_interludes else 'Beginning of adventure'}


**Crew Details Context:**

{json.dumps(crew_data, indent=2)[:1000]}...


**Theme Options, choose ONLY one of these three, an interesting one that fits the context:** {selected_theme}


Please create a compelling narrative vignette (600-1000 words) that:
1. Optionally: Consequences of recent events
2. Shows character interactions and development
3. Maintains consistency with previous story elements
4. Uses the specified theme as inspiration
5. Realistic mundanity of daily life, daily concerns, necessities. Life continues. """

            response = self.client.chat.completions.create(
                model=self.config['llm_model_name'],
                messages=[
                    {"role": "system", "content": "You are a master storyteller creating narrative vignettes for intellectually mature audiences comfortable with provocative themes about Pillars of Eternity II adventures with ASoIaF/GoT influences. Focus on character-driven, interesting scenes, that are crafted with storytelling agility, multi-faced, multi-layered, and entertaining."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config['llm_max_tokens_vignette'],
                temperature=self.config['llm_temperature'],
                timeout=self.config['llm_timeout_seconds']
            )
            
            vignette = response.choices[0].message.content.strip()
            self.logger.info(f"Generated vignette ({len(vignette)} characters)")
            return vignette
            
        except Exception as e:
            self.error_logger.error(f"Error generating vignette: {e}")
            return None
            
    def create_narrative_summary(self, vignette):
        """Create narrative summary of the vignette (LLM Call #2)."""
        try:
            prompt = f"""Create a concise narrative summary (100-200 words) of the following vignette that captures:
1. Key character interactions and developments
2. Important plot points or discoveries
3. Emotional or relationship changes
4. Setting or location significance
5. Narrative tone or style elements
6. Ultra-compact shorthand using abbreviations, symbols, and minimal syntax while preserving major details and relationship. Use techniques like: acronyms, mathematical symbols, but NO EMOJIS, drop articles/prepositions where clear, use punctuation as operators, compress similar concepts. Ensure an LLM can fully reconstruct the original meaning.
7. Max 200 words

This summary will be used as context for future story generation.

Vignette:
{vignette}

Please provide only the summary, no additional text."""

            response = self.client.chat.completions.create(
                model=self.config['llm_model_name'],
                messages=[
                    {"role": "system", "content": "You are creating concise narrative summaries that capture the essence of story vignettes for future reference."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config['llm_max_tokens_summary'],
                temperature=0.3,
                timeout=self.config['llm_timeout_seconds']
            )
            
            summary = response.choices[0].message.content.strip()
            self.logger.info(f"Created narrative summary ({len(summary)} characters)")
            return summary
            
        except Exception as e:
            self.error_logger.error(f"Error creating narrative summary: {e}")
            return None
            
    def update_crew_details(self, vignette, current_crew_data):
        """Update crew details based on vignette content (LLM Call #3)."""
        try:
            # Reduce the max tokens to prevent truncation issues
            reduced_max_tokens = min(self.config['llm_max_tokens_crew_update'], 4000)
            
            prompt = f"""Analyze the following vignette and current crew details to identify any changes that should be made to character relationships, status, or details based on the events described.

Current Crew Details:
{json.dumps(current_crew_data, indent=2)}

New Vignette:
{vignette}

CRITICAL INSTRUCTIONS:
1. You MUST return ONLY valid, complete JSON that starts with {{ and ends with }}
2. Include ALL existing characters, even if unchanged
3. Do NOT add any text before or after the JSON
4. If the response would be too long, make minimal changes only
5. Ensure all strings are properly quoted and JSON is valid
6. Ensure all strings are brief, using abbreviations, symbols, minimal wording, punctuation as operators, drop articles/prepositions where clear

If no meaningful changes are needed based on the vignette, return the original JSON exactly as provided."""

            response = self.client.chat.completions.create(
                model=self.config['llm_model_name'],
                messages=[
                    {"role": "system", "content": "You are a JSON data processor. Return ONLY valid JSON. Never add explanatory text. If the JSON would be too long, make minimal changes to fit within token limits."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=reduced_max_tokens,
                temperature=0.1,  # Very low temperature for consistency
                timeout=self.config['llm_timeout_seconds']
            )
            
            updated_crew_json = response.choices[0].message.content.strip()
            
            # Clean up the response - remove any non-JSON content
            if not updated_crew_json.startswith('{'):
                # Look for JSON block in the response
                json_start = updated_crew_json.find('{')
                if json_start != -1:
                    updated_crew_json = updated_crew_json[json_start:]
                else:
                    self.error_logger.error("No JSON found in LLM response")
                    return current_crew_data
            
            # Try to parse as JSON to validate
            try:
                updated_crew_data = json.loads(updated_crew_json)
                self.logger.info("Updated crew details based on vignette")
                return updated_crew_data
            except json.JSONDecodeError as e:
                self.error_logger.error(f"Invalid JSON returned from crew update: {e}")
                self.error_logger.error(f"JSON response length: {len(updated_crew_json)} characters")
                
                # If JSON is truncated, just return the original data
                if "Unterminated string" in str(e) or "Expecting" in str(e):
                    self.logger.info("JSON appears truncated - likely hit token limit. Returning original data.")
                    return current_crew_data
                    
                # Try basic repair for minor issues
                try:
                    self.logger.info("Attempting basic JSON repair...")
                    repaired_json = updated_crew_json
                    
                    # Ensure proper closing
                    open_braces = repaired_json.count('{')
                    close_braces = repaired_json.count('}')
                    if open_braces > close_braces:
                        repaired_json += '}' * (open_braces - close_braces)
                    
                    # Try parsing repaired JSON
                    updated_crew_data = json.loads(repaired_json)
                    self.logger.info("Successfully repaired and parsed JSON")
                    return updated_crew_data
                    
                except Exception as repair_error:
                    self.error_logger.error(f"JSON repair failed: {repair_error}")
                    self.logger.info("Returning original crew data due to JSON issues")
                    return current_crew_data
                
        except Exception as e:
            self.error_logger.error(f"Error updating crew details: {e}")
            return current_crew_data
            
    def save_vignette(self, vignette, metadata=None):
        """Save vignette to output folder."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"vignette_{timestamp}.md"
            filepath = self.output_folder / filename
            
            # Ensure output folder exists
            self.output_folder.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Story Vignette - {timestamp}\n\n")
                if metadata:
                    f.write("## Metadata\n\n")
                    for key, value in metadata.items():
                        f.write(f"- **{key}:** {value}\n")
                    f.write("\n")
                f.write("## Vignette\n\n")
                f.write(vignette)
                
            self.logger.info(f"Saved vignette to {filepath}")
            return filepath
            
        except Exception as e:
            self.error_logger.error(f"Error saving vignette: {e}")
            return None
            
    def save_narrative_summary(self, summary):
        """Save narrative summary to processing folder."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"narrative_{timestamp}_summary.txt"
            filepath = self.processing_folder / "narrative_summaries" / filename
            
            # Ensure folder exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Narrative Summary - {timestamp}\n")
                f.write("=" * 50 + "\n\n")
                f.write(summary)
                
            self.logger.info(f"Saved narrative summary to {filepath}")
            return filepath
            
        except Exception as e:
            self.error_logger.error(f"Error saving narrative summary: {e}")
            return None
            
    def update_gamestate_with_narrative_summary(self, gamestate_data, summary):
        """Update gameState.json with new narrative summary."""
        try:
            if 'narrative_log' not in gamestate_data:
                gamestate_data['narrative_log'] = {'previous_interludes': []}
                
            # Add new summary to beginning of interludes (most recent first)
            gamestate_data['narrative_log']['previous_interludes'].insert(0, summary)
            
            # Keep only last 3 interludes
            if len(gamestate_data['narrative_log']['previous_interludes']) > 3:
                gamestate_data['narrative_log']['previous_interludes'] = \
                    gamestate_data['narrative_log']['previous_interludes'][:3]
                    
            # Save updated gamestate
            gamestate_path = self.script_folder / self.config['gamestate_file_path']
            with open(gamestate_path, 'w', encoding='utf-8') as f:
                json.dump(gamestate_data, f, indent=2, ensure_ascii=False)
                
            self.logger.info("Updated gameState.json with new narrative summary")
            
        except Exception as e:
            self.error_logger.error(f"Error updating gamestate with narrative summary: {e}")
            
    def save_updated_crew_details(self, updated_crew_data):
        """Save updated crew details to file."""
        try:
            crew_path = self.script_folder / self.config['crew_details_file_path']
            with open(crew_path, 'w', encoding='utf-8') as f:
                json.dump(updated_crew_data, f, indent=2, ensure_ascii=False)
                
            self.logger.info("Saved updated crew_details.json")
            
        except Exception as e:
            self.error_logger.error(f"Error saving updated crew details: {e}")
            
    def generate_vignette_cycle(self):
        """Execute the complete vignette generation cycle."""
        try:
            self.logger.info("Starting vignette generation cycle")
            
            # Step 1: Load and update gamestate
            gamestate_data = self.load_gamestate()
            if not gamestate_data:
                self.logger.error("Failed to load gamestate data")
                return False
                
            # Step 2: Load crew details and themes
            crew_data = self.load_crew_details()
            themes_data = self.load_vignette_themes()
            quest_data = self.load_recent_quests()
            
            # Step 3: Select theme
            selected_theme = self.select_vignette_theme(themes_data, gamestate_data)
            
            # Step 4: Generate vignette (LLM Call #1)
            vignette = self.generate_vignette(gamestate_data, crew_data, selected_theme, quest_data)
            if not vignette:
                self.logger.error("Failed to generate vignette")
                return False
                
            # Step 5: Create narrative summary (LLM Call #2)
            summary = self.create_narrative_summary(vignette)
            if not summary:
                self.logger.error("Failed to create narrative summary")
                return False
                
            # Step 6: Update crew details (LLM Call #3)
            updated_crew_data = self.update_crew_details(vignette, crew_data)
            
            # Step 7: Save all outputs
            metadata = {
                "Theme": selected_theme,
                "Generated": datetime.now().isoformat(),
                "Party Members": ", ".join(gamestate_data.get('party_context', {}).get('active_members', [])),
                "LLM Model": self.config['llm_model_name']
            }
            
            vignette_path = self.save_vignette(vignette, metadata)
            summary_path = self.save_narrative_summary(summary)
            
            # Step 8: Update gamestate and crew files
            self.update_gamestate_with_narrative_summary(gamestate_data, summary)
            self.save_updated_crew_details(updated_crew_data)
            
            # Step 9: Update execution timestamp
            self.update_last_execution_time()
            
            self.logger.info("Vignette generation cycle completed successfully")
            return True
            
        except Exception as e:
            self.error_logger.error(f"Error in vignette generation cycle: {e}")
            return False
            
    def run(self):
        """Main execution loop."""
        self.logger.info("Starting VignetteGenerator")
        
        # Initial setup check
        if not self.input_folder.exists():
            self.error_logger.error(f"Input folder not found: {self.input_folder}")
            return
            
        try:
            while True:
                if self.check_trigger_conditions():
                    success = self.generate_vignette_cycle()
                    if success:
                        self.logger.info("Vignette generation completed successfully")
                    else:
                        self.logger.error("Vignette generation failed")
                        
                # Wait for next check (check every minute)
                time.sleep(60)
                
        except KeyboardInterrupt:
            self.logger.info("VignetteGenerator stopped by user")
        except Exception as e:
            self.error_logger.error(f"Unexpected error in main loop: {e}")

def main():
    """Entry point for the vignette generator."""
    generator = VignetteGenerator()
    generator.run()

if __name__ == "__main__":
    main()
