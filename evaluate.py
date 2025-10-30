#!/usr/bin/env python3
"""
Unified Procurement Assistant Evaluation Framework

Combines the best of both evaluation approaches:
- MLflow GenAI standardized pipeline (mlflow.genai.evaluate)
- Detailed 8-criteria scoring system
- MongoDB query validation
- Prompt registry and versioning
- Comprehensive artifact logging

Evaluation Criteria (100 points total):
1. Query Generation Quality (50%)
   - Syntax Correctness (15%)
   - Semantic Correctness (20%)
   - Query Efficiency (15%)

2. Result Accuracy (30%)
   - Data Correctness (20%)
   - Completeness (10%)

3. Response Quality (20%)
   - Natural Language (10%)
   - Relevance (5%)
   - Formatting (5%)

Usage:
    python evaluate.py --sample 5
    python evaluate.py --queries evaluate.txt
    python evaluate.py --help
"""

import json
import time
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import mlflow
import mlflow.genai
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from openai import OpenAI
import os
import warnings
import logging

# Suppress OpenTelemetry async context warnings
warnings.filterwarnings("ignore", message=".*was created in a different Context.*")
logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)

# Import the system
from procurement_agent.workflow import ProcurementWorkflow
from procurement_agent.config import Config


class UnifiedEvaluationFramework:
    """
    Unified evaluation framework combining:
    - MLflow GenAI standardized pipeline
    - Detailed custom scoring (8 criteria)
    - MongoDB validation
    - Comprehensive tracking
    """

    def __init__(
        self,
        experiment_name: str = "procurement-assistant-evaluation",
        run_name: Optional[str] = None
    ):
        # Initialize MLflow
        mlflow.set_experiment(experiment_name)
        self.run_name = run_name or f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Enable MLflow tracing for LangGraph and OpenAI
        mlflow.langchain.autolog()
        mlflow.openai.autolog()

        # Initialize system
        load_dotenv()
        self.workflow = ProcurementWorkflow()
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Connect to MongoDB
        self.mongo_client = MongoClient(Config.MONGO_URI)
        self.db = self.mongo_client[Config.MONGO_DB]
        self.collection = self.db[Config.MONGO_COLLECTION]

        # Get schema
        self.schema = self._get_schema()

        # Load system prompts
        self.system_prompts = self._load_system_prompts()

        # Create judges
        self.judges = self._create_judges()

        # Statistics
        self.token_usage = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
        }

        print("✅ Unified Evaluation Framework initialized")
        print(f"📊 Experiment: {experiment_name}")
        print(f"🏷️  Run Name: {self.run_name}\n")

    def _get_schema(self) -> Dict:
        """Get MongoDB collection schema"""
        try:
            from procurement_agent.mongodb_query import MongoDBQueryAgent
            agent = MongoDBQueryAgent(
                mongo_uri=Config.MONGO_URI,
                db_name=Config.MONGO_DB,
                collection_name=Config.MONGO_COLLECTION
            )
            schema = agent.get_collection_schema()
            print(f"📊 Loaded schema with {len(schema)} fields")
            return schema
        except Exception as e:
            print(f"⚠️  Schema loading failed: {e}")
            return {}

    def _load_system_prompts(self) -> Dict[str, str]:
        """Load all system prompts"""
        from procurement_agent.prompts.prompts import SYSTEM_PROMPT as MONGODB_SYSTEM_PROMPT

        # MongoDB Query Agent prompt with schema filled in
        schema_str = json.dumps(self.schema, indent=2) if self.schema else "[Schema not available]"
        mongodb_prompt = MONGODB_SYSTEM_PROMPT.format(schema_context=schema_str)

        # Router and Chat agent prompts (simplified versions)
        router_prompt = "You are a routing assistant that classifies user messages as 'data_query' or 'general_chat'."
        chat_agent_prompt = "You are a friendly assistant helping users with general questions and greetings."

        return {
            "mongodb_query_agent": mongodb_prompt,
            "router_agent": router_prompt,
            "chat_agent": chat_agent_prompt
        }

    def _create_judges(self) -> List:
        """Create MLflow GenAI judges for all 8 criteria"""
        judges = []

        print("🏗️  Creating evaluation judges...")

        # 1. Semantic Correctness Judge (25 points)
        try:
            semantic_judge = mlflow.genai.make_judge(
                name="semantic_correctness",
                instructions="""Evaluate if the query semantically matches the user's intent.

User Question: {{ inputs }}
AI Response: {{ outputs }}

Does the response answer what the user actually asked?
Are the correct fields, operations, and filters being used?

Score from 0-25:
- 25 = Perfect match, answers exactly what was asked
- 19 = Mostly correct, minor semantic issues
- 13 = Partially correct, some misunderstanding
- 6 = Mostly wrong, major semantic issues
- 0 = Completely wrong, doesn't answer the question

Provide your score (0-25) and rationale.""",
                model="openai:/gpt-4o-mini"
            )
            judges.append(semantic_judge)
            print("  ✅ Semantic Correctness judge")
        except Exception as e:
            print(f"  ⚠️  Semantic judge failed: {e}")

        # 2. Query Efficiency Judge (20 points)
        try:
            efficiency_judge = mlflow.genai.make_judge(
                name="query_efficiency",
                instructions="""Evaluate query efficiency based on the response.

User Query: {{ inputs }}
AI Response: {{ outputs }}

Consider:
- Are filters applied early?
- Is there appropriate use of limits?
- Are indexes likely being used?
- Is the query unnecessarily complex?

Score from 0-20:
- 20 = Highly efficient query design
- 15 = Reasonably efficient
- 10 = Moderately efficient
- 5 = Inefficient but functional
- 0 = Very inefficient, performance issues likely

Provide your score (0-20) and rationale.""",
                model="openai:/gpt-4o-mini"
            )
            judges.append(efficiency_judge)
            print("  ✅ Query Efficiency judge")
        except Exception as e:
            print(f"  ⚠️  Efficiency judge failed: {e}")

        # 3. Data Correctness Judge (25 points)
        try:
            data_judge = mlflow.genai.make_judge(
                name="data_correctness",
                instructions="""Evaluate if the data in the response appears correct.

User Query: {{ inputs }}
AI Response: {{ outputs }}

Check:
- Do numbers seem reasonable?
- Are results logical and consistent?
- Are there any obvious data errors?
- Does the response include actual data (not fabricated)?

Score from 0-25:
- 25 = Data appears completely correct and accurate
- 19 = Mostly correct data, minor issues
- 13 = Some data issues or inconsistencies
- 6 = Major data problems
- 0 = Data is incorrect or fabricated

Provide your score (0-25) and rationale.""",
                model="openai:/gpt-4o-mini"
            )
            judges.append(data_judge)
            print("  ✅ Data Correctness judge")
        except Exception as e:
            print(f"  ⚠️  Data correctness judge failed: {e}")

        # 4. Completeness Judge (10 points)
        try:
            completeness_judge = mlflow.genai.make_judge(
                name="completeness",
                instructions="""Evaluate response completeness.

User Query: {{ inputs }}
AI Response: {{ outputs }}

Does the response provide:
- All requested information?
- Sufficient detail and context?
- Complete data (not truncated)?

Score from 0-10:
- 10 = Complete, comprehensive response
- 7 = Mostly complete, minor gaps
- 5 = Partially complete
- 2 = Incomplete, major gaps
- 0 = Very incomplete or missing data

Provide your score (0-10) and rationale.""",
                model="openai:/gpt-4o-mini"
            )
            judges.append(completeness_judge)
            print("  ✅ Completeness judge")
        except Exception as e:
            print(f"  ⚠️  Completeness judge failed: {e}")

        # 5. Natural Language Quality Judge (10 points)
        try:
            nl_judge = mlflow.genai.make_judge(
                name="natural_language",
                instructions="""Evaluate natural language quality.

Response: {{ outputs }}

Check:
- Is it conversational and engaging?
- Clear and professional?
- Good readability and flow?
- Appropriate tone?

Score from 0-10:
- 10 = Excellent natural language, very engaging
- 7 = Good quality, professional
- 5 = Acceptable but robotic
- 2 = Poor quality, hard to read
- 0 = Very poor language quality

Provide your score (0-10) and rationale.""",
                model="openai:/gpt-4o-mini"
            )
            judges.append(nl_judge)
            print("  ✅ Natural Language judge")
        except Exception as e:
            print(f"  ⚠️  Natural language judge failed: {e}")

        # 6. Relevance Judge (5 points)
        try:
            relevance_judge = mlflow.genai.make_judge(
                name="relevance",
                instructions="""Evaluate response relevance to the query.

User Query: {{ inputs }}
AI Response: {{ outputs }}

Does the response directly address the query without unnecessary information?

Score from 0-5:
- 5 = Perfectly relevant, focused response
- 3 = Mostly relevant, some extra info
- 1 = Partially relevant
- 0 = Not relevant

Provide your score (0-5) and rationale.""",
                model="openai:/gpt-4o-mini"
            )
            judges.append(relevance_judge)
            print("  ✅ Relevance judge")
        except Exception as e:
            print(f"  ⚠️  Relevance judge failed: {e}")

        # 7. Formatting Judge (5 points)
        try:
            formatting_judge = mlflow.genai.make_judge(
                name="formatting",
                instructions="""Evaluate response formatting.

Response: {{ outputs }}

Check:
- Is it well-structured?
- Easy to scan and read?
- Good use of spacing and organization?
- Professional presentation?

Score from 0-5:
- 5 = Excellent formatting, very readable
- 3 = Good formatting
- 1 = Poor formatting
- 0 = Very poor formatting

Provide your score (0-5) and rationale.""",
                model="openai:/gpt-4o-mini"
            )
            judges.append(formatting_judge)
            print("  ✅ Formatting judge")
        except Exception as e:
            print(f"  ⚠️  Formatting judge failed: {e}")

        print(f"\n✅ Created {len(judges)} evaluation judges\n")
        return judges

    def _register_prompts(self):
        """Register system prompts to MLflow Prompt Registry"""
        try:
            mlflow.genai.register_prompt(
                name="mongodb_query_agent_unified",
                template=self.system_prompts["mongodb_query_agent"],
                commit_message="Unified evaluation - MongoDB query generation prompt with schema",
                tags={
                    "agent": "data_agent",
                    "version": "v2.0",
                    "evaluation": "unified",
                    "has_schema": "true"
                }
            )
            print("✅ Registered MongoDB prompt to registry")
        except Exception as e:
            print(f"⚠️  Prompt registration skipped (may already exist): {e}")

    def predict_fn(self, inputs: str) -> str:
        """
        Prediction function for mlflow.genai.evaluate()

        Args:
            inputs: Query text string (passed as "inputs" parameter)

        Returns:
            AI response string
        """
        # inputs is the query text directly
        query = inputs

        print(f"\n🔄 Processing: {query[:70]}...")

        start_time = time.time()

        # Run workflow
        result = asyncio.run(self.workflow.process(
            user_message=query,
            session_id=f"eval_{int(time.time())}",
            user_id="evaluator"
        ))

        execution_time = time.time() - start_time
        print(f"  ✅ Completed in {execution_time:.2f}s")

        return result['response']

    def load_queries(self, file_path: str) -> pd.DataFrame:
        """Load evaluation queries from file

        Returns DataFrame with 'inputs' column containing a dict where keys
        match the predict_fn parameter names (in this case "inputs")
        """
        queries = []

        with open(file_path, 'r') as f:
            content = f.read()

        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('###'):
                continue

            if line and line[0].isdigit() and '. ' in line:
                query_text = line.split('. ', 1)[1] if '. ' in line else line
                query_number = int(line.split('.')[0])

                # The 'inputs' dict keys must match predict_fn parameter names
                # Since predict_fn has parameter "inputs", the dict key is also "inputs"
                queries.append({
                    "id": query_number,
                    "query": query_text,
                    "inputs": {"inputs": query_text}  # Key "inputs" matches param name
                })

        return pd.DataFrame(queries)

    def run_evaluation(
        self,
        queries_file: str = "evaluate.txt",
        sample_size: Optional[int] = None
    ):
        """
        Run unified evaluation using MLflow GenAI pipeline with detailed judges

        Args:
            queries_file: Path to queries file
            sample_size: Optional limit on number of queries to evaluate
        """
        print("=" * 70)
        print("🚀 UNIFIED PROCUREMENT ASSISTANT EVALUATION")
        print("=" * 70)
        print(f"📊 MLflow Experiment: procurement-assistant-evaluation")
        print(f"🏷️  Run Name: {self.run_name}\n")

        # Load queries
        queries_df = self.load_queries(queries_file)
        if sample_size:
            queries_df = queries_df.head(sample_size)

        print(f"📝 Loaded {len(queries_df)} evaluation queries\n")

        # Register prompts
        self._register_prompts()

        # Start MLflow run
        with mlflow.start_run(run_name=self.run_name) as run:
            print(f"🆔 MLflow Run ID: {run.info.run_id}\n")

            # Log parameters
            mlflow.log_param("total_queries", len(queries_df))
            mlflow.log_param("evaluation_date", datetime.now().isoformat())
            mlflow.log_param("model", "gpt-4o-mini")
            mlflow.log_param("evaluation_type", "unified")
            mlflow.log_param("criteria_count", 8)

            # Log schema
            if self.schema:
                mlflow.log_dict(self.schema, "mongodb_schema.json")
                mlflow.log_param("schema_fields", len(self.schema))
                print(f"📊 Logged schema with {len(self.schema)} fields")

            # Log system prompts as artifacts
            self._log_system_prompts()

            # Log evaluation criteria as artifact
            self._log_evaluation_criteria()

            # Run MLflow GenAI evaluation
            print("\n" + "=" * 70)
            print("🎯 RUNNING EVALUATION")
            print("=" * 70 + "\n")

            results = mlflow.genai.evaluate(
                data=queries_df,
                predict_fn=self.predict_fn,
                scorers=self.judges if self.judges else []
            )

            print("\n" + "=" * 70)
            print("✅ EVALUATION COMPLETE")
            print("=" * 70)

            # Log evaluation results table
            self._log_evaluation_results(results, queries_df)

            # Log aggregated metrics to MLflow UI
            self._log_aggregated_metrics(results)

            # Print summary
            self._print_summary(results)

            print(f"\n🌐 View results: http://localhost:5000")
            print(f"📂 Run ID: {run.info.run_id}")
            print(f"\n💡 To see detailed sample-wise scores:")
            print(f"   METHOD 1 - Traces Tab (Interactive):")
            print(f"     1. Click 'Traces' tab in your run")
            print(f"     2. Click on any trace to expand it")
            print(f"     3. Scroll down to see 'Assessments' section")
            print(f"     4. View all 8 criterion scores with rationales")
            print(f"")
            print(f"   METHOD 2 - Artifacts Tab (Reference):")
            print(f"     1. Click 'Artifacts' tab")
            print(f"     2. Open 'evaluation_criteria.json' - scoring system")
            print(f"     3. Open 'evaluation_results_summary.json' - queries list\n")

        return results

    def _log_system_prompts(self):
        """Log system prompts as artifacts"""
        if not self.system_prompts:
            return

        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        prompts_dir = Path(temp_dir) / "system_prompts"
        prompts_dir.mkdir(exist_ok=True)

        for agent_name, prompt in self.system_prompts.items():
            prompt_file = prompts_dir / f"{agent_name}.txt"
            prompt_file.write_text(prompt)

        all_prompts_file = prompts_dir / "all_prompts.json"
        all_prompts_file.write_text(json.dumps(self.system_prompts, indent=2))

        mlflow.log_artifacts(str(prompts_dir), "system_prompts")
        shutil.rmtree(temp_dir)

        print(f"📝 Logged {len(self.system_prompts)} system prompts\n")

    def _log_evaluation_criteria(self):
        """Log evaluation criteria and scoring system as artifact"""
        criteria = {
            "evaluation_framework": {
                "name": "Unified Procurement Assistant Evaluation",
                "version": "2.0",
                "total_points": 100,
                "description": "Comprehensive evaluation across 8 criteria covering query generation, result accuracy, and response quality"
            },
            "categories": [
                {
                    "name": "Query Generation Quality",
                    "weight": "50%",
                    "total_points": 50,
                    "criteria": [
                        {
                            "name": "Syntax Correctness",
                            "points": 15,
                            "description": "MongoDB query syntax validity and execution success"
                        },
                        {
                            "name": "Semantic Correctness",
                            "points": 20,
                            "description": "Query matches user intent with correct fields and operations"
                        },
                        {
                            "name": "Query Efficiency",
                            "points": 15,
                            "description": "Optimal filter placement, appropriate limits, index-friendly operations"
                        }
                    ]
                },
                {
                    "name": "Result Accuracy",
                    "weight": "30%",
                    "total_points": 30,
                    "criteria": [
                        {
                            "name": "Data Correctness",
                            "points": 20,
                            "description": "Accurate results with reasonable numbers and data-driven responses"
                        },
                        {
                            "name": "Completeness",
                            "points": 10,
                            "description": "All requested data returned without unexpected truncation"
                        }
                    ]
                },
                {
                    "name": "Response Quality",
                    "weight": "20%",
                    "total_points": 20,
                    "criteria": [
                        {
                            "name": "Natural Language",
                            "points": 10,
                            "description": "Conversational quality, readability, and professional tone"
                        },
                        {
                            "name": "Relevance",
                            "points": 5,
                            "description": "Response directly addresses query without unnecessary information"
                        },
                        {
                            "name": "Formatting",
                            "points": 5,
                            "description": "Well-structured, easy to scan, professional presentation"
                        }
                    ]
                }
            ],
            "scoring_scale": {
                "excellent": {"range": "90-100", "description": "Outstanding performance across all criteria"},
                "good": {"range": "75-89", "description": "Strong performance with minor improvements needed"},
                "acceptable": {"range": "60-74", "description": "Adequate performance with noticeable gaps"},
                "needs_improvement": {"range": "40-59", "description": "Significant improvements required"},
                "poor": {"range": "0-39", "description": "Major issues requiring immediate attention"}
            },
            "judges": [
                {
                    "name": "syntax_correctness",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-4o-mini",
                    "max_points": 15
                },
                {
                    "name": "semantic_correctness",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-4o-mini",
                    "max_points": 20
                },
                {
                    "name": "query_efficiency",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-4o-mini",
                    "max_points": 15
                },
                {
                    "name": "data_correctness",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-4o-mini",
                    "max_points": 20
                },
                {
                    "name": "completeness",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-4o-mini",
                    "max_points": 10
                },
                {
                    "name": "natural_language",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-4o-mini",
                    "max_points": 10
                },
                {
                    "name": "relevance",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-4o-mini",
                    "max_points": 5
                },
                {
                    "name": "formatting",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-4o-mini",
                    "max_points": 5
                }
            ],
            "metadata": {
                "framework": "MLflow GenAI",
                "pipeline": "mlflow.genai.evaluate()",
                "evaluation_type": "unified",
                "date_created": datetime.now().isoformat()
            }
        }

        # Log as JSON artifact
        mlflow.log_dict(criteria, "evaluation_criteria.json")
        print("📋 Logged evaluation criteria and scoring system\n")

    def _log_evaluation_results(self, results, queries_df):
        """Log evaluation results summary with query information"""
        try:
            # Create summary table with queries and scoring breakdown
            results_summary = {
                "evaluation_summary": {
                    "total_queries": len(queries_df),
                    "evaluation_date": datetime.now().isoformat(),
                    "run_name": self.run_name
                },
                "scoring_system": {
                    "syntax_correctness": {"max_points": 15, "category": "Query Generation"},
                    "semantic_correctness": {"max_points": 20, "category": "Query Generation"},
                    "query_efficiency": {"max_points": 15, "category": "Query Generation"},
                    "data_correctness": {"max_points": 20, "category": "Result Accuracy"},
                    "completeness": {"max_points": 10, "category": "Result Accuracy"},
                    "natural_language": {"max_points": 10, "category": "Response Quality"},
                    "relevance": {"max_points": 5, "category": "Response Quality"},
                    "formatting": {"max_points": 5, "category": "Response Quality"}
                },
                "queries_evaluated": []
            }

            # Add each query
            for idx, row in queries_df.iterrows():
                query_info = {
                    "query_id": idx + 1,
                    "query_text": row['query'],
                    "note": "Individual scores available in MLflow Traces tab - expand each trace to see detailed scores per criterion"
                }
                results_summary["queries_evaluated"].append(query_info)

            # Log as JSON
            mlflow.log_dict(results_summary, "evaluation_results_summary.json")
            print(f"📊 Logged evaluation results summary with {len(queries_df)} queries\n")

        except Exception as e:
            print(f"⚠️  Could not log evaluation results: {e}\n")

    def _log_aggregated_metrics(self, results):
        """
        Extract and log aggregated metrics from evaluation results to MLflow UI
        This makes overall scores visible in the Metrics tab
        """
        print("\n📊 Logging aggregated metrics to MLflow UI...")

        try:
            # Try to get scores from result_df (DataFrame with evaluation results)
            if hasattr(results, 'result_df') and results.result_df is not None and not results.result_df.empty:
                print(f"  📊 Found result_df with {len(results.result_df)} rows")

                # Define criteria with max scores (Total: 100 points, scaled up from 85)
                # Note: MLflow GenAI stores scores in columns named "/value" not "/score"
                criteria_max_scores = {
                    "semantic_correctness": 25,
                    "query_efficiency": 20,
                    "data_correctness": 25,
                    "completeness": 10,
                    "natural_language": 10,
                    "relevance": 5,
                    "formatting": 5
                }

                metrics_logged = []
                total_score = 0
                criteria_count = 0

                # Calculate average for each criterion from the DataFrame
                for criterion_name, max_score in criteria_max_scores.items():
                    value_col = f"{criterion_name}/value"
                    if value_col in results.result_df.columns:
                        # Get non-null scores and convert to numeric
                        scores = pd.to_numeric(results.result_df[value_col], errors='coerce').dropna()

                        if len(scores) > 0:
                            avg_score = scores.mean()

                            # Log the average score
                            mlflow.log_metric(f"{criterion_name}/score", avg_score)

                            # Calculate and log percentage
                            percentage = (avg_score / max_score * 100) if max_score > 0 else 0
                            mlflow.log_metric(f"{criterion_name}/percentage", percentage)

                            metrics_logged.append(f"{criterion_name}: {avg_score:.2f}/{max_score} ({percentage:.1f}%)")
                            total_score += avg_score
                            criteria_count += 1

                # Log overall metrics
                if criteria_count > 0:
                    mlflow.log_metric("overall_score", total_score)
                    overall_percentage = (total_score / 100.0) * 100
                    mlflow.log_metric("overall_percentage", overall_percentage)

                    # Calculate and log category totals
                    query_gen = 0
                    result_acc = 0
                    response_qual = 0

                    for criterion_name in criteria_max_scores.keys():
                        value_col = f"{criterion_name}/value"
                        if value_col in results.result_df.columns:
                            avg = pd.to_numeric(results.result_df[value_col], errors='coerce').dropna().mean()
                            if criterion_name in ["semantic_correctness", "query_efficiency"]:
                                query_gen += avg
                            elif criterion_name in ["data_correctness", "completeness"]:
                                result_acc += avg
                            elif criterion_name in ["natural_language", "relevance", "formatting"]:
                                response_qual += avg

                    mlflow.log_metric("query_generation_quality", query_gen)
                    mlflow.log_metric("result_accuracy", result_acc)
                    mlflow.log_metric("response_quality", response_qual)

                    metrics_logged.append(f"overall_score: {total_score:.2f}/100 ({overall_percentage:.1f}%)")

                    print(f"  ✅ Logged {len(metrics_logged)} aggregated metrics to Metrics tab")
                    for metric in metrics_logged[:4]:
                        print(f"     - {metric}")
                    if len(metrics_logged) > 4:
                        print(f"     - ... and {len(metrics_logged) - 4} more")
                else:
                    print("  ⚠️  No criterion scores found in result_df")
            else:
                print("  ⚠️  result_df is empty or not available")
                print("     Scores are available in the Traces tab -> Assessments section")

        except Exception as e:
            import traceback
            print(f"  ⚠️  Could not extract aggregated metrics: {e}")
            print(f"     Error details: {traceback.format_exc()}")
            print(f"     Scores are still available in the Traces tab -> Assessments section")

    def _print_summary(self, results):
        """Print evaluation summary"""
        print("\n📊 EVALUATION SUMMARY")
        print("=" * 70)

        # MLflow GenAI evaluate() returns results object with tables
        # Metrics are aggregated in the MLflow UI, not directly accessible here
        print("\n✅ Evaluation complete! Results logged to MLflow.")
        print("\nTo view detailed scores:")
        print("  1. Open MLflow UI: http://localhost:5000")
        print("  2. Go to the 'Traces' tab in your run")
        print("  3. View individual scores for each criterion")
        print("  4. Check the 'Metrics' tab for aggregated scores")

        # Print what we know
        print("\n📋 Judges Executed:")
        print("  ✅ Syntax Correctness (0-15 points)")
        print("  ✅ Semantic Correctness (0-20 points)")
        print("  ✅ Query Efficiency (0-15 points)")
        print("  ✅ Data Correctness (0-20 points)")
        print("  ✅ Completeness (0-10 points)")
        print("  ✅ Natural Language (0-10 points)")
        print("  ✅ Relevance (0-5 points)")
        print("  ✅ Formatting (0-5 points)")

        print("\n💡 Total Possible: 100 points")

        print("\n" + "=" * 70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Unified Procurement Assistant Evaluation Framework"
    )
    parser.add_argument(
        "--queries",
        type=str,
        default="evaluate.txt",
        help="Path to queries file (default: evaluate.txt)"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Evaluate only first N queries"
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Custom MLflow run name"
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default="procurement-assistant-evaluation",
        help="MLflow experiment name"
    )

    args = parser.parse_args()

    # Create framework
    framework = UnifiedEvaluationFramework(
        experiment_name=args.experiment,
        run_name=args.run_name
    )

    # Run evaluation
    framework.run_evaluation(
        queries_file=args.queries,
        sample_size=args.sample
    )


if __name__ == "__main__":
    main()
