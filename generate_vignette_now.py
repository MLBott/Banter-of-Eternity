#!/usr/bin/env python3
"""
Manual trigger for vignette generation
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

from vignette_generator import VignetteGenerator

def force_generation():
    """Force a vignette generation cycle."""
    print("🎯 Manually triggering vignette generation...")
    print("=" * 50)
    
    try:
        generator = VignetteGenerator()
        
        # Force the execution by setting last execution time to long ago
        last_exec_file = generator.config_folder / 'last_execution.json'
        old_time = datetime.now() - timedelta(hours=1)  # 1 hour ago
        data = {"last_execution_time": old_time.isoformat()}
        with open(last_exec_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print("✓ Forced trigger conditions")
        
        # Run generation cycle
        success = generator.generate_vignette_cycle()
        
        if success:
            print("\n🎉 Vignette generation completed successfully!")
            
            # Show recent outputs
            output_files = list(generator.output_folder.glob("vignette_*.md"))
            if output_files:
                latest_vignette = max(output_files, key=lambda x: x.stat().st_mtime)
                print(f"✓ Latest vignette: {latest_vignette.name}")
                
                # Show metadata
                with open(latest_vignette, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    print("\n📋 Vignette Metadata:")
                    for line in lines[3:8]:  # Metadata section
                        if line.strip().startswith('- **'):
                            print(f"   {line}")
                            
            summary_files = list((generator.processing_folder / "narrative_summaries").glob("narrative_*_summary.txt"))
            print(f"✓ Total vignettes generated: {len(output_files)}")
            print(f"✓ Total summaries generated: {len(summary_files)}")
            
        else:
            print("❌ Vignette generation failed. Check the logs for details.")
            
    except Exception as e:
        print(f"❌ Error during manual generation: {e}")

def main():
    """Main entry point."""
    force_generation()

if __name__ == "__main__":
    main()
