import click
import httpx
import json
import os
from typing import Optional
import sys

class LogAnalyzer:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def analyze_prompt(self, prompt: str, context: dict = None) -> dict:
        """Send prompt for analysis"""
        try:
            response = self.client.post(
                f"{self.base_url}/analyze-prompt",
                json={"prompt": prompt, "context": context or {}}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_analysis(self, batch_id: str) -> dict:
        """Get analysis results"""
        try:
            response = self.client.get(f"{self.base_url}/analyze/{batch_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

@click.group()
def cli():
    """Log Analysis CLI"""
    pass

@cli.command()
@click.option('--prompt', '-p', required=True, help='Analysis prompt')
@click.option('--context', '-c', help='JSON context string')
@click.option('--output', '-o', help='Output file path')
def analyze(prompt: str, context: Optional[str], output: Optional[str]):
    """Analyze prompt with optional context"""
    analyzer = LogAnalyzer()
    
    try:
        context_dict = json.loads(context) if context else {}
    except json.JSONDecodeError:
        click.echo("Error: Context must be valid JSON")
        sys.exit(1)
    
    result = analyzer.analyze_prompt(prompt, context_dict)
    
    if output:
        with open(output, 'w') as f:
            json.dump(result, f, indent=2)
        click.echo(f"Results saved to {output}")
    else:
        click.echo(json.dumps(result, indent=2))

@cli.command()
@click.argument('batch_id')
@click.option('--output', '-o', help='Output file path')
def get_analysis(batch_id: str, output: Optional[str]):
    """Get analysis results for a batch ID"""
    analyzer = LogAnalyzer()
    result = analyzer.get_analysis(batch_id)
    
    if output:
        with open(output, 'w') as f:
            json.dump(result, f, indent=2)
        click.echo(f"Results saved to {output}")
    else:
        click.echo(json.dumps(result, indent=2))

if __name__ == '__main__':
    cli() 