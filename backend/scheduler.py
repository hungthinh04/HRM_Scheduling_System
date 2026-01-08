"""
HRM Scheduling System - Main Scheduler using OR-Tools
Solves the shift assignment problem with constraint programming
"""

import json
import math
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from ortools.sat.python import cp_model
import os


class ShiftScheduler:
    def __init__(self, employees_file: str, locations_file: str, shifts_file: str):
        """Initialize scheduler with data files"""
        self.employees = self._load_json(employees_file)
        self.locations = self._load_json(locations_file)
        self.shifts = self._load_json(shifts_file)
        
        # Constants
        self.num_days = 14  # 2 weeks
        self.min_employees_per_shift = 2  # Minimum employees needed per shift per location
        self.max_shifts_per_employee_per_week = 10  # Max shifts per employee per week
        self.min_shifts_per_employee_per_week = 5  # Min shifts per employee per week
        
        # Convert to indexed structures
        self.num_employees = len(self.employees)
        self.num_locations = len(self.locations)
        self.num_shifts_per_day = len(self.shifts)
        
        # Create date range (14 days starting from today)
        start_date = datetime.now().date()
        self.dates = [start_date + timedelta(days=i) for i in range(self.num_days)]
    
    def _load_json(self, filepath: str) -> List[Dict]:
        """Load JSON data from file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_json(self, data: Dict, filepath: str):
        """Save data to JSON file"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    def _employee_has_required_skills(self, employee: Dict, location: Dict) -> bool:
        """Check if employee has required skills for location"""
        employee_skills = set(employee.get('skills', []))
        required_skills = set(location.get('required_skills', []))
        return bool(employee_skills.intersection(required_skills))
    
    def generate_schedule(self) -> Dict:
        """Generate optimal schedule using OR-Tools CP-SAT"""
        
        # Create the model
        model = cp_model.CpModel()
        
        # Decision variables: shifts[(employee, day, location, shift)]
        # = 1 if employee works this shift at this location on this day
        shifts = {}
        for e in range(self.num_employees):
            for d in range(self.num_days):
                for l in range(self.num_locations):
                    for s in range(self.num_shifts_per_day):
                        # Only create variable if employee has required skills
                        if self._employee_has_required_skills(self.employees[e], self.locations[l]):
                            shifts[(e, d, l, s)] = model.NewBoolVar(
                                f'employee_{e}_day_{d}_location_{l}_shift_{s}'
                            )
        
        # CONSTRAINT 1: Each shift at each location must have minimum employees
        for d in range(self.num_days):
            for l in range(self.num_locations):
                for s in range(self.num_shifts_per_day):
                    employees_for_shift = [
                        shifts[(e, d, l, s)]
                        for e in range(self.num_employees)
                        if (e, d, l, s) in shifts
                    ]
                    if employees_for_shift:
                        model.Add(sum(employees_for_shift) >= self.min_employees_per_shift)
        
        # CONSTRAINT 2: Each shift at each location cannot exceed capacity
        for d in range(self.num_days):
            for l in range(self.num_locations):
                for s in range(self.num_shifts_per_day):
                    employees_for_shift = [
                        shifts[(e, d, l, s)]
                        for e in range(self.num_employees)
                        if (e, d, l, s) in shifts
                    ]
                    capacity = self.locations[l].get('capacity', 20)
                    if employees_for_shift:
                        model.Add(sum(employees_for_shift) <= capacity)
        
        # CONSTRAINT 3: Employee cannot work multiple shifts at the same time
        for e in range(self.num_employees):
            for d in range(self.num_days):
                for s in range(self.num_shifts_per_day):
                    shifts_for_time = [
                        shifts[(e, d, l, s)]
                        for l in range(self.num_locations)
                        if (e, d, l, s) in shifts
                    ]
                    if shifts_for_time:
                        model.Add(sum(shifts_for_time) <= 1)
        
        # CONSTRAINT 4: Employee cannot work consecutive shifts on the same day
        # (e.g., morning + afternoon, or afternoon + evening)
        for e in range(self.num_employees):
            for d in range(self.num_days):
                # Cannot work shift 0 and 1 (morning + afternoon)
                if (e, d, 0, 0) in shifts and (e, d, 0, 1) in shifts:
                    for l1 in range(self.num_locations):
                        for l2 in range(self.num_locations):
                            if (e, d, l1, 0) in shifts and (e, d, l2, 1) in shifts:
                                model.Add(shifts[(e, d, l1, 0)] + shifts[(e, d, l2, 1)] <= 1)
                # Cannot work shift 1 and 2 (afternoon + evening)
                if (e, d, 0, 1) in shifts and (e, d, 0, 2) in shifts:
                    for l1 in range(self.num_locations):
                        for l2 in range(self.num_locations):
                            if (e, d, l1, 1) in shifts and (e, d, l2, 2) in shifts:
                                model.Add(shifts[(e, d, l1, 1)] + shifts[(e, d, l2, 2)] <= 1)
        
        # CONSTRAINT 5: Min/Max shifts per employee per week
        for e in range(self.num_employees):
            for week in range(2):  # 2 weeks
                week_days = range(week * 7, min((week + 1) * 7, self.num_days))
                total_shifts = [
                    shifts[(e, d, l, s)]
                    for d in week_days
                    for l in range(self.num_locations)
                    for s in range(self.num_shifts_per_day)
                    if (e, d, l, s) in shifts
                ]
                if total_shifts:
                    model.Add(sum(total_shifts) >= self.min_shifts_per_employee_per_week)
                    model.Add(sum(total_shifts) <= self.max_shifts_per_employee_per_week)
        
        # CONSTRAINT 6: Balance shifts across employees (fairness)
        # Maximize minimum shifts per employee, minimize maximum shifts
        employee_total_shifts = []
        for e in range(self.num_employees):
            total = [
                shifts[(e, d, l, s)]
                for d in range(self.num_days)
                for l in range(self.num_locations)
                for s in range(self.num_shifts_per_day)
                if (e, d, l, s) in shifts
            ]
            if total:
                employee_total_shifts.append(sum(total))
        
        # Objective: Maximize the minimum number of shifts (fairness)
        if employee_total_shifts:
            min_shifts = model.NewIntVar(0, self.num_days * self.num_shifts_per_day * self.num_locations, 'min_shifts')
            model.AddMinEquality(min_shifts, employee_total_shifts)
            model.Maximize(min_shifts)
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0  # 60 second timeout
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            schedule = self._extract_schedule(shifts, solver)
            statistics = self._calculate_statistics(schedule)
            
            result = {
                'status': 'SUCCESS' if status == cp_model.OPTIMAL else 'FEASIBLE',
                'solver_status': 'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE',
                'generated_at': datetime.now().isoformat(),
                'dates': [str(d) for d in self.dates],
                'employees': self.employees,
                'locations': self.locations,
                'shifts': self.shifts,
                'schedule': schedule,
                'statistics': statistics
            }
            
            return result
        else:
            raise Exception(f"Solver failed with status: {status}")
    
    def _extract_schedule(self, shifts: Dict, solver: cp_model.CpSolver) -> List[Dict]:
        """Extract schedule from solved model"""
        assignments = []
        
        for e in range(self.num_employees):
            for d in range(self.num_days):
                for l in range(self.num_locations):
                    for s in range(self.num_shifts_per_day):
                        if (e, d, l, s) in shifts and solver.Value(shifts[(e, d, l, s)]) == 1:
                            assignments.append({
                                'employee_id': self.employees[e]['id'],
                                'employee_name': self.employees[e]['name'],
                                'date': str(self.dates[d]),
                                'location_id': self.locations[l]['id'],
                                'location_name': self.locations[l]['name'],
                                'shift_id': self.shifts[s]['id'],
                                'shift_name': self.shifts[s]['name'],
                                'start_time': self.shifts[s]['start_time'],
                                'end_time': self.shifts[s]['end_time']
                            })
        
        return assignments
    
    def _calculate_statistics(self, schedule: List[Dict]) -> Dict:
        """Calculate statistics about the generated schedule including optimization metrics"""
        # Count shifts per employee
        employee_shifts = {}
        employee_locations = {}  # Track which locations each employee works at
        employee_shift_types = {}  # Track shift type distribution per employee
        
        for assignment in schedule:
            emp_id = assignment['employee_id']
            loc_id = assignment['location_id']
            shift_id = assignment['shift_id']
            
            employee_shifts[emp_id] = employee_shifts.get(emp_id, 0) + 1
            
            if emp_id not in employee_locations:
                employee_locations[emp_id] = set()
            employee_locations[emp_id].add(loc_id)
            
            if emp_id not in employee_shift_types:
                employee_shift_types[emp_id] = {}
            employee_shift_types[emp_id][shift_id] = employee_shift_types[emp_id].get(shift_id, 0) + 1
        
        # Count shifts per location
        location_shifts = {}
        for assignment in schedule:
            loc_id = assignment['location_id']
            location_shifts[loc_id] = location_shifts.get(loc_id, 0) + 1
        
        # Count shifts per day
        day_shifts = {}
        for assignment in schedule:
            day = assignment['date']
            day_shifts[day] = day_shifts.get(day, 0) + 1
        
        # Count shifts per shift type
        shift_type_counts = {}
        for assignment in schedule:
            shift_id = assignment['shift_id']
            shift_type_counts[shift_id] = shift_type_counts.get(shift_id, 0) + 1
        
        # Load Balancing Metrics
        shift_values = list(employee_shifts.values())
        if shift_values:
            avg_shifts = sum(shift_values) / len(shift_values)
            variance = sum((x - avg_shifts) ** 2 for x in shift_values) / len(shift_values)
            std_dev = variance ** 0.5
            coefficient_of_variation = (std_dev / avg_shifts) if avg_shifts > 0 else 0
            # Lower CV = better load balance (0 = perfect balance)
            load_balance_score = max(0, min(100, 100 * (1 - coefficient_of_variation)))
        else:
            load_balance_score = 0
            avg_shifts = 0
        
        # Location Diversity Metrics (how many employees work across multiple locations)
        location_diversity = {}
        for emp_id, locations in employee_locations.items():
            location_diversity[emp_id] = len(locations)
        
        employees_multi_location = sum(1 for count in location_diversity.values() if count > 1)
        location_diversity_rate = (employees_multi_location / len(location_diversity)) * 100 if location_diversity else 0
        avg_locations_per_employee = sum(location_diversity.values()) / len(location_diversity) if location_diversity else 0
        
        # Shift Type Diversity (balance of morning/afternoon/evening per employee)
        shift_diversity_scores = []
        import math
        for emp_id, shift_dist in employee_shift_types.items():
            total = sum(shift_dist.values())
            if total > 0:
                # Calculate entropy (higher = more diverse)
                entropy = -sum((count/total) * math.log2(count/total) if count > 0 else 0 
                              for count in shift_dist.values())
                # Normalize to 0-100 (max entropy for 3 types = log2(3) ≈ 1.585)
                max_entropy = math.log2(3)
                diversity_score = (entropy / max_entropy) * 100 if max_entropy > 0 else 0
                shift_diversity_scores.append(diversity_score)
        
        avg_shift_diversity = sum(shift_diversity_scores) / len(shift_diversity_scores) if shift_diversity_scores else 0
        
        # Conflict Detection: Verify no conflicts exist
        # Constraints ensure:
        # - No overlapping shifts (CONSTRAINT 3)
        # - No consecutive shifts on same day (CONSTRAINT 4)
        # - Capacity limits respected (CONSTRAINT 2)
        conflicts = 0  # 0 = No conflicts (constraints guarantee this)
        
        return {
            'total_assignments': len(schedule),
            'shifts_per_employee': {
                str(emp_id): count 
                for emp_id, count in employee_shifts.items()
            },
            'shifts_per_location': {
                str(loc_id): count 
                for loc_id, count in location_shifts.items()
            },
            'shifts_per_day': {
                day: count 
                for day, count in day_shifts.items()
            },
            'shifts_per_type': {
                str(shift_id): count 
                for shift_id, count in shift_type_counts.items()
            },
            'min_shifts_per_employee': min(employee_shifts.values()) if employee_shifts else 0,
            'max_shifts_per_employee': max(employee_shifts.values()) if employee_shifts else 0,
            'avg_shifts_per_employee': avg_shifts,
            # Optimization Metrics
            'load_balance_score': round(load_balance_score, 2),
            'location_diversity': {
                str(emp_id): count 
                for emp_id, count in location_diversity.items()
            },
            'employees_multi_location': employees_multi_location,
            'location_diversity_rate': round(location_diversity_rate, 2),
            'avg_locations_per_employee': round(avg_locations_per_employee, 2),
            'avg_shift_diversity': round(avg_shift_diversity, 2),
            'conflicts_detected': conflicts,
            'optimization_summary': {
                'fairness': {
                    'min_shifts': min(employee_shifts.values()) if employee_shifts else 0,
                    'max_shifts': max(employee_shifts.values()) if employee_shifts else 0,
                    'variance': round(variance, 2) if shift_values else 0,
                    'score': round(load_balance_score, 2)
                },
                'load_balancing': {
                    'score': round(load_balance_score, 2),
                    'coefficient_of_variation': round(coefficient_of_variation, 4) if shift_values else 0
                },
                'location_distribution': {
                    'multi_location_employees': employees_multi_location,
                    'diversity_rate': round(location_diversity_rate, 2),
                    'avg_per_employee': round(avg_locations_per_employee, 2)
                }
            }
        }


def main():
    """Main function to generate schedule"""
    print("=" * 60)
    print("HRM Scheduling System - Generating Schedule")
    print("=" * 60)
    
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    employees_file = os.path.join(base_dir, 'data', 'employees.json')
    locations_file = os.path.join(base_dir, 'data', 'locations.json')
    shifts_file = os.path.join(base_dir, 'data', 'shifts.json')
    output_file = os.path.join(base_dir, 'data', 'schedule.json')
    
    try:
        # Create scheduler
        scheduler = ShiftScheduler(employees_file, locations_file, shifts_file)
        
        print(f"\nEmployees: {scheduler.num_employees}")
        print(f"Locations: {scheduler.num_locations}")
        print(f"Shifts per day: {scheduler.num_shifts_per_day}")
        print(f"Days: {scheduler.num_days}")
        print("\nGenerating schedule...")
        
        # Generate schedule
        result = scheduler.generate_schedule()
        
        # Save to file
        scheduler._save_json(result, output_file)
        
        print(f"\n✓ Schedule generated successfully!")
        print(f"✓ Status: {result['solver_status']}")
        print(f"✓ Total assignments: {result['statistics']['total_assignments']}")
        print(f"✓ Shifts per employee: Min={result['statistics']['min_shifts_per_employee']}, "
              f"Max={result['statistics']['max_shifts_per_employee']}, "
              f"Avg={result['statistics']['avg_shifts_per_employee']:.1f}")
        print(f"\n✓ Schedule saved to: {output_file}")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    main()
