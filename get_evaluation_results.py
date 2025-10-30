#!/usr/bin/env python3
"""
Script to retrieve and display evaluation results from MLflow

Usage:
    python get_evaluation_results.py
    python get_evaluation_results.py --run-id YOUR_RUN_ID
    python get_evaluation_results.py --latest  # Get latest run
"""

import argparse
import mlflow
from mlflow.tracking import MlflowClient
import pandas as pd
from datetime import datetime
import json


def get_latest_run(experiment_name: str = "procurement-assistant-evaluation"):
    """Get the most recent run from the experiment"""
    client = MlflowClient()

    # Get experiment
    experiment = client.get_experiment_by_name(experiment_name)
    if not experiment:
        print(f"Error: Experiment '{experiment_name}' not found")
        return None

    # Get all runs, sorted by start time
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["start_time DESC"],
        max_results=1
    )

    if not runs:
        print(f"Error: No runs found in experiment '{experiment_name}'")
        return None

    return runs[0]


def get_run_metrics(run_id: str):
    """Get all metrics for a run"""
    client = MlflowClient()
    run = client.get_run(run_id)

    print("=" * 70)
    print("OVERALL EVALUATION RESULTS")
    print("=" * 70)
    print(f"Run ID: {run_id}")
    print(f"Run Name: {run.data.tags.get('mlflow.runName', 'N/A')}")
    print(f"Start Time: {datetime.fromtimestamp(run.info.start_time / 1000)}")
    print(f"Status: {run.info.status}")
    print()

    # Get parameters
    params = run.data.params
    print("EVALUATION PARAMETERS")
    print("-" * 70)
    print(f"Total Queries: {params.get('total_queries', 'N/A')}")
    print(f"Model: {params.get('model', 'N/A')}")
    print(f"Criteria Count: {params.get('criteria_count', 'N/A')}")
    print(f"Evaluation Date: {params.get('evaluation_date', 'N/A')}")
    print()

    # Get metrics
    metrics = run.data.metrics

    # Display summary metrics if available
    if any(key in metrics for key in ['success_rate', 'failure_rate', 'average_score', 'average_execution_time']):
        print("SUMMARY METRICS")
        print("-" * 70)
        if 'success_rate' in metrics:
            print(f"Success Rate: {metrics['success_rate']:.2f}%")
        if 'failure_rate' in metrics:
            print(f"Failure Rate: {metrics['failure_rate']:.2f}%")
        if 'average_score' in metrics:
            print(f"Average Score: {metrics['average_score']:.2f}/100")
        if 'average_execution_time' in metrics:
            print(f"Average Execution Time: {metrics['average_execution_time']:.2f}s")
        print()

    print("OVERALL SCORES (Average Across All Queries)")
    print("-" * 70)

    # Define criteria with their max scores (Total: 100 points)
    criteria = {
        "avg_syntax_correctness": {"max": 15, "name": "Syntax Correctness"},
        "avg_semantic_correctness": {"max": 20, "name": "Semantic Correctness"},
        "avg_query_efficiency": {"max": 15, "name": "Query Efficiency"},
        "avg_data_correctness": {"max": 20, "name": "Data Correctness"},
        "avg_completeness": {"max": 10, "name": "Completeness"},
        "avg_natural_language": {"max": 10, "name": "Natural Language"},
        "avg_relevance": {"max": 5, "name": "Relevance"},
        "avg_formatting": {"max": 5, "name": "Formatting"}
    }

    total_score = 0
    total_possible = 100

    print("\nBY CATEGORY:\n")

    # Category 1: Query Generation Quality (50 points)
    print("1. Query Generation Quality (50 points)")
    cat1_score = 0
    for key in ["avg_syntax_correctness", "avg_semantic_correctness", "avg_query_efficiency"]:
        if key in metrics:
            score = metrics[key]
            max_score = criteria[key]["max"]
            name = criteria[key]["name"]
            percentage = (score / max_score * 100) if max_score > 0 else 0
            print(f"  - {name:25s}: {score:5.2f}/{max_score:2d} ({percentage:5.2f}%)")
            cat1_score += score
        else:
            name = criteria[key]["name"]
            print(f"  - {name:25s}: N/A")

    print(f"  {'Category Total':25s}: {cat1_score:5.2f}/50\n")

    # Category 2: Result Accuracy (30 points)
    print("2. Result Accuracy (30 points)")
    cat2_score = 0
    for key in ["avg_data_correctness", "avg_completeness"]:
        if key in metrics:
            score = metrics[key]
            max_score = criteria[key]["max"]
            name = criteria[key]["name"]
            percentage = (score / max_score * 100) if max_score > 0 else 0
            print(f"  - {name:25s}: {score:5.2f}/{max_score:2d} ({percentage:5.2f}%)")
            cat2_score += score
        else:
            name = criteria[key]["name"]
            print(f"  - {name:25s}: N/A")

    print(f"  {'Category Total':25s}: {cat2_score:5.2f}/30\n")

    # Category 3: Response Quality (20 points)
    print("3. Response Quality (20 points)")
    cat3_score = 0
    for key in ["avg_natural_language", "avg_relevance", "avg_formatting"]:
        if key in metrics:
            score = metrics[key]
            max_score = criteria[key]["max"]
            name = criteria[key]["name"]
            percentage = (score / max_score * 100) if max_score > 0 else 0
            print(f"  - {name:25s}: {score:5.2f}/{max_score:2d} ({percentage:5.2f}%)")
            cat3_score += score
        else:
            name = criteria[key]["name"]
            print(f"  - {name:25s}: N/A")

    print(f"  {'Category Total':25s}: {cat3_score:5.2f}/20\n")

    # Overall total
    total_score = cat1_score + cat2_score + cat3_score
    overall_percentage = (total_score / total_possible * 100) if total_possible > 0 else 0

    print("=" * 70)
    print(f"OVERALL TOTAL SCORE: {total_score:.2f}/{total_possible} ({overall_percentage:.2f}%)")
    print("=" * 70)

    return run, metrics


def get_artifacts_summary(run_id: str):
    """Show available artifacts"""
    client = MlflowClient()

    print("\nAVAILABLE ARTIFACTS")
    print("-" * 70)

    try:
        artifacts = client.list_artifacts(run_id)

        if not artifacts:
            print("No artifacts found")
            return

        for artifact in artifacts:
            if artifact.is_dir:
                print(f"[DIR] {artifact.path}/")
                # List files in directory
                sub_artifacts = client.list_artifacts(run_id, artifact.path)
                for sub in sub_artifacts:
                    print(f"   [FILE] {sub.path}")
            else:
                print(f"[FILE] {artifact.path}")

        print("\nTo download artifacts:")
        print(f"   mlflow artifacts download -r {run_id} -d ./results")

    except Exception as e:
        print(f"Error listing artifacts: {e}")


def export_to_json(run_id: str, output_file: str = "evaluation_results.json"):
    """Export results to JSON file"""
    client = MlflowClient()
    run = client.get_run(run_id)

    results = {
        "run_info": {
            "run_id": run_id,
            "run_name": run.data.tags.get('mlflow.runName', 'N/A'),
            "experiment_name": "procurement-assistant-evaluation",
            "start_time": datetime.fromtimestamp(run.info.start_time / 1000).isoformat(),
            "end_time": datetime.fromtimestamp(run.info.end_time / 1000).isoformat() if run.info.end_time else None,
            "status": run.info.status
        },
        "parameters": dict(run.data.params),
        "metrics": dict(run.data.metrics),
        "tags": dict(run.data.tags)
    }

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Get MLflow evaluation results")
    parser.add_argument("--run-id", type=str, help="Specific run ID to retrieve")
    parser.add_argument("--latest", action="store_true", help="Get latest run")
    parser.add_argument("--export", type=str, help="Export to JSON file")
    parser.add_argument("--experiment", type=str, default="procurement-assistant-evaluation",
                        help="Experiment name")

    args = parser.parse_args()

    # Determine which run to use
    if args.run_id:
        run_id = args.run_id
        print(f"Retrieving run: {run_id}\n")
    elif args.latest:
        run = get_latest_run(args.experiment)
        if not run:
            return
        run_id = run.info.run_id
        print(f"Using latest run: {run_id}\n")
    else:
        # Try to get latest by default
        run = get_latest_run(args.experiment)
        if not run:
            print("\nUsage:")
            print("   python get_evaluation_results.py --latest")
            print("   python get_evaluation_results.py --run-id YOUR_RUN_ID")
            return
        run_id = run.info.run_id

    # Get and display metrics
    run, metrics = get_run_metrics(run_id)

    # Show artifacts
    get_artifacts_summary(run_id)

    # Export if requested
    if args.export:
        export_to_json(run_id, args.export)

    # Show how to view in UI
    print("\n" + "=" * 70)
    print("VIEW IN MLFLOW UI")
    print("-" * 70)
    print("1. Open: http://localhost:5000")
    print(f"2. Go to experiment: {args.experiment}")
    print(f"3. Click on run: {run.data.tags.get('mlflow.runName', 'N/A')}")
    print("4. Check tabs:")
    print("   - Metrics: Aggregated scores")
    print("   - Traces: Individual query scores")
    print("   - Artifacts: Detailed results files")
    print("=" * 70)


if __name__ == "__main__":
    main()
