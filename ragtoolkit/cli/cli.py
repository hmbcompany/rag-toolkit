"""
RAG Toolkit CLI for batch evaluation and testing.

Provides commands for:
- Batch evaluation of Q&A pairs
- Testing and validation
- Configuration management
"""

import asyncio
import csv
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from ..sdk.evaluator import CompositeScorer, GroundingScorer, HelpfulnessScorer, SafetyScorer


app = typer.Typer(
    name="ragtoolkit",
    help="RAG Toolkit CLI for evaluation and testing",
    add_completion=False
)

console = Console()


@app.command()
def eval(
    file: Path = typer.Argument(..., help="Path to CSV/JSONL file with test cases"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file for results"),
    format: str = typer.Option("json", "--format", "-f", help="Output format (json, markdown, csv)"),
    model_config: Optional[Path] = typer.Option(None, "--config", "-c", help="Model configuration file"),
    openai_api_key: Optional[str] = typer.Option(None, "--openai-key", help="OpenAI API key for LLM grading"),
    grounding_threshold: float = typer.Option(0.3, "--grounding-threshold", help="Grounding threshold (0-1)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """
    Batch evaluate Q&A pairs from a file.
    
    File format should contain columns: question, expected_context, expected_answer
    """
    if not file.exists():
        rprint(f"[red]Error: File {file} not found[/red]")
        raise typer.Exit(1)
    
    # Load test cases
    test_cases = load_test_cases(file)
    if not test_cases:
        rprint("[red]Error: No test cases found in file[/red]")
        raise typer.Exit(1)
    
    rprint(f"[green]Loaded {len(test_cases)} test cases[/green]")
    
    # Initialize evaluators
    scorers = initialize_scorers(
        openai_api_key=openai_api_key,
        grounding_threshold=grounding_threshold
    )
    
    # Run evaluation
    results = run_batch_evaluation(test_cases, scorers, verbose=verbose)
    
    # Generate report
    report = generate_report(results, test_cases)
    
    # Output results
    if output:
        save_results(report, output, format)
        rprint(f"[green]Results saved to {output}[/green]")
    else:
        display_results(report, format)


@app.command()
def test(
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="RAG Toolkit API URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key for authentication"),
    test_traces: int = typer.Option(10, "--count", help="Number of test traces to generate"),
    seed_hallucinations: bool = typer.Option(False, "--seed-hallucinations", help="Include hallucinated responses for testing")
):
    """Test the RAG Toolkit system with sample data."""
    from ..sdk.tracer import configure_tracker, trace
    import httpx
    
    # Configure tracker
    configure_tracker(api_url=api_url, api_key=api_key)
    
    # Test API connectivity
    try:
        response = httpx.get(f"{api_url}/")
        response.raise_for_status()
        rprint(f"[green]✓ Connected to API at {api_url}[/green]")
    except Exception as e:
        rprint(f"[red]✗ Failed to connect to API: {e}[/red]")
        raise typer.Exit(1)
    
    # Generate test traces
    rprint(f"[blue]Generating {test_traces} test traces...[/blue]")
    
    generated_traces = generate_test_traces(test_traces, seed_hallucinations)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Sending traces...", total=len(generated_traces))
        
        for i, trace_data in enumerate(generated_traces):
            # Use the tracer to send the trace
            @trace
            def mock_rag_pipeline(query: str) -> str:
                return trace_data["answer"]
            
            # Simulate the RAG pipeline
            mock_rag_pipeline(trace_data["query"])
            
            progress.update(task, advance=1)
    
    rprint(f"[green]✓ Sent {len(generated_traces)} test traces[/green]")
    rprint(f"[blue]Check the dashboard at {api_url.replace('api.', '')} to see results[/blue]")


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="Set API URL"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Set API key"),
    openai_key: Optional[str] = typer.Option(None, "--openai-key", help="Set OpenAI API key")
):
    """Manage RAG Toolkit configuration."""
    config_file = Path.home() / ".ragtoolkit" / "config.json"
    config_file.parent.mkdir(exist_ok=True)
    
    # Load existing config
    if config_file.exists():
        with open(config_file) as f:
            config_data = json.load(f)
    else:
        config_data = {}
    
    if show:
        rprint("[blue]Current configuration:[/blue]")
        table = Table()
        table.add_column("Setting")
        table.add_column("Value")
        
        for key, value in config_data.items():
            if "key" in key.lower() and value:
                value = "*" * len(value)  # Hide API keys
            table.add_row(key, str(value))
        
        console.print(table)
        return
    
    # Update config
    if api_url:
        config_data["api_url"] = api_url
    if api_key:
        config_data["api_key"] = api_key
    if openai_key:
        config_data["openai_api_key"] = openai_key
    
    # Save config
    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)
    
    rprint("[green]Configuration updated[/green]")


def load_test_cases(file: Path) -> List[Dict[str, Any]]:
    """Load test cases from CSV or JSONL file."""
    test_cases = []
    
    if file.suffix.lower() == ".csv":
        with open(file, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                test_cases.append({
                    "question": row.get("question", ""),
                    "expected_context": row.get("expected_context", ""),
                    "expected_answer": row.get("expected_answer", "")
                })
    elif file.suffix.lower() in [".jsonl", ".json"]:
        with open(file) as f:
            if file.suffix.lower() == ".json":
                data = json.load(f)
                if isinstance(data, list):
                    test_cases = data
                else:
                    test_cases = [data]
            else:  # .jsonl
                for line in f:
                    test_cases.append(json.loads(line.strip()))
    
    return test_cases


def initialize_scorers(openai_api_key: Optional[str], grounding_threshold: float) -> Dict[str, Any]:
    """Initialize evaluation scorers."""
    return {
        "grounding": GroundingScorer(threshold=grounding_threshold),
        "helpfulness": HelpfulnessScorer(api_key=openai_api_key),
        "safety": SafetyScorer(api_key=openai_api_key),
        "composite": CompositeScorer(
            GroundingScorer(threshold=grounding_threshold),
            HelpfulnessScorer(api_key=openai_api_key),
            SafetyScorer(api_key=openai_api_key)
        )
    }


def run_batch_evaluation(test_cases: List[Dict[str, Any]], scorers: Dict[str, Any], verbose: bool = False) -> List[Dict[str, Any]]:
    """Run batch evaluation on test cases."""
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Evaluating...", total=len(test_cases))
        
        for i, test_case in enumerate(test_cases):
            question = test_case.get("question", "")
            expected_answer = test_case.get("expected_answer", "")
            expected_context = test_case.get("expected_context", "")
            
            if verbose:
                console.print(f"[dim]Evaluating case {i+1}: {question[:50]}...[/dim]")
            
            # Prepare context chunks
            chunks = []
            if expected_context:
                chunks = [{"text": expected_context}]
            
            # Run evaluation
            result = asyncio.run(evaluate_single_case(
                question, expected_answer, chunks, scorers
            ))
            
            result.update({
                "case_id": i + 1,
                "question": question,
                "expected_answer": expected_answer,
                "expected_context": expected_context
            })
            
            results.append(result)
            progress.update(task, advance=1)
    
    return results


async def evaluate_single_case(question: str, answer: str, chunks: List[Dict], scorers: Dict) -> Dict[str, Any]:
    """Evaluate a single test case."""
    try:
        composite_score = await scorers["composite"].score(
            answer=answer,
            retrieved_chunks=chunks,
            query=question
        )
        
        return {
            "grounding_score": composite_score.grounding.score if composite_score.grounding else 0,
            "helpfulness_score": composite_score.helpfulness.score if composite_score.helpfulness else 0,
            "safety_score": composite_score.safety.score if composite_score.safety else 0,
            "overall_score": composite_score.overall_score,
            "traffic_light": composite_score.overall_traffic_light.value,
            "grounding_explanation": composite_score.grounding.explanation if composite_score.grounding else "",
            "helpfulness_explanation": composite_score.helpfulness.explanation if composite_score.helpfulness else "",
            "safety_explanation": composite_score.safety.explanation if composite_score.safety else "",
            "error": None
        }
    except Exception as e:
        return {
            "grounding_score": 0,
            "helpfulness_score": 0,
            "safety_score": 0,
            "overall_score": 0,
            "traffic_light": "red",
            "grounding_explanation": "",
            "helpfulness_explanation": "",
            "safety_explanation": "",
            "error": str(e)
        }


def generate_report(results: List[Dict[str, Any]], test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate evaluation report."""
    total_cases = len(results)
    successful_cases = len([r for r in results if r.get("error") is None])
    
    # Calculate averages
    avg_grounding = sum(r["grounding_score"] for r in results if r.get("error") is None) / successful_cases if successful_cases > 0 else 0
    avg_helpfulness = sum(r["helpfulness_score"] for r in results if r.get("error") is None) / successful_cases if successful_cases > 0 else 0
    avg_safety = sum(r["safety_score"] for r in results if r.get("error") is None) / successful_cases if successful_cases > 0 else 0
    avg_overall = sum(r["overall_score"] for r in results if r.get("error") is None) / successful_cases if successful_cases > 0 else 0
    
    # Traffic light distribution
    traffic_lights = [r["traffic_light"] for r in results if r.get("error") is None]
    traffic_light_dist = {
        "green": traffic_lights.count("green"),
        "amber": traffic_lights.count("amber"),
        "red": traffic_lights.count("red")
    }
    
    return {
        "summary": {
            "total_cases": total_cases,
            "successful_cases": successful_cases,
            "error_cases": total_cases - successful_cases,
            "success_rate": successful_cases / total_cases * 100 if total_cases > 0 else 0
        },
        "scores": {
            "avg_grounding": round(avg_grounding, 3),
            "avg_helpfulness": round(avg_helpfulness, 3),
            "avg_safety": round(avg_safety, 3),
            "avg_overall": round(avg_overall, 3)
        },
        "traffic_light_distribution": traffic_light_dist,
        "detailed_results": results,
        "generated_at": time.time()
    }


def generate_test_traces(count: int, seed_hallucinations: bool = False) -> List[Dict[str, Any]]:
    """Generate test traces for system testing."""
    import random
    
    sample_queries = [
        "What is the capital of France?",
        "How does machine learning work?",
        "What are the benefits of renewable energy?",
        "Explain quantum computing in simple terms",
        "What is the history of the internet?",
        "How do vaccines work?",
        "What causes climate change?",
        "Explain the theory of relativity",
        "What is artificial intelligence?",
        "How do solar panels work?"
    ]
    
    sample_answers = [
        "Paris is the capital of France, known for its rich history and culture.",
        "Machine learning uses algorithms to learn patterns from data without explicit programming.",
        "Renewable energy reduces carbon emissions and provides sustainable power sources.",
        "Quantum computing uses quantum mechanical phenomena to process information.",
        "The internet evolved from ARPANET in the 1960s to become a global network.",
        "Vaccines train the immune system to recognize and fight specific diseases.",
        "Climate change is primarily caused by greenhouse gas emissions from human activities.",
        "Einstein's theory describes the relationship between space, time, and gravity.",
        "AI involves creating systems that can perform tasks requiring human intelligence.",
        "Solar panels convert sunlight into electricity using photovoltaic cells."
    ]
    
    hallucinated_answers = [
        "The capital of France is actually London, which moved there in 1823.",
        "Machine learning works by having computers eat data and digest it into knowledge.",
        "Renewable energy is actually harmful to the environment and causes more pollution.",
        "Quantum computing was invented by aliens and given to humans in 1955.",
        "The internet was created by a single person named Bob Internet in 1990."
    ]
    
    traces = []
    for i in range(count):
        query = random.choice(sample_queries)
        
        if seed_hallucinations and random.random() < 0.2:  # 20% hallucinations
            answer = random.choice(hallucinated_answers)
        else:
            answer = random.choice(sample_answers)
        
        traces.append({
            "query": query,
            "answer": answer,
            "context": f"Context for: {query}"
        })
    
    return traces


def save_results(report: Dict[str, Any], output: Path, format: str):
    """Save results to file."""
    if format == "json":
        with open(output, "w") as f:
            json.dump(report, f, indent=2)
    elif format == "markdown":
        save_markdown_report(report, output)
    elif format == "csv":
        save_csv_report(report, output)


def save_markdown_report(report: Dict[str, Any], output: Path):
    """Save report as markdown."""
    md_content = f"""# RAG Toolkit Evaluation Report

Generated at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report['generated_at']))}

## Summary

- **Total Cases**: {report['summary']['total_cases']}
- **Successful Cases**: {report['summary']['successful_cases']}
- **Error Cases**: {report['summary']['error_cases']}
- **Success Rate**: {report['summary']['success_rate']:.1f}%

## Average Scores

- **Grounding**: {report['scores']['avg_grounding']:.3f}
- **Helpfulness**: {report['scores']['avg_helpfulness']:.3f}
- **Safety**: {report['scores']['avg_safety']:.3f}
- **Overall**: {report['scores']['avg_overall']:.3f}

## Traffic Light Distribution

- 🟢 **Green**: {report['traffic_light_distribution']['green']}
- 🟡 **Amber**: {report['traffic_light_distribution']['amber']}
- 🔴 **Red**: {report['traffic_light_distribution']['red']}

## Detailed Results

| Case | Question | Overall Score | Traffic Light | Error |
|------|----------|---------------|---------------|-------|
"""
    
    for result in report['detailed_results']:
        error = result.get('error', '')
        md_content += f"| {result['case_id']} | {result['question'][:50]}... | {result['overall_score']:.3f} | {result['traffic_light']} | {error} |\n"
    
    with open(output, "w") as f:
        f.write(md_content)


def save_csv_report(report: Dict[str, Any], output: Path):
    """Save detailed results as CSV."""
    with open(output, "w", newline='') as csvfile:
        fieldnames = ['case_id', 'question', 'expected_answer', 'grounding_score', 
                     'helpfulness_score', 'safety_score', 'overall_score', 
                     'traffic_light', 'error']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in report['detailed_results']:
            writer.writerow({
                'case_id': result['case_id'],
                'question': result['question'],
                'expected_answer': result['expected_answer'],
                'grounding_score': result['grounding_score'],
                'helpfulness_score': result['helpfulness_score'],
                'safety_score': result['safety_score'],
                'overall_score': result['overall_score'],
                'traffic_light': result['traffic_light'],
                'error': result.get('error', '')
            })


def display_results(report: Dict[str, Any], format: str):
    """Display results in terminal."""
    rprint("\n[bold blue]RAG Toolkit Evaluation Report[/bold blue]")
    rprint("=" * 40)
    
    # Summary
    rprint(f"\n[bold]Summary:[/bold]")
    rprint(f"Total Cases: {report['summary']['total_cases']}")
    rprint(f"Successful: {report['summary']['successful_cases']}")
    rprint(f"Errors: {report['summary']['error_cases']}")
    rprint(f"Success Rate: {report['summary']['success_rate']:.1f}%")
    
    # Scores
    rprint(f"\n[bold]Average Scores:[/bold]")
    rprint(f"Grounding: {report['scores']['avg_grounding']:.3f}")
    rprint(f"Helpfulness: {report['scores']['avg_helpfulness']:.3f}")
    rprint(f"Safety: {report['scores']['avg_safety']:.3f}")
    rprint(f"Overall: {report['scores']['avg_overall']:.3f}")
    
    # Traffic lights
    rprint(f"\n[bold]Traffic Light Distribution:[/bold]")
    rprint(f"🟢 Green: {report['traffic_light_distribution']['green']}")
    rprint(f"🟡 Amber: {report['traffic_light_distribution']['amber']}")
    rprint(f"🔴 Red: {report['traffic_light_distribution']['red']}")


if __name__ == "__main__":
    app() 