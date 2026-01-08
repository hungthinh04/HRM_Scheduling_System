"""
AI Analyzer - Uses Gemini Pro API to analyze and improve schedules
Provides insights, fairness evaluation, and optimization suggestions
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv

# Load .env file from backend directory
backend_dir = Path(__file__).parent
env_path = backend_dir / '.env'

# Handle encoding issues (Windows may save .env as UTF-16)
try:
    if env_path.exists():
        # Try common encodings first (faster than chardet)
        loaded = False
        for enc in ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1', 'cp1252']:
            try:
                load_dotenv(dotenv_path=env_path, encoding=enc)
                loaded = True
                break
            except (UnicodeDecodeError, UnicodeError, Exception):
                continue
        
        # If chardet available, use it as fallback
        if not loaded:
            try:
                import chardet
                with open(env_path, 'rb') as f:
                    raw_data = f.read()
                    detected = chardet.detect(raw_data)
                    encoding = detected.get('encoding', 'utf-8')
                load_dotenv(dotenv_path=env_path, encoding=encoding)
            except (ImportError, Exception):
                # Final fallback: try UTF-8 with errors='ignore'
                try:
                    with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    # Manually parse and set env vars if needed
                    load_dotenv(dotenv_path=env_path, encoding='utf-8', override=True)
                except Exception:
                    print(f"Warning: Could not load .env file with any encoding. Please save .env as UTF-8.")
    else:
        load_dotenv()
except Exception as e:
    # If loading fails, just continue - will check for API key later
    print(f"Warning: Could not load .env file: {e}")
    try:
        load_dotenv()
    except:
        pass


class AIAnalyzer:
    def __init__(self):
        """Initialize AI analyzer with Gemini Pro API"""
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError(
                f"GEMINI_API_KEY not found in environment variables.\n"
                f"Please create a .env file in {backend_dir} with:\n"
                f"GEMINI_API_KEY=your_api_key_here"
            )
        
        # Detect API type by key format
        if api_key.startswith('AIza'):
            # Gemini API key
            genai.configure(api_key=api_key)
            
            # First, try to list available models to see what's actually available
            try:
                models = genai.list_models()
                available_models = []
                for m in models:
                    if 'generateContent' in m.supported_generation_methods:
                        # Extract model name from full path (e.g., "models/gemini-pro" -> "gemini-pro")
                        model_name = m.name.split('/')[-1] if '/' in m.name else m.name
                        available_models.append(model_name)
                
                if available_models:
                    # Prefer stable models with quota (avoid experimental models)
                    # Experimental models like gemini-2.0-flash-exp have quota = 0 for free tier
                    preferred_order = ['gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash']
                    # Filter out experimental models - STRICTLY exclude any with 'exp', 'experimental', or version 2.0
                    stable_models = [
                        m for m in available_models 
                        if 'exp' not in m.lower() 
                        and 'experimental' not in m.lower()
                        and '2.0' not in m  # Exclude all 2.0 models (they're experimental)
                    ]
                    
                    if not stable_models:
                        # If no stable models, warn and use gemini-pro directly
                        print("⚠ Warning: No stable models found. Using gemini-pro directly.")
                        stable_models = ['gemini-pro']
                    
                    model_name = None
                    for pref in preferred_order:
                        if pref in stable_models:
                            model_name = pref
                            break
                    
                    if not model_name:
                        model_name = stable_models[0]  # Use first stable model
                    
                    print(f"📋 Available models: {available_models}")
                    print(f"✅ Stable models (filtered): {stable_models}")
                    print(f"🎯 Selected model: {model_name}")
                    
                    self.model = genai.GenerativeModel(model_name)
                    self.model_name = model_name
                    self.ai_type = "gemini"
                    print(f"✓ Using Gemini model: {model_name} (from {len(available_models)} available models)")
                else:
                    raise ValueError("No Gemini models found with generateContent support")
                    
            except Exception as e:
                # If listing fails, try common model names directly
                print(f"Warning: Could not list available models: {e}")
                print("Attempting to use 'gemini-pro' directly...")
                
                try:
                    self.model = genai.GenerativeModel('gemini-pro')
                    self.model_name = 'gemini-pro'
                    self.ai_type = "gemini"
                    print("✓ Using Gemini model: gemini-pro (direct)")
                except Exception as direct_error:
                    raise ValueError(
                        f"Could not initialize Gemini model. "
                        f"Please check your API key. Error: {direct_error}"
                    )
        else:
            # Fallback: try OpenAI format (for backward compatibility)
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
                self.model = "gpt-4o-mini"
                self.ai_type = "openai"
                self.model_name = "gpt-4o-mini"
            except ImportError:
                raise ValueError("Please use Gemini API key (starts with AIza) or install openai package")
    
    def analyze_schedule(self, schedule_data: Dict) -> Dict:
        """
        Analyze the schedule using AI and provide insights
        
        Args:
            schedule_data: Complete schedule data including statistics
        
        Returns:
            Dictionary with AI analysis including fairness, insights, and suggestions
        """
        # Extract key information for AI
        stats = schedule_data.get('statistics', {})
        schedule = schedule_data.get('schedule', [])
        
        # Build context for AI
        context = self._build_context(stats, schedule, schedule_data)
        
        # AI Prompts - Reduced to 2 most important ones for faster generation
        # Only analyze fairness and insights (skip suggestions and explanation to save time)
        prompts = {
            'fairness_analysis': self._get_fairness_prompt(context),
            'insights': self._get_insights_prompt(context),
            # 'suggestions': self._get_suggestions_prompt(context),  # Skip for faster generation
            # 'explanation': self._get_explanation_prompt(context)   # Skip for faster generation
        }
        
        results = {}
        
        # System instruction
        system_instruction = "You are an expert HR scheduling analyst. Provide clear, actionable insights."
        
        import time
        skip_remaining = False  # Flag to skip remaining calls if rate limited
        previous_key = None
        
        for key, prompt in prompts.items():
            # If previous call was rate limited, skip all remaining calls
            if skip_remaining:
                print(f"⏭ Skipping {key} - previous call rate limited")
                results[key] = "⚠ Skipped: Previous AI analysis rate limited. Please try again later."
                continue
            
            # Delay between calls (but only if previous succeeded)
            if previous_key and previous_key in results:
                if not results[previous_key].startswith('⚠'):
                    time.sleep(1.5)  # 1.5s delay between successful calls
                else:
                    # Previous call failed, skip remaining to fail fast
                    skip_remaining = True
                    results[key] = "⚠ Skipped: Previous AI analysis failed. Please try again later."
                    continue
            
            previous_key = key
            try:
                # Combine system instruction with user prompt
                full_prompt = f"{system_instruction}\n\n{prompt}"
                
                # Try once - if rate limit, skip immediately (no retry to avoid long waits)
                if self.ai_type == "gemini":
                    # Generate content with Gemini
                    response = self.model.generate_content(
                        full_prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.7,
                            max_output_tokens=1000,  # Increased from 500 to get full responses
                        )
                    )
                    results[key] = response.text.strip()
                else:
                    # Generate content with OpenAI (fallback)
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=1000
                    )
                    results[key] = response.choices[0].message.content.strip()
            except Exception as e:
                error_msg = str(e)
                print(f"⚠ Warning: AI analysis failed for {key}")
                print(f"   Error details: {error_msg[:200]}...")  # Log first 200 chars only
                
                # Parse and format error message for better UX - ALWAYS format before saving
                formatted_msg = None
                
                if "429" in error_msg or "quota" in error_msg.lower() or "exceeded" in error_msg.lower():
                    # Rate limit / quota exceeded - set flag to skip remaining calls
                    skip_remaining = True
                    
                    if "retry in" in error_msg.lower():
                        # Extract retry time if available
                        import re
                        retry_match = re.search(r'retry in ([\d.]+)s?', error_msg.lower())
                        if retry_match:
                            retry_sec = float(retry_match.group(1))
                            if retry_sec >= 60:
                                retry_min = int(retry_sec // 60)
                                retry_msg = f"{retry_min} minute{'s' if retry_min > 1 else ''}"
                            else:
                                retry_msg = f"{int(retry_sec)} second{'s' if retry_sec > 1 else ''}"
                        else:
                            retry_msg = "a few minutes"
                        formatted_msg = f"⚠ AI analysis unavailable due to API rate limit. Please try again in {retry_msg}."
                    elif "gemini-2.0" in error_msg or "flash-exp" in error_msg:
                        formatted_msg = "⚠ AI analysis unavailable: Experimental model quota exceeded. The system will use a stable model on next generation."
                    else:
                        formatted_msg = "⚠ AI analysis unavailable: API quota exceeded. Please check your Gemini API quota or wait a few minutes before trying again."
                elif "404" in error_msg or "not found" in error_msg.lower():
                    # Model not found
                    formatted_msg = "⚠ AI analysis unavailable: Model not found. The system will try an alternative model on next attempt."
                else:
                    # Generic error - show short, user-friendly message
                    if "error" in error_msg.lower() and len(error_msg) > 100:
                        formatted_msg = "⚠ AI analysis temporarily unavailable. Please try again later."
                    else:
                        # Keep short errors as-is but truncate if too long
                        short_msg = error_msg[:150] + "..." if len(error_msg) > 150 else error_msg
                        formatted_msg = f"⚠ AI analysis unavailable: {short_msg}"
                
                results[key] = formatted_msg or "⚠ AI analysis unavailable. Please try again later."
        
        # Calculate fairness score (0-100)
        fairness_score = self._calculate_fairness_score(stats)
        
        # For skipped prompts, provide default messages
        insights_text = results.get('insights', '')
        if not insights_text or insights_text.startswith('⚠'):
            # If insights failed, combine with suggestions prompt for a simpler combined analysis
            pass
        
        return {
            'fairness_score': fairness_score,
            'fairness_analysis': results.get('fairness_analysis', ''),
            'insights': insights_text or 'AI insights generation skipped for faster schedule generation.',
            'optimization_suggestions': 'AI optimization suggestions available in insights above. For detailed analysis, enable full AI analysis in settings.',
            'schedule_explanation': 'Schedule generated using OR-Tools constraint programming with fairness optimization. AI analysis focuses on fairness and load balancing metrics.',
            'ai_model_used': self.model_name,
            'ai_provider': self.ai_type
        }
    
    def _build_context(self, stats: Dict, schedule: List[Dict], full_data: Dict) -> str:
        """Build context string for AI analysis with optimization metrics"""
        opt_summary = stats.get('optimization_summary', {})
        fairness_info = opt_summary.get('fairness', {})
        load_balancing = opt_summary.get('load_balancing', {})
        location_dist = opt_summary.get('location_distribution', {})
        
        context = f"""
SCHEDULING SYSTEM CONTEXT - OPTIMIZATION ANALYSIS:

Basic Information:
- Total Employees: {len(full_data.get('employees', []))}
- Locations: {len(full_data.get('locations', []))}
- Shifts per day: {len(full_data.get('shifts', []))}
- Schedule period: {len(full_data.get('dates', []))} days (2 weeks)
- Total shift assignments: {stats.get('total_assignments', 0)}

=== FAIRNESS & LOAD BALANCING METRICS ===
Employee Shift Distribution:
- Minimum shifts per employee: {stats.get('min_shifts_per_employee', 0)}
- Maximum shifts per employee: {stats.get('max_shifts_per_employee', 0)}
- Average shifts per employee: {stats.get('avg_shifts_per_employee', 0):.2f}
- Variance: {fairness_info.get('variance', 0)}
- Load Balance Score: {load_balancing.get('score', 0)}/100
- Coefficient of Variation: {load_balancing.get('coefficient_of_variation', 0)}

=== LOCATION DISTRIBUTION METRICS ===
Location Diversity:
- Employees working at multiple locations: {location_dist.get('multi_location_employees', 0)}
- Location diversity rate: {location_dist.get('diversity_rate', 0)}%
- Average locations per employee: {location_dist.get('avg_per_employee', 0):.2f}

Location Assignment Counts:
{self._format_distribution(stats.get('shifts_per_location', {}))}

=== SHIFT TYPE DISTRIBUTION ===
Shift Type Counts:
{self._format_distribution(stats.get('shifts_per_type', {}))}
- Average shift type diversity: {stats.get('avg_shift_diversity', 0):.2f}/100

=== DAILY DISTRIBUTION ===
Daily Assignment Counts (first 5 days):
{self._format_distribution(dict(list(stats.get('shifts_per_day', {}).items())[:5]))}

=== DETAILED EMPLOYEE BREAKDOWN ===
Shifts per Employee (all employees):
{self._format_distribution(stats.get('shifts_per_employee', {}))}

Location Diversity per Employee:
{self._format_distribution(stats.get('location_diversity', {}))}

=== OPTIMIZATION TARGETS ===
The system aims to:
1. Maximize fairness (minimize variance in shifts per employee)
2. Optimize load balancing (balance workload across all employees)
3. Ensure location diversity (employees work across multiple locations)
4. Balance shift types (fair distribution of morning/afternoon/evening)
5. Resolve conflicts (no overlapping or consecutive shifts)
"""
        return context
    
    def _format_distribution(self, distribution: Dict) -> str:
        """Format distribution dictionary for readability"""
        if not distribution:
            return "  None"
        lines = []
        for key, value in distribution.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)
    
    def _get_fairness_prompt(self, context: str) -> str:
        """Get prompt for fairness analysis focused on optimization"""
        return f"""
{context}

You are analyzing the FAIRNESS of this employee schedule. Focus on OPTIMIZATION aspects:

1. **Workload Distribution**: Analyze shift distribution among employees. Are some significantly overworked or underworked? Calculate the variance and identify outliers.

2. **Load Balancing**: Evaluate how well the workload is balanced. Consider:
   - The spread between minimum and maximum shifts per employee
   - Coefficient of variation in shift distribution
   - Whether the distribution approaches optimal fairness

3. **Location Diversity**: Assess how employees are distributed across locations:
   - How many employees work at multiple locations?
   - Is the location distribution fair and efficient?
   - Are there employees stuck at one location?

4. **Shift Type Balance**: Analyze distribution of morning/afternoon/evening shifts:
   - Is each employee getting a balanced mix of shift types?
   - Are some employees getting only undesirable shifts?

Provide a detailed fairness analysis with specific metrics and actionable recommendations for OPTIMIZATION.
"""
    
    def _get_insights_prompt(self, context: str) -> str:
        """Get prompt for optimization insights"""
        return f"""
{context}

Analyze this schedule for OPTIMIZATION OPPORTUNITIES. Focus on:

**Load Balancing Issues:**
- Identify employees with unusually high or low shift counts
- Detect patterns in shift distribution that indicate imbalance
- Calculate and report variance metrics

**Conflict Resolution:**
- Verify no scheduling conflicts exist
- Check for potential issues that constraints might have missed
- Identify edge cases that need attention

**Distribution Patterns:**
- How are employees distributed across locations?
- Are shift types (morning/afternoon/evening) balanced?
- Are there bottlenecks or underutilized resources?

Provide KEY INSIGHTS with specific numbers, metrics, and optimization recommendations.
"""
    
    def _get_suggestions_prompt(self, context: str) -> str:
        """Get prompt for optimization suggestions focused on fairness, load balancing, conflict resolution"""
        return f"""
{context}

Provide SPECIFIC OPTIMIZATION SUGGESTIONS to improve this schedule. Focus on:

**1. Fairness Optimization:**
- How to better balance shifts among employees
- Specific adjustments to reduce variance
- Strategies to ensure minimum/maximum constraints are met optimally

**2. Load Balancing Improvements:**
- How to redistribute shifts for better balance
- Identify which employees should work more/fewer shifts
- Calculate target distribution and suggest changes

**3. Conflict Resolution:**
- Address any detected scheduling conflicts
- Suggest constraint adjustments if needed
- Propose handling for edge cases

**4. Location Distribution:**
- Optimize cross-location assignments
- Ensure employees have appropriate location diversity
- Balance workload across all locations

**5. Shift Type Distribution:**
- Balance morning/afternoon/evening shifts per employee
- Ensure no employee gets only undesirable shifts
- Optimize shift type allocation

Provide actionable, specific recommendations with expected impact on fairness and load balance scores.
"""
    
    def _get_explanation_prompt(self, context: str) -> str:
        """Get prompt for schedule explanation"""
        return f"""
{context}

Explain how this schedule was generated. Describe:
1. The overall approach to scheduling
2. Key constraints that were considered
3. How the system ensures adequate coverage
4. How fairness was maintained

Write this as if explaining to HR management.
"""
    
    def _calculate_fairness_score(self, stats: Dict) -> float:
        """Calculate a simple fairness score based on distribution"""
        shifts_per_employee = stats.get('shifts_per_employee', {})
        
        if not shifts_per_employee:
            return 0.0
        
        values = [int(v) for v in shifts_per_employee.values()]
        if not values:
            return 0.0
        
        min_val = min(values)
        max_val = max(values)
        avg_val = sum(values) / len(values)
        
        # Calculate coefficient of variation (lower is better)
        if avg_val == 0:
            return 0.0
        
        variance = sum((x - avg_val) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        coefficient_of_variation = std_dev / avg_val if avg_val > 0 else 1.0
        
        # Convert to score (0-100, lower CV = higher score)
        # CV of 0 = perfect fairness (100), CV of 1 = poor fairness (0)
        fairness_score = max(0, min(100, 100 * (1 - coefficient_of_variation)))
        
        # Bonus for range being small
        if max_val > 0:
            range_ratio = (max_val - min_val) / max_val
            range_bonus = (1 - range_ratio) * 10
            fairness_score = min(100, fairness_score + range_bonus)
        
        return round(fairness_score, 2)
    
    def analyze_with_ai(self, schedule_file: str) -> Optional[Dict]:
        """
        Load schedule and analyze with AI
        
        Args:
            schedule_file: Path to schedule JSON file
        
        Returns:
            AI analysis results
        """
        try:
            with open(schedule_file, 'r', encoding='utf-8') as f:
                schedule_data = json.load(f)
            
            print("\n" + "=" * 60)
            print("AI Analysis - Analyzing Schedule")
            print("=" * 60)
            
            analysis = self.analyze_schedule(schedule_data)
            
            # Save analysis
            output_file = schedule_file.replace('.json', '_ai_analysis.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'schedule_file': schedule_file,
                    'analysis': analysis,
                    'analyzed_at': json.dumps(dict(), default=str)  # Will be set properly
                }, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"\n✓ AI Analysis completed!")
            print(f"✓ Fairness Score: {analysis['fairness_score']}/100")
            print(f"✓ Analysis saved to: {output_file}\n")
            
            return analysis
            
        except Exception as e:
            print(f"\n✗ Error in AI analysis: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Main function for AI analysis"""
    import sys
    
    if len(sys.argv) > 1:
        schedule_file = sys.argv[1]
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        schedule_file = os.path.join(base_dir, 'data', 'schedule.json')
    
    analyzer = AIAnalyzer()
    analyzer.analyze_with_ai(schedule_file)


if __name__ == '__main__':
    main()
