#!/usr/bin/env python3
"""
Web server backend for the Vignette Generator Interface.
Provides API endpoints for the HTML interface to interact with combat logs and vignettes.
"""

import json
import os
import asyncio
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, render_template_string
from flask_cors import CORS
import re
# from fix_busted_json import repair_json

# Import our vignette generator
from vignette_generator import VignetteGenerator

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

class WebInterfaceAPI:
    def __init__(self):
        self.script_folder = Path(__file__).parent
        self.config_path = self.script_folder / "Config" / "config.json"
        self.load_config()
        
    def load_config(self):
        """Load configuration from config.json."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = {}
    
    def get_combat_logs(self):
        """Get list of all combat logs with metadata."""
        try:
            combat_logs_folder = self.script_folder / self.config.get('combat_logs_folder_path', 'Input/CombatLogs')
            if not combat_logs_folder.exists():
                return []
            
            combat_logs = []
            summary_files = list(combat_logs_folder.glob("*_summary.txt"))
            
            for summary_file in sorted(summary_files, key=lambda x: x.stat().st_mtime, reverse=True):
                try:
                    # Extract metadata from filename
                    filename = summary_file.name
                    # Parse location and timestamp from filename
                    match = re.match(r'CombatLogs(.+?) - (\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})_summary\.txt', filename)
                    
                    if match:
                        location = match.group(1).strip()
                        timestamp_str = match.group(2)
                        # Convert timestamp format
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H-%M-%S').isoformat()
                    else:
                        location = "Unknown"
                        timestamp = datetime.fromtimestamp(summary_file.stat().st_mtime).isoformat()
                    
                    # Read summary content
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    combat_logs.append({
                        'name': filename,
                        'timestamp': timestamp,
                        'location': location,
                        'summary': content,
                        'file_path': str(summary_file)
                    })
                    
                except Exception as e:
                    print(f"Error processing combat log {summary_file}: {e}")
                    continue
            
            return combat_logs
            
        except Exception as e:
            print(f"Error getting combat logs: {e}")
            return []
    
    def get_vignettes(self):
        """Get list of all vignettes with metadata."""
        try:
            vignettes_folder = self.script_folder / self.config.get('output_folder_path', 'Output/Vignettes')
            if not vignettes_folder.exists():
                return []
            
            vignettes = []
            vignette_files = list(vignettes_folder.glob("*.md"))
            
            for vignette_file in sorted(vignette_files, key=lambda x: x.stat().st_mtime, reverse=True):
                try:
                    # Read vignette content
                    with open(vignette_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extract metadata
                    metadata = self.extract_vignette_metadata(content)
                    
                    # Determine if it's interactive (check if filename contains 'interactive')
                    is_interactive = 'interactive' in vignette_file.name.lower()
                    
                    vignettes.append({
                        'name': vignette_file.name,
                        'timestamp': metadata.get('generated', datetime.fromtimestamp(vignette_file.stat().st_mtime).isoformat()),
                        'theme': metadata.get('theme', 'Story Vignette'),
                        'isInteractive': is_interactive,
                        'content': content,
                        'file_path': str(vignette_file)
                    })
                    
                except Exception as e:
                    print(f"Error processing vignette {vignette_file}: {e}")
                    continue
            
            return vignettes
            
        except Exception as e:
            print(f"Error getting vignettes: {e}")
            return []
    
    def extract_vignette_metadata(self, content):
        """Extract metadata from vignette markdown content."""
        metadata = {}
        
        # Extract theme
        theme_match = re.search(r'\*\*Theme:\*\*\s*(.+)', content)
        if theme_match:
            metadata['theme'] = theme_match.group(1).strip()
        
        # Extract generated timestamp
        generated_match = re.search(r'\*\*Generated:\*\*\s*(.+)', content)
        if generated_match:
            metadata['generated'] = generated_match.group(1).strip()
        
        # Extract party members
        party_match = re.search(r'\*\*Party Members:\*\*\s*(.+)', content)
        if party_match:
            metadata['party_members'] = party_match.group(1).strip()
        
        return metadata
    
    async def generate_interactive_vignette(self, base_vignette_data, user_message):
        """Generate a new vignette based on user input."""
        try:
            # Initialize vignette generator
            generator = VignetteGenerator(force_trigger=True)
            
            # Load current game state
            gamestate_data = generator.load_gamestate()
            crew_data = generator.load_crew_details()
            themes_data = generator.load_vignette_themes()
            
            # Create a custom prompt that incorporates the user's message
            selected_theme = f"Interactive Response: {user_message}"
            
            # Extract current context from base vignette
            base_content = base_vignette_data.get('content', '')
            
            # Create enhanced prompt for interactive generation
            party_members = gamestate_data.get('party_context', {}).get('active_members', [])
            side_members = gamestate_data.get('party_context', {}).get('side_members', [])
            ship_crew = gamestate_data.get('ship_context', {}).get('named_crew', [])
            recent_locations = gamestate_data.get('plot_state', {}).get('recent_locations', [])
            narrative_interludes = gamestate_data.get('narrative_log', {}).get('previous_interludes', [])
            combat_summary = gamestate_data.get('combat_log', {}).get('latest_executive_summary', '')
            
            # Create interactive prompt
            interactive_prompt = f"""**Objective:** Generate a short, interactive continuation scene for Pillars of Eternity 2: Deadfire based on user input. This is a direct response to the user's input: "{user_message}"

**Previous Scene Context:**
{base_content[:1000]}...

**User Response/Action:** {user_message}

**Current Party:**
- Active Members: {', '.join(party_members) if party_members else 'None'}
- Side Members: {', '.join(side_members) if side_members else 'None'}

**Ship Crew:**
{', '.join(ship_crew) if ship_crew else 'None'}

**Recent Combat Summary:**
{combat_summary}

**Recent Locations:**
{', '.join(recent_locations[-5:]) if recent_locations else 'No recent locations'}

**Previous Story Context:**
{' '.join(narrative_interludes[-2:]) if narrative_interludes else 'Beginning of adventure'}

**Crew Details Context:**
{json.dumps(crew_data, indent=2)[:800]}...

Please create a compelling narrative continuation (400-800 words) that:
1. Directly responds to the user's input: "{user_message}"
2. Shows how the characters react to or implement the user's suggestion
3. Maintains consistency with previous story elements
4. Advances the narrative based on the user's direction
5. Focuses on character interactions and realistic consequences
"""

            # Generate the interactive vignette
            response = generator.client.chat.completions.create(
                model=generator.config['llm_model_name'],
                messages=[
                    {"role": "system", "content": "You are a master storyteller creating interactive narrative continuations for Pillars of Eternity II adventures. Focus on responding directly to user input while maintaining story coherence."},
                    {"role": "user", "content": interactive_prompt}
                ],
                max_tokens=generator.config['llm_max_tokens_vignette'],
                temperature=generator.config['llm_temperature'],
                timeout=generator.config['llm_timeout_seconds']
            )
            
            vignette_content = response.choices[0].message.content.strip()
            
            # Create timestamp for filename
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
            
            # Create interactive vignette metadata
            metadata = {
                'theme': 'Interactive Response',
                'generated': timestamp.isoformat(),
                'party_members': ', '.join(party_members),
                'user_prompt': user_message,
                'base_vignette': base_vignette_data.get('name', 'Unknown'),
                'llm_model': generator.config['llm_model_name']
            }
            
            # Format the complete vignette
            full_vignette = f"""# Interactive Story Vignette - {timestamp_str}

## Metadata

- **Theme:** Interactive Response
- **Generated:** {timestamp.isoformat()}
- **Party Members:** {', '.join(party_members)}
- **User Prompt:** "{user_message}"
- **Based on:** {base_vignette_data.get('name', 'Previous Vignette')}
- **LLM Model:** {generator.config['llm_model_name']}

## Vignette

{vignette_content}
"""
            
            # Save the interactive vignette
            output_folder = generator.script_folder / generator.config['output_folder_path']
            output_folder.mkdir(parents=True, exist_ok=True)
            
            vignette_filename = f"interactive_vignette_{timestamp_str}.md"
            vignette_path = output_folder / vignette_filename
            
            with open(vignette_path, 'w', encoding='utf-8') as f:
                f.write(full_vignette)
            
            # Create summary for narrative log (but don't add to gameState since it's interactive)
            summary_prompt = f"""Create a concise narrative summary (100-150 words) of this interactive vignette that captures:
1. The user's input/action: "{user_message}"
2. Character responses and interactions
3. Key plot developments
4. Setting details

Vignette:
{vignette_content}

Please provide only the summary, no additional text."""

            summary_response = generator.client.chat.completions.create(
                model=generator.config['llm_model_name'],
                messages=[
                    {"role": "system", "content": "You are creating concise narrative summaries for interactive story elements."},
                    {"role": "user", "content": summary_prompt}
                ],
                max_tokens=generator.config['llm_max_tokens_summary'],
                temperature=0.3,
                timeout=generator.config['llm_timeout_seconds']
            )
            
            summary = summary_response.choices[0].message.content.strip()
            
            # Save summary to processing folder
            processing_folder = generator.script_folder / generator.config['processing_folder_path'] / "narrative_summaries"
            processing_folder.mkdir(parents=True, exist_ok=True)
            
            summary_filename = f"interactive_{timestamp_str}_summary.txt"
            summary_path = processing_folder / summary_filename
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            
            return {
                'name': vignette_filename,
                'timestamp': timestamp.isoformat(),
                'theme': 'Interactive Response',
                'isInteractive': True,
                'userPrompt': user_message,
                'content': full_vignette,
                'summary': summary,
                'file_path': str(vignette_path)
            }
            
        except Exception as e:
            print(f"Error generating interactive vignette: {e}")
            raise e

# Initialize API
api = WebInterfaceAPI()

@app.route('/')
def index():
    """Serve the main web interface."""
    return send_from_directory('.', 'web_interface.html')

@app.route('/api/combat-logs')
def get_combat_logs():
    """API endpoint to get all combat logs."""
    try:
        logs = api.get_combat_logs()
        return jsonify({'success': True, 'data': logs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vignettes')
def get_vignettes():
    """API endpoint to get all vignettes."""
    try:
        vignettes = api.get_vignettes()
        return jsonify({'success': True, 'data': vignettes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-interactive', methods=['POST'])
def generate_interactive():
    """API endpoint to generate interactive vignette."""
    try:
        data = request.get_json()
        base_vignette = data.get('baseVignette')
        user_message = data.get('userMessage')
        
        if not base_vignette or not user_message:
            return jsonify({'success': False, 'error': 'Missing baseVignette or userMessage'}), 400
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(api.generate_interactive_vignette(base_vignette, user_message))
            return jsonify({'success': True, 'data': result})
        finally:
            loop.close()
            
    except Exception as e:
        print(f"Error in generate_interactive: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trigger-generation', methods=['POST'])
def trigger_generation():
    """API endpoint to manually trigger vignette generation (like generate_vignette_now.py)."""
    try:
        generator = VignetteGenerator(force_trigger=True)
        success = generator.generate_vignette_cycle()
        
        if success:
            return jsonify({'success': True, 'message': 'Vignette generated successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to generate vignette'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Vignette Generator Web Interface...")
    print("📱 Access the interface at: http://localhost:5000")
    print("🔧 API endpoints available:")
    print("   - GET  /api/combat-logs")
    print("   - GET  /api/vignettes") 
    print("   - POST /api/generate-interactive")
    print("   - POST /api/trigger-generation")
    print("\n💡 Make sure you have Flask and Flask-CORS installed:")
    print("   pip install flask flask-cors")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
