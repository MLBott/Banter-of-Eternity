#!/usr/bin/env python3
"""
Startup script for the Vignette Generator Service
"""

import sys
import signal
import time
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

from vignette_generator import VignetteGenerator

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    print("\n🛑 Vignette Generator stopping...")
    sys.exit(0)

def main():
    """Main entry point for the vignette generator service."""
    
    print("🚀 Starting Pillars of Eternity II Vignette Generator")
    print("=" * 60)
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Initialize generator
        generator = VignetteGenerator()
        
        print(f"✓ Generator initialized")
        print(f"✓ Monitoring interval: {generator.config['interval_minutes']} minutes")
        print(f"✓ Input folder: {generator.input_folder}")
        print(f"✓ Output folder: {generator.output_folder}")
        print(f"✓ LLM Model: {generator.config['llm_model_name']}")
        print()
        print("🎯 Monitoring for file changes...")
        print("   - The generator will check every minute for trigger conditions")
        print("   - Vignettes will be generated when:")
        print(f"     • {generator.config['interval_minutes']} minutes have passed since last generation")
        print("     • Files in Input/ folder have been modified recently")
        print()
        print("📁 Generated files will be saved to:")
        print(f"   • Vignettes: {generator.output_folder}")
        print(f"   • Summaries: {generator.processing_folder / 'narrative_summaries'}")
        print()
        print("Press Ctrl+C to stop the service")
        print("=" * 60)
        
        # Run the monitoring service
        generator.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Service stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
