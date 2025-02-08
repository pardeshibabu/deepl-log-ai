from openai import OpenAI
from typing import List, Dict
from app.models.log_model import ElkLog
import json
import re
import logging
from datetime import datetime

# Add after imports
logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def analyze_log(self, log: ElkLog) -> dict:
        """Analyze log and provide detailed analysis with suggestions"""
        try:
            # Extract error details from event.original if available
            event_data = {}
            try:
                event_data = json.loads(log.source.get("event", {}).get("original", "{}"))
            except json.JSONDecodeError:
                pass

            # Build the prompt with available information
            prompt = f"""
            Analyze this error log and provide a detailed solution. Format your response exactly as follows:

            ERROR DETECTION
            Type: [Specific error type, e.g., Database Connection Error, API Error, Authentication Error]
            Status Code: [HTTP status code if applicable, or internal error code]
            Description: [Brief, clear description of the error]
            File Location: [Extract or infer the file location from the error message]

            CODE ANALYSIS
            Problematic Code: [If available, show the problematic code snippet]
            Suggested Fix: [Provide the corrected code]
            
            ANALYSIS
            Severity: [HIGH/MEDIUM/LOW]
            Impact: [Brief description of the impact]
            Root Cause: [Most likely cause of the error]

            RESOLUTION
            Immediate Actions:
            - [Action 1]
            - [Action 2]
            
            Long-term Solutions:
            - [Solution 1]
            - [Solution 2]

            Log Details:
            - Message: {log.source.get("message")}
            - Level: {log.source.get("level_name")}
            - Error Context: {event_data.get("context", {})}
            - Timestamp: {event_data.get("datetime") or log.source.get("@timestamp", "Unknown")}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            analysis = response.choices[0].message.content
            
            # Parse the structured response
            sections = analysis.split('\n')
            error_info = {}
            current_section = ""
            immediate_actions = []
            resolution_steps = []
            code_info = {}
            
            for line in sections:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith("ERROR DETECTION"):
                    current_section = "error"
                elif line.startswith("CODE ANALYSIS"):
                    current_section = "code"
                elif line.startswith("ANALYSIS"):
                    current_section = "analysis"
                elif line.startswith("RESOLUTION"):
                    current_section = "resolution"
                elif line.startswith("Type:") and current_section == "error":
                    error_info["error_type"] = line.split(":", 1)[1].strip()
                elif line.startswith("Status Code:") and current_section == "error":
                    try:
                        error_info["status_code"] = int(line.split(":", 1)[1].strip())
                    except:
                        error_info["status_code"] = 500
                elif line.startswith("Description:") and current_section == "error":
                    error_info["error_message"] = line.split(":", 1)[1].strip()
                elif line.startswith("File Location:") and current_section == "error":
                    error_info["file_location"] = line.split(":", 1)[1].strip()
                elif line.startswith("Problematic Code:") and current_section == "code":
                    code_info["problematic_code"] = line.split(":", 1)[1].strip()
                elif line.startswith("Suggested Fix:") and current_section == "code":
                    code_info["suggested_fix"] = line.split(":", 1)[1].strip()
                elif line.startswith("Severity:") and current_section == "analysis":
                    error_info["severity"] = line.split(":", 1)[1].strip().upper()
                elif line.startswith("Impact:") and current_section == "analysis":
                    error_info["impact"] = line.split(":", 1)[1].strip()
                elif line.startswith("Root Cause:") and current_section == "analysis":
                    error_info["root_cause"] = line.split(":", 1)[1].strip()
                elif line.startswith("-"):
                    if "Immediate Actions" in current_section:
                        immediate_actions.append(line.strip("- "))
                    elif "Long-term Solutions" in current_section:
                        resolution_steps.append(line.strip("- "))
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error_type": error_info.get("error_type", "Unknown Error"),
                "error_message": error_info.get("error_message", log.source.get("message", "")[:150]),
                "file_location": error_info.get("file_location", "Unknown location"),
                "problematic_code": code_info.get("problematic_code"),
                "suggested_fix": code_info.get("suggested_fix"),
                "status_code": error_info.get("status_code", 500),
                "severity": error_info.get("severity", "MEDIUM"),
                "impact": error_info.get("impact", "Unknown impact"),
                "root_cause": error_info.get("root_cause", "Unknown cause"),
                "immediate_actions": immediate_actions,
                "resolution_steps": resolution_steps,
                "needs_immediate_attention": error_info.get("severity", "MEDIUM") == "HIGH"
            }
        except Exception as e:
            logger.error(f"Error in analyze_log: {e}")
            raise

    def _extract_error_details(self, log: ElkLog) -> dict:
        """Extract structured error details from log message"""
        message = log.source.message
        
        try:
            # Try to parse JSON if message is in JSON format
            if message.startswith('{'):
                data = json.loads(message)
                message = data.get('message', message)
                status_code = data.get('status_code') or data.get('code')
            else:
                status_code = None

            # Extract status code from message if not found in JSON
            if not status_code:
                status_match = re.search(r'status(?:\s+code)?[:=\s]+(\d{3})', message, re.IGNORECASE)
                if status_match:
                    status_code = int(status_match.group(1))

            # Common error patterns with their types
            error_patterns = [
                # HTTP/API Errors
                (r'(\d{3})(?:\s+)?(?:error)?\s*[:-]\s*(.+?)(?=\s*at\s|$)',
                 lambda m: ("HTTP Error", f"Status {m.group(1)}: {m.group(2).strip()}", int(m.group(1)))),
                
                # Database Errors
                (r'SQLSTATE\[(\w+)\].*?(?:errno\s*=\s*(\d+))?\s*(.+?)(?=\s*\(|$)',
                 lambda m: ("Database Error", f"SQL Error {m.group(1)}: {m.group(3).strip()}", 500)),
                
                # Authentication Errors
                (r'(auth\w*\s+failed|permission\s+denied|access\s+denied)(.+?)(?=\s*at\s|$)',
                 lambda m: ("Authentication Error", m.group(0), 401)),
                
                # Connection Errors
                (r'(connection\s+\w+|refused|timed?\s*out|couldn\'t\s+connect)(.+?)(?=\s*at\s|$)',
                 lambda m: ("Connection Error", f"Connection failed: {m.group(0)}", 503)),
                
                # Application Errors
                (r'exception\s*[\'"](.+?)[\'"].*?message\s*[\'"](.+?)[\'"]',
                 lambda m: ("Application Error", f"{m.group(1)}: {m.group(2)}", 500))
            ]

            # Try each pattern
            for pattern, formatter in error_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    error_type, error_message, default_status = formatter(match)
                    return {
                        "error_type": error_type,
                        "error_message": error_message,
                        "status_code": status_code or default_status
                    }

            # Default case - clean up message
            cleaned = re.sub(r'\s+', ' ', message).strip()
            return {
                "error_type": "Unknown Error",
                "error_message": cleaned[:150] + ('...' if len(cleaned) > 150 else ''),
                "status_code": status_code or 500
            }

        except Exception as e:
            print(f"Error extracting details: {e}")
            return {
                "error_type": "Parse Error",
                "error_message": message[:150] + ('...' if len(message) > 150 else ''),
                "status_code": 500
            }

    def _parse_analysis(self, analysis: str) -> dict:
        """Parse AI analysis into structured format"""
        severity = "MEDIUM"
        impact = ""
        immediate_actions = []
        resolution_steps = []
        
        sections = analysis.split('\n')
        current_section = ""
        
        for line in sections:
            line = line.strip()
            if not line:
                continue
            
            # Extract severity
            if "severity" in line.lower():
                if "high" in line.lower():
                    severity = "HIGH"
                elif "low" in line.lower():
                    severity = "LOW"
                
            # Extract impact
            elif "impact" in line.lower():
                impact = line.split(":", 1)[1].strip() if ":" in line else line
                
            # Collect actions and steps
            elif line.startswith("-"):
                if "immediate" in current_section:
                    immediate_actions.append(line[1:].strip())
                elif "resolution" in current_section or "preventive" in current_section:
                    resolution_steps.append(line[1:].strip())
            else:
                current_section = line.lower()
        
        return {
            "severity": severity,
            "impact": impact,
            "immediate_actions": immediate_actions,
            "resolution_steps": resolution_steps
        }

    def _extract_specific_error(self, message: str) -> str:
        """Extract specific error from message in human readable format"""
        try:
            # Try to parse JSON if message is in JSON format
            if message.startswith('{'):
                data = json.loads(message)
                if 'message' in data:
                    message = data['message']

            # Common error patterns
            patterns = [
                # SQL errors
                (r'SQLSTATE\[(\w+)\].*?(?:errno\s*=\s*(\d+))?\s*(.+?)(?=\s*\(|$)', 
                 lambda m: f"SQL Error {m.group(1)}: {m.group(3).strip()}"),
                
                # Laravel exceptions
                (r'exception\s*\'(.+?)\'\s*with\s*message\s*\'(.+?)\'',
                 lambda m: f"{m.group(1)}: {m.group(2)}"),
                
                # General error patterns
                (r'error:(.+?)(?=\s*at\s|$)', 
                 lambda m: m.group(1).strip()),
                
                # Connection errors
                (r'(connection\s+\w+|refused|timed?\s*out|couldn\'t\s+connect)(.+?)(?=\s*at\s|$)',
                 lambda m: f"Connection Error: {m.group(0)}"),
                
                # Authentication errors
                (r'(auth\w*\s+failed|permission\s+denied|access\s+denied)(.+?)(?=\s*at\s|$)',
                 lambda m: f"Authentication Error: {m.group(0)}")
            ]

            # Try each pattern
            for pattern, formatter in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    return formatter(match)

            # If no pattern matches, clean up the message
            cleaned = re.sub(r'\s+', ' ', message).strip()
            return cleaned[:150] + ('...' if len(cleaned) > 150 else '')

        except Exception as e:
            print(f"Error extracting specific error: {e}")
            return message[:150] + ('...' if len(message) > 150 else '')

    def _extract_priority(self, analysis: str) -> str:
        """Extract priority level from analysis text."""
        priority_levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        for level in priority_levels:
            if level in analysis.upper():
                return level
        return "MEDIUM"

    def analyze_logs_batch(self, logs: List[ElkLog]) -> List[Dict[str, str]]:
        """Analyze multiple logs and group related issues."""
        analyses = [self.analyze_log(log) for log in logs]
        
        # Group similar errors
        grouped_analyses = self._group_similar_errors(analyses)
        return grouped_analyses

    def _group_similar_errors(self, analyses: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Group similar errors together for batch reporting."""
        # Implementation to group similar errors
        # This could use error patterns, hosts, or other criteria
        return analyses

    async def analyze_custom_prompt(self, prompt: str, context: dict = None) -> dict:
        """Analyze custom prompt and return structured response"""
        try:
            # Add file path detection to the prompt
            formatted_prompt = f"""
            Analyze this context and provide a detailed solution. When referring to code or files,
            please wrap the file paths in backticks (`path/to/file.ext`).
            
            Context:
            {context}
            
            Prompt:
            {prompt}
            
            Provide response in the following format:
            1. Analysis
            2. Recommendations (include file paths in backticks where relevant)
            3. Code Suggestions (include file paths in backticks)
            4. Next Steps
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=0.7
            )
            
            analysis = response.choices[0].message.content
            
            # Parse the response into structured format
            return self._parse_custom_analysis(analysis)
            
        except Exception as e:
            logger.error(f"Error in analyze_custom_prompt: {e}")
            raise

    def _parse_custom_analysis(self, analysis: str) -> dict:
        """Parse custom analysis into structured format"""
        sections = analysis.split('\n')
        result = {
            "analysis": "",
            "recommendations": [],
            "code_suggestions": [],
            "next_steps": []
        }
        
        current_section = ""
        
        for line in sections:
            line = line.strip()
            if not line:
                continue
            
            if "Analysis" in line:
                current_section = "analysis"
            elif "Recommendations" in line:
                current_section = "recommendations"
            elif "Code Suggestions" in line:
                current_section = "code_suggestions"
            elif "Next Steps" in line:
                current_section = "next_steps"
            elif line.startswith("-"):
                if current_section in ["recommendations", "code_suggestions", "next_steps"]:
                    result[current_section].append(line[1:].strip())
            else:
                if current_section == "analysis":
                    result["analysis"] += line + "\n"
        
        return result

    def get_latest_response(self):
        """
        Retrieve the latest analysis response
        """
        try:
            # Get the latest log entry with response
            latest_log = log_repository.get_latest_with_response()
            if latest_log:
                return latest_log.response
            return None
        except Exception as e:
            logger.error(f"Error getting latest response: {str(e)}")
            return None