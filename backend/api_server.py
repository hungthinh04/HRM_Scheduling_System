"""
Simple API server for frontend to call backend functions
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import sys
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scheduler import ShiftScheduler
from ai_analyzer import AIAnalyzer
from ai_pre_analyzer import AIPreAnalyzer

app = Flask(__name__)
CORS(app)

base_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(base_dir, 'data')

@app.route('/api/generate', methods=['POST'])
def generate_schedule():
    """Generate schedule with optional data updates"""
    try:
        # Get data from request (optional - if not provided, use files)
        try:
            request_data = request.get_json() or {}
        except Exception as e:
            # Handle empty or invalid JSON body gracefully
            request_data = {}
        
        employees_data = request_data.get('employees')
        locations_data = request_data.get('locations')
        shifts_data = request_data.get('shifts')
        
        # Save updated data if provided
        if employees_data:
            with open(os.path.join(data_dir, 'employees.json'), 'w', encoding='utf-8') as f:
                json.dump(employees_data, f, ensure_ascii=False, indent=2)
        
        if locations_data:
            with open(os.path.join(data_dir, 'locations.json'), 'w', encoding='utf-8') as f:
                json.dump(locations_data, f, ensure_ascii=False, indent=2)
        
        if shifts_data:
            with open(os.path.join(data_dir, 'shifts.json'), 'w', encoding='utf-8') as f:
                json.dump(shifts_data, f, ensure_ascii=False, indent=2)
        
        # Load data files
        employees_file = os.path.join(data_dir, 'employees.json')
        locations_file = os.path.join(data_dir, 'locations.json')
        shifts_file = os.path.join(data_dir, 'shifts.json')
        schedule_file = os.path.join(data_dir, 'schedule.json')
        
        # Step 0: AI Pre-Analysis (OPTIONAL - Skip to speed up)
        # Skip pre-analysis for faster generation - it's optional optimization
        ai_pre_analysis = None
        # Uncomment below to enable AI Pre-Analysis (slower but better optimization)
        # try:
        #     pre_analyzer = AIPreAnalyzer()
        #     with open(employees_file, 'r', encoding='utf-8') as f:
        #         emp_data = json.load(f)
        #     with open(locations_file, 'r', encoding='utf-8') as f:
        #         loc_data = json.load(f)
        #     with open(shifts_file, 'r', encoding='utf-8') as f:
        #         shift_data = json.load(f)
        #     
        #     ai_pre_analysis = pre_analyzer.analyze_scheduling_requirements(
        #         emp_data, loc_data, shift_data
        #     )
        # except Exception as e:
        #     print(f"AI Pre-Analysis skipped: {e}")
        
        # Step 1: Generate Schedule
        scheduler = ShiftScheduler(employees_file, locations_file, shifts_file)
        
        if ai_pre_analysis and ai_pre_analysis.get('suggested_constraints'):
            constraints = ai_pre_analysis['suggested_constraints']
            if 'min_employees_per_shift' in constraints:
                scheduler.min_employees_per_shift = constraints['min_employees_per_shift']
        
        schedule_result = scheduler.generate_schedule()
        scheduler._save_json(schedule_result, schedule_file)
        
        # Step 2: AI Post-Analysis (skip if rate limit to avoid long waits)
        ai_analysis = None
        try:
            analyzer = AIAnalyzer()
            ai_analysis = analyzer.analyze_schedule(schedule_result)
            
            # If all AI calls failed due to rate limit, set to None to avoid showing error messages
            if ai_analysis:
                all_rate_limited = (
                    ai_analysis.get('fairness_analysis', '').startswith('⚠') and 
                    ai_analysis.get('insights', '').startswith('⚠')
                )
                if all_rate_limited:
                    print("⚠ All AI analysis failed due to rate limit - skipping AI section")
                    ai_analysis = None  # Don't show AI section if completely rate limited
        except Exception as e:
            print(f"AI Post-Analysis skipped: {e}")
            ai_analysis = None
        
        # Combine results
        final_result = {
            **schedule_result,
        }
        
        if ai_pre_analysis:
            final_result['ai_pre_analysis'] = ai_pre_analysis
        
        if ai_analysis:
            final_result['ai_analysis'] = ai_analysis
        
        # Step 3: Optimization
        if ai_analysis and ai_analysis.get('fairness_score', 100) < 85:
            final_result['optimization_suggestions'] = {
                'current_fairness': ai_analysis['fairness_score'],
                'target_fairness': 85,
                'suggestions': ai_analysis.get('optimization_suggestions', '')
            }
        
        # Save final result
        final_output_file = os.path.join(data_dir, 'schedule_with_ai.json')
        scheduler._save_json(final_result, final_output_file)
        
        # Copy to frontend public folder
        import shutil
        frontend_public = os.path.join(base_dir, '..', 'frontend', 'public')
        os.makedirs(frontend_public, exist_ok=True)
        shutil.copy2(final_output_file, os.path.join(frontend_public, 'schedule_with_ai.json'))
        
        # Also copy data files to frontend public
        for data_file in ['employees.json', 'locations.json', 'shifts.json']:
            src_file = os.path.join(data_dir, data_file)
            if os.path.exists(src_file):
                shutil.copy2(src_file, os.path.join(frontend_public, data_file))
        
        return jsonify({
            'success': True,
            'message': 'Schedule generated successfully',
            'statistics': schedule_result['statistics']
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/save-data', methods=['POST'])
def save_data():
    """Save data files (employees, locations, shifts)"""
    try:
        request_data = request.get_json() or {}
        
        employees_data = request_data.get('employees')
        locations_data = request_data.get('locations')
        shifts_data = request_data.get('shifts')
        
        saved_files = []
        
        # Save employees
        if employees_data:
            emp_file = os.path.join(data_dir, 'employees.json')
            with open(emp_file, 'w', encoding='utf-8') as f:
                json.dump(employees_data, f, ensure_ascii=False, indent=2)
            saved_files.append('employees.json')
            
            # Also copy to frontend public
            frontend_public = os.path.join(base_dir, '..', 'frontend', 'public')
            os.makedirs(frontend_public, exist_ok=True)
            import shutil
            shutil.copy2(emp_file, os.path.join(frontend_public, 'employees.json'))
        
        # Save locations
        if locations_data:
            loc_file = os.path.join(data_dir, 'locations.json')
            with open(loc_file, 'w', encoding='utf-8') as f:
                json.dump(locations_data, f, ensure_ascii=False, indent=2)
            saved_files.append('locations.json')
            
            # Also copy to frontend public
            frontend_public = os.path.join(base_dir, '..', 'frontend', 'public')
            os.makedirs(frontend_public, exist_ok=True)
            import shutil
            shutil.copy2(loc_file, os.path.join(frontend_public, 'locations.json'))
        
        # Save shifts
        if shifts_data:
            shift_file = os.path.join(data_dir, 'shifts.json')
            with open(shift_file, 'w', encoding='utf-8') as f:
                json.dump(shifts_data, f, ensure_ascii=False, indent=2)
            saved_files.append('shifts.json')
            
            # Also copy to frontend public
            frontend_public = os.path.join(base_dir, '..', 'frontend', 'public')
            os.makedirs(frontend_public, exist_ok=True)
            import shutil
            shutil.copy2(shift_file, os.path.join(frontend_public, 'shifts.json'))
        
        return jsonify({
            'success': True,
            'message': f'Data saved successfully: {", ".join(saved_files)}'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/data/<filename>', methods=['GET'])
def get_data(filename):
    """Serve data files"""
    try:
        return send_from_directory(data_dir, filename)
    except:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    print("=" * 70)
    print("HRM Scheduling System - API Server")
    print("=" * 70)
    print(f"\n📡 Server starting on http://localhost:8000")
    print(f"📂 Data directory: {data_dir}")
    print("\nAvailable endpoints:")
    print("  POST /api/generate - Generate schedule")
    print("  POST /api/save-data - Save data files")
    print("  GET  /api/data/<filename> - Get data files")
    print("\n" + "=" * 70)
    app.run(port=8000, debug=True)
