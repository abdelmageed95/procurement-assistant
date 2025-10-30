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
        print(f"❌ Experiment '{experiment_name}' not found")
        return None

    # Get all runs, sorted by start time
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["start_time DESC"],
        max_results=1
    )

    if not runs:
        print(f"❌ No runs found in experiment '{experiment_name}'")
        return None

    return runs[0]


def get_run_metrics(run_id: str):
    """Get all metrics for a run"""
    client = MlflowClient()
    run = client.get_run(run_id)

    print("=" * 70)
    print("📊 OVERALL EVALUATION RESULTS")
    print("=" * 70)
    print(f"Run ID: {run_id}")
    print(f"Run Name: {run.data.tags.get('mlflow.runName', 'N/A')}")
    print(f"Start Time: {datetime.fromtimestamp(run.info.start_time / 1000)}")
    print(f"Status: {run.info.status}")
    print()

    # Get parameters
    params = run.data.params
    print("📋 EVALUATION PARAMETERS")
    print("-" * 70)
    print(f"Total Queries: {params.get('total_queries', 'N/A')}")
    print(f"Model: {params.get('model', 'N/A')}")
    print(f"Criteria Count: {params.get('criteria_count', 'N/A')}")
    print(f"Evaluation Date: {params.get('evaluation_date', 'N/A')}")
    print()

    # Get metrics
    metrics = run.data.metrics

    print("🎯 OVERALL SCORES (Average Across All Queries)")
    print("-" * 70)

    # Define criteria with their max scores (Total: 100 points)
    criteria = {
        "semantic_correctness/score": {"max": 25, "name": "Semantic Correctness"},
        "query_efficiency/score": {"max": 20, "name": "Query Efficiency"},
        "data_correctness/score": {"max": 25, "name": "Data Correctness"},
        "completeness/score": {"max": 10, "name": "Completeness"},
        "natural_language/score": {"max": 10, "name": "Natural Language"},
        "relevance/score": {"max": 5, "name": "Relevance"},
        "formatting/score": {"max": 5, "name": "Formatting"}
    }

    total_score = 0
    total_possible = 100

    print("\n📊 BY CATEGORY:\n")

    # Category 1: Query Generation Quality (45 points)
    print("1️⃣  Query Generation Quality (45 points)")
    cat1_score = 0
    for key in ["semantic_correctness/score", "query_efficiency/score"]:
        if key in metrics:
            score = metrics[key]
            max_score = criteria[key]["max"]
            name = criteria[key]["name"]
            percentage = (score / max_score * 100) if max_score > 0 else 0
            print(f"  - {name:25s}: {score:5.1f}/{max_score:2d} ({percentage:5.1f}%)")
            cat1_score += score
        else:
            name = criteria[key]["name"]
            print(f"  - {name:25s}: N/A")

    print(f"  {'Category Total':25s}: {cat1_score:5.1f}/45\n")

    # Category 2: Result Accuracy (35 points)
    print("2️⃣  Result Accuracy (35 points)")
    cat2_score = 0
    for key in ["data_correctness/score", "completeness/score"]:
        if key in metrics:
            score = metrics[key]
            max_score = criteria[key]["max"]
            name = criteria[key]["name"]
            percentage = (score / max_score * 100) if max_score > 0 else 0
            print(f"  - {name:25s}: {score:5.1f}/{max_score:2d} ({percentage:5.1f}%)")
            cat2_score += score
        else:
            name = criteria[key]["name"]
            print(f"  - {name:25s}: N/A")

    print(f"  {'Category Total':25s}: {cat2_score:5.1f}/35\n")

    # Category 3: Response Quality (20 points)
    print("3️⃣  Response Quality (20 points)")
    cat3_score = 0
    for key in ["natural_language/score", "relevance/score", "formatting/score"]:
        if key in metrics:
            score = metrics[key]
            max_score = criteria[key]["max"]
            name = criteria[key]["name"]
            percentage = (score / max_score * 100) if max_score > 0 else 0
            print(f"  - {name:25s}: {score:5.1f}/{max_score:2d} ({percentage:5.1f}%)")
            cat3_score += score
        else:
            name = criteria[key]["name"]
            print(f"  - {name:25s}: N/A")

    print(f"  {'Category Total':25s}: {cat3_score:5.1f}/20\n")

    # Overall total
    total_score = cat1_score + cat2_score + cat3_score
    overall_percentage = (total_score / total_possible * 100) if total_possible > 0 else 0

    print("=" * 70)
    print(f"🎯 OVERALL TOTAL SCORE: {total_score:.1f}/{total_possible} ({overall_percentage:.1f}%)")
    print("=" * 70)

    return run, metrics


def get_artifacts_summary(run_id: str):
    """Show available artifacts"""
    client = MlflowClient()

    print("\n📁 AVAILABLE ARTIFACTS")
    print("-" * 70)

    try:
        artifacts = client.list_artifacts(run_id)

        if not artifacts:
            print("No artifacts found")
            return

        for artifact in artifacts:
            if artifact.is_dir:
                print(f"📂 {artifact.path}/")
                # List files in directory
                sub_artifacts = client.list_artifacts(run_id, artifact.path)
                for sub in sub_artifacts:
                    print(f"   📄 {sub.path}")
            else:
                print(f"📄 {artifact.path}")

        print("\n💡 To download artifacts:")
        print(f"   mlflow artifacts download -r {run_id} -d ./results")

    except Exception as e:
        print(f"❌ Error listing artifacts: {e}")


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

    print(f"\n✅ Results exported to: {output_file}")


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
        print(f"📊 Retrieving run: {run_id}\n")
    elif args.latest:
        run = get_latest_run(args.experiment)
        if not run:
            return
        run_id = run.info.run_id
        print(f"📊 Using latest run: {run_id}\n")
    else:
        # Try to get latest by default
        run = get_latest_run(args.experiment)
        if not run:
            print("\n💡 Usage:")
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
    print("🌐 VIEW IN MLFLOW UI")
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
