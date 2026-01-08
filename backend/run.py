"""
Quick run script - Generates schedule and copies to frontend
"""

import os
import shutil
import sys

def main():
    print("=" * 70)
    print("HRM Scheduling System - Quick Run")
    print("=" * 70)
    
    # Step 1: Generate schedule
    print("\n[1/2] Generating schedule...")
    try:
        from main import main as generate_main
        result = generate_main()
        
        if not result:
            print("✗ Schedule generation failed!")
            return 1
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
        # Step 2: Copy to frontend
        print("\n[2/2] Copying files to frontend...")
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(base_dir)
            
            schedule_file = os.path.join(base_dir, 'data', 'schedule_with_ai.json')
            frontend_public = os.path.join(project_root, 'frontend', 'public')
            
            # Create public directory if it doesn't exist
            os.makedirs(frontend_public, exist_ok=True)
            
            # Copy schedule file
            if os.path.exists(schedule_file):
                dest = os.path.join(frontend_public, 'schedule_with_ai.json')
                shutil.copy2(schedule_file, dest)
                print(f"✓ Copied schedule_with_ai.json")
            else:
                # Try copying schedule.json instead
                schedule_file_fallback = os.path.join(base_dir, 'data', 'schedule.json')
                if os.path.exists(schedule_file_fallback):
                    dest = os.path.join(frontend_public, 'schedule.json')
                    shutil.copy2(schedule_file_fallback, dest)
                    print(f"✓ Copied schedule.json")
                else:
                    print("⚠ Warning: No schedule file found to copy")
            
            # Copy data files
            from copy_data_to_frontend import copy_data_files
            copy_data_files()
        
        print("\n" + "=" * 70)
        print("✓ All done! You can now run the frontend:")
        print("  cd frontend && npm run dev")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print(f"✗ Error copying files: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
