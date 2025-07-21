import os
import shutil
import zipfile
import time
import json
import re
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import getpass
from openai import OpenAI
from datetime import datetime

class GameSaveMonitor:
    def __init__(self, config_path=None):
        """
        Initialize the game save monitor.
        
        Args:
            config_path: Path to config.json file (optional, defaults to Config/config.json)
        """
        self.username = getpass.getuser()
        self.save_folder = Path(f"C:/Users/{self.username}/Saved Games/Pillars of Eternity II")
        self.script_folder = Path(__file__).parent
        self.saves_folder = self.script_folder / "Input/Saves"
        self.processed_folder = self.saves_folder / "processed_saves"
        self.files_list_path = self.saves_folder / "files_list.json"
        
        # Load configuration
        if config_path is None:
            config_path = self.script_folder / "Config" / "config.json"
        self.config = self.load_config(config_path)
        
        # Create necessary directories
        self.saves_folder.mkdir(exist_ok=True)
        self.processed_folder.mkdir(exist_ok=True)
        
        # Initialize OpenAI client with config values
        self.client = OpenAI(api_key=self.config["llm_api_key"])
        self.model = self.config["llm_model_name"]
        
        # Load existing files list
        self.files_list = self.load_files_list()
        
        print(f"Monitoring: {self.save_folder}")
        print(f"Script folder: {self.script_folder}")
        print(f"Saves folder: {self.saves_folder}")
        print(f"Processed saves folder: {self.processed_folder}")
    
    def load_config(self, config_path):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Validate required keys
            required_keys = ["llm_api_key", "llm_model_name"]
            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required config key: {key}")
                    
            # Check if API key is still the placeholder
            if config["llm_api_key"] == "YOUR-API-KEY-HERE":
                raise ValueError("Please update the API key in config.json")
                
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {config_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in config file: {config_path}")
    
    def load_files_list(self):
        """Load the existing files list from JSON file."""
        if self.files_list_path.exists():
            try:
                with open(self.files_list_path, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_files_list(self):
        """Save the files list to JSON file."""
        with open(self.files_list_path, 'w') as f:
            json.dump(self.files_list, f, indent=2)
    
    def copy_and_rename_save(self, save_file_path):
        """Copy save file to script folder and rename to .zip"""
        save_file = Path(save_file_path)
        if not save_file.exists():
            print(f"Save file not found: {save_file}")
            return None
            
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"save_{timestamp}.zip"
        zip_path = self.saves_folder / zip_filename
        
        # Ensure saves folder exists
        self.saves_folder.mkdir(parents=True, exist_ok=True)

        # Copy and rename
        shutil.copy2(save_file, zip_path)
        print(f"Copied save file to: {zip_path}")
        return zip_path
    
    def extract_zip(self, zip_path):
        """Extract zip file contents."""
        extract_folder = zip_path.with_suffix('')
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            print(f"Extracted to: {extract_folder}")
            return extract_folder
        except zipfile.BadZipFile:
            print(f"Error: {zip_path} is not a valid zip file")
            return None
    
    def get_all_files(self, folder_path):
        """Get list of all files in folder and subfolders."""
        files = []
        folder = Path(folder_path)
        
        for file_path in folder.rglob('*'):
            if file_path.is_file():
                # Get relative path from the extract folder
                relative_path = file_path.relative_to(folder)
                files.append(str(relative_path))
        
        return sorted(files)
    
    def compare_files_and_mark_new(self, current_files):
        """Compare current files with previous list and mark new ones."""
        new_files = []
        updated_list = []
        
        # Find new files
        for file in current_files:
            if file not in self.files_list:
                new_files.append(file)
                updated_list.append(file + " - NEW")
            else:
                updated_list.append(file)
        
        # Add any files that were in the old list but not in current
        for file in self.files_list:
            if file not in current_files and not file.endswith(" - NEW"):
                updated_list.append(file)
        
        print(f"Found {len(new_files)} new files")
        return updated_list, new_files
    
    def call_llm_for_analysis(self, new_files_list):
        """Call LLM to analyze if new files are in-game locations."""
        if not new_files_list:
            return []
        
        # Create the prompt
        files_text = "\n".join(new_files_list)
        prompt = f"""Analyze the following list of new files from a game save and determine which ones represent new in-game locations (like maps, levels, areas, zones, regions, etc.) versus other file types (like settings, saves, logs, temporary files, etc.).

New files:
{files_text}

Please respond with only the filenames that represent new in-game locations, one per line. If none of the files represent in-game locations, respond with "NONE"."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing game files and identifying which files represent in-game locations versus other file types."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            
            if result.upper() == "NONE":
                return []
            
            # Parse the response to get list of location files
            location_files = [line.strip() for line in result.split('\n') if line.strip()]
            return location_files
            
        except Exception as e:
            print(f"Error calling LLM: {e}")
            return []
    
    def process_llm_results(self, files_list, new_files, location_files):
        """Process LLM results and update file lists accordingly."""
        # Create copy of the list for location processing
        location_list = files_list.copy()
        
        # Process location files
        if location_files:
            print(f"LLM identified {len(location_files)} new location files")
            
            # Update location list - change NEW to NEW LOCATION for identified files
            # and remove all other files
            final_location_list = []
            for file in location_list:
                if file.endswith(" - NEW"):
                    base_file = file[:-6]  # Remove " - NEW"
                    if base_file in location_files:
                        final_location_list.append(base_file + " - NEW LOCATION")
                        
        else:
            print("LLM found no new location files")
            final_location_list = []
        
        # Create original list without " - NEW" endings
        clean_list = []
        for file in files_list:
            if file.endswith(" - NEW"):
                clean_list.append(file[:-6])  # Remove " - NEW"
            else:
                clean_list.append(file)
        
        return clean_list, final_location_list
    
    def clean_location_name(self, location_file):
        """Clean location filename to readable format."""
        # Remove " - NEW LOCATION" suffix if present
        if location_file.endswith(" - NEW LOCATION"):
            location_file = location_file[:-16]

        # Remove trailing punctuation, brackets, and whitespace
        location_file = location_file.strip().rstrip('",]')

        # Remove .lvl extension if present
        if location_file.endswith(".lvl"):
            location_file = location_file[:-4]
        
        # Remove file extension (e.g., .txt, .lvl, etc.)
        location_file = re.sub(r'\.[a-z0-9]+$', '', location_file, flags=re.IGNORECASE)

        
        
        # Remove acronym and number prefix (e.g., "ar_0501_")
        # Pattern to match prefix like "ar_0501_", "neketaka_", etc.
        cleaned = re.sub(r'^[a-z]+_\d+_', '', location_file)
        
        # If no number prefix, try removing just letter prefix (e.g., "neketaka_")
        if cleaned == location_file:
            cleaned = re.sub(r'^[a-z]+_', '', location_file)
        
        # Replace underscores with spaces and title case
        cleaned = cleaned.replace('_', ' ').title()
        
        # Handle special cases for better formatting
        cleaned = cleaned.replace(' Ext', ' (Exterior)')
        cleaned = cleaned.replace(' Int', ' (Interior)')
        cleaned = cleaned.replace('District', 'District')
        
        return cleaned
    
    def merge_location_files(self, new_locations):
        """Merge new locations with existing location files, keeping only the newest and a merged historical file."""
        if not new_locations:
            return
        
        # Clean the new location names
        cleaned_new_locations = [self.clean_location_name(loc) for loc in new_locations]
        
        # Find all existing location files
        location_files = list(self.saves_folder.glob("new_locations_*.txt"))
        location_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)  # Sort by modification time, newest first
        
        # Current timestamp for new file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create the newest locations file
        newest_file = self.saves_folder / f"new_locations_{timestamp}.txt"
        with open(newest_file, 'w', encoding='utf-8') as f:
            f.write(f"New locations found in save processed at {datetime.now()}:\n\n")
            for location in cleaned_new_locations:
                f.write(f"{location}\n")
        
        print(f"New locations saved to: {newest_file}")
        
        # Collect all historical locations from existing files
        all_historical_locations = set()
        
        for file_path in location_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Skip the header lines and extract location names
                    lines = content.split('\n')
                    for line in lines[2:]:  # Skip first 2 lines (header)
                        line = line.strip()
                        if line and not line.startswith('='):
                            # Clean the location name in case old files have uncleaned names
                            cleaned_line = self.clean_location_name(line)
                            all_historical_locations.add(cleaned_line)
            except Exception as e:
                print(f"Error reading location file {file_path}: {e}")
        
        # Add current new locations to historical set
        all_historical_locations.update(cleaned_new_locations)
        
        # Create merged historical file
        historical_file = self.saves_folder / "new_locations_all_previous.txt"
        with open(historical_file, 'w', encoding='utf-8') as f:
            f.write(f"All previously discovered locations (merged file):\n")
            f.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for location in sorted(all_historical_locations):
                f.write(f"{location}\n")
        
        print(f"Historical locations merged to: {historical_file}")
        
        # Clean up old location files (keep newest and merged historical)
        files_to_keep = {newest_file.name, historical_file.name}
        for file_path in location_files:
            if file_path.name not in files_to_keep:
                try:
                    file_path.unlink()
                    print(f"Removed old location file: {file_path}")
                except Exception as e:
                    print(f"Error removing file {file_path}: {e}")
    
    def update_gamestate_with_recent_locations(self, new_locations):
        """Update gameState.json with new locations in a rotating queue fashion."""
        try:
            gamestate_path = self.script_folder / "Input" / "gameState.json"
            
            if not gamestate_path.exists():
                print(f"Warning: gameState.json not found at {gamestate_path}")
                return
                
            # Load current gameState
            with open(gamestate_path, 'r', encoding='utf-8') as f:
                gamestate_data = json.load(f)
                
            # Ensure plot_state structure exists
            if 'plot_state' not in gamestate_data:
                gamestate_data['plot_state'] = {}
            if 'recent_locations' not in gamestate_data['plot_state']:
                gamestate_data['plot_state']['recent_locations'] = []
                
            # Clean the new locations
            cleaned_new_locations = [self.clean_location_name(loc) for loc in new_locations]
            
            # Get current recent_locations list
            recent_locations = gamestate_data['plot_state']['recent_locations']
            
            # Add new locations to the front of the list, avoiding duplicates
            for location in reversed(cleaned_new_locations):  # Reverse to maintain order when inserting at front
                if location and location not in recent_locations:
                    recent_locations.insert(0, location)
                    print(f"Added new location to recent_locations: {location}")
                    
            # Keep only the last 10 locations (rotating queue)
            if len(recent_locations) > 10:
                removed_locations = recent_locations[10:]
                recent_locations = recent_locations[:10]
                gamestate_data['plot_state']['recent_locations'] = recent_locations
                print(f"Rotated out old locations: {removed_locations}")
                
            # Save updated gameState
            with open(gamestate_path, 'w', encoding='utf-8') as f:
                json.dump(gamestate_data, f, indent=2, ensure_ascii=False)
                
            print(f"Updated gameState.json with {len(cleaned_new_locations)} new locations")
            print(f"Current recent_locations ({len(recent_locations)}): {recent_locations}")
            
        except Exception as e:
            print(f"Error updating gameState with recent locations: {e}")
    
    def find_combat_logs(self):
        """Find all CombatLogs files in the Input/CombatLogs folder."""
        combat_logs = []
        
        # Look in Input/CombatLogs folder for consistency with vignette_generator
        combat_logs_folder = self.script_folder / "Input" / "CombatLogs"
        if combat_logs_folder.exists():
            for file_path in combat_logs_folder.glob('CombatLogs*.log'):
                if file_path.is_file():
                    combat_logs.append(file_path)
        
        return combat_logs
    
    def get_summary_path(self, combat_log_path):
        """Get the path where the summary should be stored."""
        # Create summaries folder in Input/CombatLogs directory for consistency
        summaries_folder = self.script_folder / "Input" / "CombatLogs"
        summaries_folder.mkdir(exist_ok=True)
        
        # Use the combat log filename but with _summary.txt extension
        summary_filename = combat_log_path.name.replace('.log', '_summary.txt')
        return summaries_folder / summary_filename
    
    def summarize_combat_log(self, combat_log_path):
        """Summarize a combat log file using LLM."""
        try:
            # Read the combat log file
            with open(combat_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
            
            # Truncate if too long (keep last 8000 characters for recent activity)
            if len(log_content) > 8000:
                log_content = "...[truncated]...\n" + log_content[-8000:]
            
            # Create the prompt for summarization
            prompt = f"""Please provide a comprehensive and concise summary and analysis of the following combat log. Organize your analysis into the distinct sections listed below.

**1. Executive Summary:**
Briefly describe the overall flow of the battle. Who were the combatants? What was the general outcome?

**2. Key Events & Turning Points:**
Chronologically list the most impactful moments in the encounter. This should include:
- The death of significant enemies (e.g., Young Drake).
- Major multi-target abilities being used (e.g., Milo's "Sympathy for the Lost," Young Drake's "Breath").
- Moments where a character was in significant danger or received a large amount of healing.
- Successful interruptions of enemy abilities (e.g., Edér interrupting the Young Drake).

**3. Character Performance Highlights:**
For each friendly combatant (Edér as main protagonist/watcher, Aloth, Milo, Xoti, Serafen), provide a brief summary of their key contributions. Mention:
- Notable high-damage attacks.
- Important support actions (healing, buffs, debuffs).
- Who landed the killing blows.

**4. Enemy Analysis:**
Describe the primary threats posed by the enemies (Young Drake, Xaurip Champion, etc.). Mention:
- Their most dangerous abilities (e.g., Poisoned Strike, Breath).
- Which player characters they focused on.

**5. Enemy Threat Report:** For each unique enemy type, list: - **Primary Abilities Used:** (e.g., Poisoned Strike, Breath, Staff Blast). - **Successful Hits Landed:** The total number of times they successfully hit a player character. - **Killed By:** The character who landed the final blow. **6. Battle Timeline & Key Events:** - **First Blood:** Note the first character to deal damage. - **First Kill:** Note the first combatant to be killed and by whom. - **Most Powerful Attack:** Identify the single highest-damage attack, the attacker, the victim, and the damage amount. - **Crucial Heal:** Identify the most impactful healing ability used and its effect. - **Experience Gains:** List all instances of experience being awarded. - **Level Ups:** List all characters who gained a level.

**Combat Log Content:**
{log_content}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing game combat logs and providing clear, concise summaries of combat activities, encounters, and outcomes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.2
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error summarizing combat log {combat_log_path.name}: {e}")
            return None
    
    def process_combat_logs(self):
        """Process all combat logs in the script folder."""
        combat_logs = self.find_combat_logs()
        
        if not combat_logs:
            return
        
        print(f"Found {len(combat_logs)} combat log(s) to process")
        
        for combat_log in combat_logs:
            summary_path = self.get_summary_path(combat_log)
            
            # Skip if summary already exists
            if summary_path.exists():
                print(f"Summary already exists for {combat_log.name}, skipping...")
                continue
            
            print(f"Summarizing combat log: {combat_log.name}")
            
            # Generate summary
            summary = self.summarize_combat_log(combat_log)
            
            if summary:
                # Save summary to file
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(f"Combat Log Summary for: {combat_log.name}\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Original file size: {combat_log.stat().st_size} bytes\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(summary)
                
                print(f"Summary saved to: {summary_path}")
            else:
                print(f"Failed to generate summary for {combat_log.name}")
    
    def copy_combat_logs_to_input(self, extract_folder):
        """Copy any combat logs found in extracted save to Input/CombatLogs folder."""
        try:
            # Find combat logs in the extracted save folder
            extract_path = Path(extract_folder)
            combat_logs_found = []
            
            for file_path in extract_path.rglob('*'):
                if file_path.is_file() and file_path.name.startswith('CombatLog') and file_path.suffix == '.log':
                    combat_logs_found.append(file_path)
            
            if combat_logs_found:
                # Ensure Input/CombatLogs folder exists
                input_combat_folder = self.script_folder / "Input" / "CombatLogs"
                input_combat_folder.mkdir(parents=True, exist_ok=True)
                
                for combat_log in combat_logs_found:
                    # Copy to Input/CombatLogs folder
                    dest_path = input_combat_folder / combat_log.name
                    if not dest_path.exists():  # Only copy if it doesn't already exist
                        shutil.copy2(combat_log, dest_path)
                        print(f"Copied combat log to Input/CombatLogs: {combat_log.name}")
                    else:
                        print(f"Combat log already exists in Input/CombatLogs: {combat_log.name}")
                        
                print(f"Processed {len(combat_logs_found)} combat log(s) from save file")
                
        except Exception as e:
            print(f"Error copying combat logs to Input folder: {e}")

    def process_save_file(self, save_file_path):
        """Process a single save file through the entire pipeline."""
        print(f"\n{'='*50}")
        print(f"Processing save file: {save_file_path}")
        print(f"{'='*50}")
        
        # Step 1: Copy and rename to .zip
        zip_path = self.copy_and_rename_save(save_file_path)
        if not zip_path:
            return
        
        # Step 2: Extract zip
        extract_folder = self.extract_zip(zip_path)
        if not extract_folder:
            return
        
        # Step 3: Get all files
        current_files = self.get_all_files(extract_folder)
        print(f"Found {len(current_files)} files in save")
        
        # Step 3.5: Copy any combat logs to Input/CombatLogs folder
        self.copy_combat_logs_to_input(extract_folder)
        
        # Step 4: Compare and mark new files
        updated_list, new_files = self.compare_files_and_mark_new(current_files)
        
        if not new_files:
            print("No new files found")
            return
        
        # Step 5: Call LLM for analysis
        print("Calling LLM for analysis...")
        location_files = self.call_llm_for_analysis(new_files)
        
        # Step 6: Process results
        clean_list, location_list = self.process_llm_results(updated_list, new_files, location_files)
        
        # Step 7: Update and save files list
        self.files_list = clean_list
        self.save_files_list()
        
        # Step 8: Save location list if any locations found
        if location_list:
            self.merge_location_files(location_list)
            self.update_gamestate_with_recent_locations(location_list)
        
        # Step 9: Process combat logs if any exist
        self.process_combat_logs()
        
        print(f"Processing complete. Updated files list has {len(clean_list)} files")
        
        # Clean up
        shutil.rmtree(extract_folder)
        zip_path.unlink()
        print("Cleaned up temporary files")

class SaveFileHandler(FileSystemEventHandler):
    def __init__(self, monitor):
        self.monitor = monitor
        self.last_processed = {}
    
    def on_created(self, event):
        print(f"on_created event: {event.src_path}")  # DEBUG
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Only process .savegame files
        if not file_path.suffix.lower() == '.savegame':
            return
        
        # Add a small delay to ensure file is fully written
        time.sleep(1)
        
        # Check if file still exists and is not currently being written to
        if file_path.exists():
            current_time = time.time()
            
            # Avoid processing the same file multiple times in short succession
            if str(file_path) in self.last_processed:
                if current_time - self.last_processed[str(file_path)] < 5:  # 5 second cooldown
                    return
            
            self.last_processed[str(file_path)] = current_time
            
            print(f"New save file detected: {file_path}")
            self.monitor.process_save_file(file_path)
    
    def on_modified(self, event):
        # Also handle file modifications (some games might modify existing save files)
        print(f"on_modified event: {event.src_path}")  # DEBUG
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Only process .savegame files
        if not file_path.suffix.lower() == '.savegame':
            return
        
        # Add a small delay to ensure file is fully written
        time.sleep(1)
        
        if file_path.exists():
            current_time = time.time()
            
            # Avoid processing the same file multiple times in short succession
            if str(file_path) in self.last_processed:
                if current_time - self.last_processed[str(file_path)] < 5:  # 5 second cooldown
                    return
            
            self.last_processed[str(file_path)] = current_time
            
            print(f"Save file modified: {file_path}")
            self.monitor.process_save_file(file_path)

def main():
    try:
        # Initialize monitor (config will be loaded automatically)
        monitor = GameSaveMonitor()
        
        # Check if save folder exists
        if not monitor.save_folder.exists():
            print(f"Error: Save folder does not exist: {monitor.save_folder}")
            print("Please check the path and ensure the folder exists.")
            return
        
        # --- Merge existing new_locations files on startup ---
        location_files = list(monitor.saves_folder.glob("new_locations_*.txt"))
        all_locations = set()
        for file_path in location_files:
            print(f"Processing and merging existing location file: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
                # Skip header lines (first 2 lines)
                for line in lines[2:]:
                    line = line.strip()
                    if line and not line.startswith('='):
                        all_locations.add(line)
        if all_locations:
            print("Merging existing new_locations files on startup...")
            monitor.merge_location_files(list(all_locations))
        
        # Set up file system monitoring
        event_handler = SaveFileHandler(monitor)
        observer = Observer()
        observer.schedule(event_handler, str(monitor.save_folder), recursive=True)
        
        # Process any existing combat logs on startup
        print("Processing existing combat logs...")
        monitor.process_combat_logs()
        
        # Start monitoring
        observer.start()
        print(f"Started monitoring {monitor.save_folder}")
        print("Press Ctrl+C to stop monitoring...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print("\nStopping monitor...")
        
        observer.join()
        print("Monitor stopped.")
        
    except (FileNotFoundError, ValueError) as e:
        print(f"Configuration error: {e}")
        print("Please check your Config/config.json file and ensure it has the correct API key.")
        return
    except Exception as e:
        print(f"Unexpected error: {e}")
        return

if __name__ == "__main__":
    main()