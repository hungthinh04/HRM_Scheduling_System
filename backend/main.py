"""
Main entry point - Generate schedule and analyze with AI
"""

import sys
import os
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scheduler import ShiftScheduler
from ai_analyzer import AIAnalyzer
from ai_pre_analyzer import AIPreAnalyzer


def main():
    """Main workflow: Generate schedule -> Analyze with AI"""
    print("\n" + "=" * 70)
    print(" " * 15 + "HRM SCHEDULING SYSTEM")
    print(" " * 10 + "With AI-Powered Analysis")
    print("=" * 70)
    
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    employees_file = os.path.join(base_dir, 'data', 'employees.json')
    locations_file = os.path.join(base_dir, 'data', 'locations.json')
    shifts_file = os.path.join(base_dir, 'data', 'shifts.json')
    schedule_file = os.path.join(base_dir, 'data', 'schedule.json')
    
    try:
        # Step 0: AI Pre-Analysis (optional but recommended)
        print("\n[STEP 0/3] AI Pre-Analysis - Analyzing requirements...")
        try:
            pre_analyzer = AIPreAnalyzer()
            with open(employees_file, 'r', encoding='utf-8') as f:
                employees_data = json.load(f)
            with open(locations_file, 'r', encoding='utf-8') as f:
                locations_data = json.load(f)
            with open(shifts_file, 'r', encoding='utf-8') as f:
                shifts_data = json.load(f)
            
            ai_pre_analysis = pre_analyzer.analyze_scheduling_requirements(
                employees_data, locations_data, shifts_data
            )
            print("✓ AI Pre-Analysis completed")
            
            # Optionally adjust scheduler parameters based on AI recommendations
            if ai_pre_analysis.get('warnings'):
                print("⚠ Warnings:", ", ".join(ai_pre_analysis['warnings']))
        except Exception as e:
            print(f"⚠ AI Pre-Analysis skipped: {e}")
            ai_pre_analysis = None
        
        # Step 1: Generate Schedule
        print("\n[STEP 1/3] Generating optimized schedule with OR-Tools...")
        scheduler = ShiftScheduler(employees_file, locations_file, shifts_file)
        
        # Optionally use AI recommendations for constraints
        if ai_pre_analysis and ai_pre_analysis.get('suggested_constraints'):
            constraints = ai_pre_analysis['suggested_constraints']
            # Update scheduler parameters if needed
            if 'min_employees_per_shift' in constraints:
                scheduler.min_employees_per_shift = constraints['min_employees_per_shift']
        
        schedule_result = scheduler.generate_schedule()
        scheduler._save_json(schedule_result, schedule_file)
        
        print(f"\n✓ Schedule generated: {schedule_result['statistics']['total_assignments']} assignments")
        
        # Step 2: Analyze with AI
        print("\n[STEP 2/3] AI Post-Analysis - Analyzing generated schedule...")
        try:
            analyzer = AIAnalyzer()
            ai_analysis = analyzer.analyze_schedule(schedule_result)
        except ValueError as e:
            print(f"\n⚠ Warning: {e}")
            print("⚠ Continuing without AI analysis...")
            ai_analysis = None
        
        # Combine results
        final_result = {
            **schedule_result,
        }
        
        if ai_pre_analysis:
            final_result['ai_pre_analysis'] = ai_pre_analysis
        
        if ai_analysis:
            final_result['ai_analysis'] = ai_analysis
        
        # Step 3: AI Optimization Suggestions
        print("\n[STEP 3/3] AI Optimization - Generating improvement suggestions...")
        optimization_suggestions = None
        if ai_analysis and ai_analysis.get('fairness_score', 100) < 85:
            optimization_suggestions = {
                'current_fairness': ai_analysis['fairness_score'],
                'target_fairness': 85,
                'suggestions': ai_analysis.get('optimization_suggestions', ''),
                'recommended_actions': 'Review optimization suggestions and consider regenerating schedule with adjusted parameters'
            }
            print("⚠ Fairness score below target - Review suggestions in final output")
        else:
            print("✓ Schedule meets quality targets")
        
        if optimization_suggestions:
            final_result['optimization_suggestions'] = optimization_suggestions
        
        # Save final result with AI analysis
        final_output_file = os.path.join(base_dir, 'data', 'schedule_with_ai.json')
        scheduler._save_json(final_result, final_output_file)
        
        # Print summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"✓ Schedule Status: {schedule_result['solver_status']}")
        print(f"✓ Total Assignments: {schedule_result['statistics']['total_assignments']}")
        if ai_analysis:
            print(f"✓ Fairness Score: {ai_analysis['fairness_score']}/100")
        else:
            print("⚠ AI Analysis: Skipped (API key not configured)")
        print(f"\n✓ Files generated:")
        print(f"  - {schedule_file}")
        print(f"  - {final_output_file}")
        print("\n" + "=" * 70)
        if ai_analysis:
            print("\nSchedule generation and AI analysis completed successfully!\n")
        else:
            print("\nSchedule generation completed! (AI analysis skipped)\n")
        
        return final_result
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    main()
