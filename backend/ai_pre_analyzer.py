"""
AI Pre-Analyzer - Analyzes requirements before scheduling
Helps generate better constraints and parameters for OR-Tools
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv

# Load .env file
backend_dir = Path(__file__).parent
env_path = backend_dir / '.env'

try:
    if env_path.exists():
        for enc in ['utf-8', 'utf-16', 'utf-16-le', 'latin-1']:
            try:
                load_dotenv(dotenv_path=env_path, encoding=enc)
                break
            except:
                continue
    else:
        load_dotenv()
except:
    load_dotenv()


class AIPreAnalyzer:
    def __init__(self):
        """Initialize AI pre-analyzer with Gemini Pro"""
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        if api_key.startswith('AIza'):
            genai.configure(api_key=api_key)
            
            # First, try to list available models
            try:
                models = genai.list_models()
                available_models = []
                for m in models:
                    if 'generateContent' in m.supported_generation_methods:
                        model_name = m.name.split('/')[-1] if '/' in m.name else m.name
                        available_models.append(model_name)
                
                if available_models:
                    # Prefer stable models (avoid experimental models with quota=0)
                    preferred_order = ['gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash']
                    # Filter out experimental models - STRICTLY exclude any with 'exp', 'experimental', or version 2.0
                    stable_models = [
                        m for m in available_models 
                        if 'exp' not in m.lower() 
                        and 'experimental' not in m.lower()
                        and '2.0' not in m  # Exclude all 2.0 models
                    ]
                    
                    if not stable_models:
                        stable_models = ['gemini-pro']  # Fallback
                    
                    model_name = None
                    for pref in preferred_order:
                        if pref in stable_models:
                            model_name = pref
                            break
                    
                    if not model_name:
                        model_name = stable_models[0]
                    
                    self.model = genai.GenerativeModel(model_name)
                    self.ai_type = "gemini"
                    print(f"✓ Using Gemini model: {model_name}")
                else:
                    raise ValueError("No Gemini models found with generateContent support")
                    
            except Exception as e:
                # If listing fails, try gemini-pro directly
                print(f"Warning: Could not list available models: {e}")
                try:
                    self.model = genai.GenerativeModel('gemini-pro')
                    self.ai_type = "gemini"
                    print("✓ Using Gemini model: gemini-pro")
                except Exception as direct_error:
                    raise ValueError(f"Could not initialize Gemini model: {direct_error}")
        else:
            raise ValueError("Please use Gemini API key (starts with AIza)")
    
    def analyze_scheduling_requirements(
        self, 
        employees: List[Dict], 
        locations: List[Dict], 
        shifts: List[Dict],
        historical_data: Optional[Dict] = None
    ) -> Dict:
        """
        AI phân tích yêu cầu trước khi tạo lịch
        Đề xuất constraints và parameters tối ưu
        
        Returns:
            Dict with AI recommendations for scheduling
        """
        context = self._build_requirements_context(employees, locations, shifts, historical_data)
        
        prompt = f"""
{context}

You are an expert HR scheduling consultant. Before creating a schedule, analyze these requirements and provide recommendations:

1. **Coverage Analysis:**
   - What is the minimum number of employees needed per shift per location?
   - Are there enough employees with required skills for each location?
   - What's the optimal coverage ratio?

2. **Fairness Targets:**
   - What should be the min/max shifts per employee per week?
   - What variance would be acceptable?
   - What load balance score should we target?

3. **Potential Issues:**
   - Are there any skill mismatches?
   - Are there capacity constraints?
   - Any potential conflicts to watch for?

4. **Optimization Suggestions:**
   - What constraints should be prioritized?
   - Any special considerations for fairness?
   - Recommendations for location diversity?

Provide specific, actionable recommendations with numbers and targets.
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=800,
                )
            )
            
            ai_recommendations = response.text.strip()
            
            # Parse recommendations into structured format
            recommendations = {
                'ai_analysis': ai_recommendations,
                'suggested_constraints': self._extract_constraints(ai_recommendations, employees, locations, shifts),
                'warnings': self._extract_warnings(ai_recommendations),
                'optimization_targets': self._extract_targets(ai_recommendations)
            }
            
            return recommendations
            
        except Exception as e:
            print(f"Warning: AI pre-analysis failed: {e}")
            return {
                'ai_analysis': f"Analysis unavailable: {str(e)}",
                'suggested_constraints': self._default_constraints(employees, locations),
                'warnings': [],
                'optimization_targets': {}
            }
    
    def _build_requirements_context(
        self, 
        employees: List[Dict], 
        locations: List[Dict], 
        shifts: List[Dict],
        historical_data: Optional[Dict]
    ) -> str:
        """Build context for AI analysis"""
        
        # Count employees by skills
        skill_distribution = {}
        for emp in employees:
            for skill in emp.get('skills', []):
                skill_distribution[skill] = skill_distribution.get(skill, 0) + 1
        
        # Analyze location requirements
        location_requirements = {}
        for loc in locations:
            required = loc.get('required_skills', [])
            capacity = loc.get('capacity', 20)
            location_requirements[loc['name']] = {
                'required_skills': required,
                'capacity': capacity
            }
        
        context = f"""
SCHEDULING REQUIREMENTS ANALYSIS:

Basic Setup:
- Total Employees: {len(employees)}
- Total Locations: {len(locations)}
- Shifts per Day: {len(shifts)}
- Schedule Period: 14 days (2 weeks)

Employee Skills Distribution:
{json.dumps(skill_distribution, indent=2)}

Location Requirements:
"""
        for loc_name, req in location_requirements.items():
            context += f"\n- {loc_name}:"
            context += f"\n  Capacity: {req['capacity']}"
            context += f"\n  Required Skills: {', '.join(req['required_skills'])}"
        
        context += f"\n\nShifts:\n"
        for shift in shifts:
            context += f"- {shift['name']}: {shift['start_time']} - {shift['end_time']}\n"
        
        if historical_data:
            context += f"\nHistorical Data:\n"
            context += f"- Previous fairness score: {historical_data.get('fairness_score', 'N/A')}\n"
            context += f"- Common issues: {historical_data.get('common_issues', 'None')}\n"
        
        return context
    
    def _extract_constraints(self, ai_text: str, employees: List, locations: List) -> Dict:
        """Extract constraint recommendations from AI text"""
        # Default constraints
        constraints = {
            'min_employees_per_shift': 2,
            'max_shifts_per_week': 10,
            'min_shifts_per_week': 5,
            'preferred_coverage_ratio': 0.8
        }
        
        # Try to extract numbers from AI text
        import re
        
        # Look for min employees
        min_match = re.search(r'minimum.*?(\d+).*?employees?', ai_text.lower())
        if min_match:
            try:
                constraints['min_employees_per_shift'] = int(min_match.group(1))
            except:
                pass
        
        # Look for max shifts
        max_match = re.search(r'max.*?(\d+).*?shifts?', ai_text.lower())
        if max_match:
            try:
                constraints['max_shifts_per_week'] = int(max_match.group(1))
            except:
                pass
        
        return constraints
    
    def _extract_warnings(self, ai_text: str) -> List[str]:
        """Extract warnings from AI analysis"""
        warnings = []
        
        if 'insufficient' in ai_text.lower() or 'not enough' in ai_text.lower():
            warnings.append("Potential coverage issues detected")
        
        if 'conflict' in ai_text.lower() or 'mismatch' in ai_text.lower():
            warnings.append("Possible conflicts or mismatches identified")
        
        if 'capacity' in ai_text.lower() and 'exceed' in ai_text.lower():
            warnings.append("Capacity constraints may be tight")
        
        return warnings
    
    def _extract_targets(self, ai_text: str) -> Dict:
        """Extract optimization targets from AI analysis"""
        targets = {
            'fairness_target': 80,
            'load_balance_target': 75,
            'variance_target': 3.0
        }
        
        import re
        
        # Look for fairness target
        fairness_match = re.search(r'fairness.*?(\d+)', ai_text.lower())
        if fairness_match:
            try:
                targets['fairness_target'] = int(fairness_match.group(1))
            except:
                pass
        
        return targets
    
    def _default_constraints(self, employees: List, locations: List) -> Dict:
        """Default constraints if AI fails"""
        return {
            'min_employees_per_shift': 2,
            'max_shifts_per_week': 10,
            'min_shifts_per_week': 5,
            'preferred_coverage_ratio': 0.8
        }
