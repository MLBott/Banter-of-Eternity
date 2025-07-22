# Banter-of-Eternity
# Pillars of Eternity II - LLM Story Vignettes Generator
A companion storytelling system that runs alongside your Pillars of Eternity II gameplay, automatically generating immersive story vignettes over a configurable period, for eternity...
Like interactive cutscenes or narrative asides, these AI-generated stories provide a rich companion experience that incorporates your combat experiences, party dynamics, and exploration progress as they happen in your playthrough.
Includes a web interface to:
  - Read any of your party story vignettes as companion narratives to your adventure
  - Chat with any story vignette, like an interactive story that expands on your gameplay moments
  - Browse AI analyses and insights from your combat scenarios as narrative commentary

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key
- Pillars of Eternity II game files
- Combat Log Explorer (Optional - For Combat Logs) - https://www.nexusmods.com/pillarsofeternity2/mods/103

### Installation

After cloning the repo or downloading the zip file and extracting to a folder, Navigate to the folder:

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure your OpenAI API key:**

   - Edit `Config/config.json`
   - Replace the `llm_api_key` value with your actual OpenAI API key
  
3. **Add Companion Names to gameState.json**

   - Add your current companion names to Banter-of-Eternity/Input/gameState.json
   - Add them under "active_members" or "side_members"
   - Optionally, change your characters name from "Watcher" to your character's first name

5. **Start the monitoring service:**

   - Click start_game_save_monitor_web_page.bat to run the scripts OR

   - You can also run them individually manually:
   ```bash
   python game_save_monitor.py
   python start_vignette_service.py
   python web_server.py

   ```


## ⚙️ How It Works

### Automatic Generation

The system runs continuously and generates vignettes when:

1. **Time condition**: At least 30 minutes (configurable) have passed since last generation
2. **Activity condition**: Files in the Input/ folder have been modified recently

### Generation Process

1. **Data Collection** (Python scripts - no LLM cost):

   - Extracts executive summary from most recent combat log
   - Updates gameState.json with latest combat data and recent locations
   - Loads crew details and story themes

2. **LLM Processing** (3 API calls per generation):

   - **Call #1**: Generate story vignette (800-1200 words)
   - **Call #2**: Create narrative summary (100-200 words)
   - **Call #3**: Update crew relationships based on story events

3. **Output**:
   - Story vignette saved to `Output/Vignettes/`
   - Narrative summary saved to `Processing/narrative_summaries/`
   - Updated gameState.json and crew_details.json

## 🎮 Usage

### Running the Service

Click start_game_save_monitor_web_page.bat to run the scripts OR


You can also run the scripts manually:
```bash
# Start game save monitoring
python game_save_monitor.py

# Start continuous monitoring
python start_vignette_service.py

# Generate vignette immediately (manual trigger)
python generate_vignette_now.py
```


### Using the Web Interface

To browse combat logs and vignettes interactively:

```bash
python start_web_interface.py
```
Then open [http://localhost:5000](http://localhost:5000) in your browser.

## 🔧 Configuration

Edit `Config/config.json` to customize:

### Timing

- `interval_minutes`: How often to check for generation (default: 30 minutes)
- `archive_retention_days`: How long to keep old vignettes (default: 30 days)

### LLM Settings

- `llm_api_key`: Enter your API key, with double quotes
- `llm_model_name`: OpenAI model to use (default: "gpt-4.1")
- `llm_temperature`: Creativity level (0.0-1.0, default: 0.7)
- `llm_max_tokens_vignette`: Max length for vignettes (default: 4000)

### File Paths

All input/output paths are configurable for different setups.

## 📖 Generated Content

### Vignette Example

Story vignettes are rich narrative pieces that:

- Incorporate recent combat events naturally
- Show character development and relationships
- Reflect the current party composition
- Build on previous story elements
- Use selected themes for narrative direction

### Story Themes

The system uses 12 different narrative themes:

- Daily Rhythms & Group Living
- Social Dynamics & Communication
- Entertainment & Competition
- Relationship Development & Intimacy
- Conflict & Tension
- Memory & Identity Exploration
- And more...

## 🔍 Monitoring & Logs

### Log Files

- `Logs/vignette_generator.log`: Main application log
- `Logs/error.log`: Error-specific entries
- Both include timestamps and detailed information

### Status Checking

The service logs its activities, including:

- When trigger conditions are checked
- Data loading status
- LLM API calls and token usage
- File generation results

## 🛠️ Troubleshooting

### Common Issues

1. **No vignettes generated**:

   - Check that files in Input/ folder have been modified recently
   - Verify trigger conditions in logs
   - Ensure OpenAI API key is valid

2. **LLM API errors**:

   - Check API key in config.json
   - Verify internet connection
   - Check OpenAI API status

3. **Missing combat summaries**:
   - Ensure combat logs are processed by game_save_monitor.py first
   - Check that summary files exist in Input/CombatLogs/

### Manual Testing

```bash
# Test basic functionality
python test_vignette_generator.py

# Test summary extraction
python test_summary_extraction.py

# Force generation for testing
python generate_vignette_now.py
```

## 📊 API Usage

The system makes 3 LLM API calls per vignette generation:

- **Vignette generation**: ~3000-4000 tokens
- **Summary creation**: ~1000-1500 tokens
- **Crew profile update**: ~2000-3000 tokens

**Total cost per generation**: Approximately $0.05-0.07 (GPT-4.1 pricing)
**Frequency**: Only after a configurable period, every 30 minutes by default (not continuous)

## 🎯 Features

✅ **Automatic monitoring** - Runs in background, generates based on game activity  
✅ **Rich storytelling** - AI creates immersive narratives from gameplay data  
✅ **Character development** - Tracks and evolves crew relationships  
✅ **Combat integration** - Naturally incorporates recent battles  
✅ **Configurable themes** - Multiple narrative styles and focuses  
✅ **Efficient design** - Minimal LLM calls, Python handles data processing  
✅ **Comprehensive logging** - Detailed monitoring and debugging  
✅ **Error handling** - Graceful failure recovery  
✅ **Interactive web interface** - Browse and chat with vignettes

## 📝 File Requirements

Ensure these files exist in the Input/ folder:

- `gameState.json`: Party, crew, locations, and previous stories
- `crew_details.json`: Detailed crew member information
- `vignette_themes.json`: Available narrative themes
- `CombatLogs/`: Folder containing combat summary files

The system will auto-create missing folders and handle missing optional files gracefully.

---

**Enjoy your AI-generated adventure stories! 🎲⚔️📚**
