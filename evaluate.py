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

        print("Unified Evaluation Framework initialized")
        print(f"Experiment: {experiment_name}")
        print(f"Run Name: {self.run_name}\n")

    def _get_schema(self) -> Dict:
        """Get MongoDB collection schema"""
        try:
            from procurement_agent.mongodb_query import MongoDBQueryAgent
            agent = MongoDBQueryAgent(
                mongo_uri=Config.MONGO_URI,
                db_name=Config.MONGO_DB,
                collection_name=Config.MONGO_COLLECTION
            )
            schema = agent._get_collection_schema()
            print(f"Loaded schema with {len(schema)} fields")
            return schema
        except Exception as e:
            print(f"Warning: Schema loading failed: {e}")
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
        self.judge_prompts = {}  # Store prompts for logging

        print("Creating evaluation judges...")

        # Get schema for syntax validation
        schema_str = json.dumps(self.schema, indent=2) if self.schema else "[Schema not available]"

        # 1. Syntax Correctness Judge (15 points)
        try:
            syntax_instructions = f"""Evaluate MongoDB query syntax correctness.

User Question: {{{{ inputs }}}}
AI Output: {{{{ outputs }}}}

The output contains "MONGODB_QUERY:" followed by the actual MongoDB query JSON.
Evaluate if the MONGODB QUERY has valid syntax and structure.

Available Collection Schema:
{schema_str}

Check:
- Is it valid MongoDB query syntax?
- Are all operators used correctly ($match, $group, $sum, $gte, etc.)?
- Are field names valid according to the schema?
- Is the structure well-formed (proper nesting, brackets, etc.)?
- Would this query execute without syntax errors?

Score from 0-15:
- 15 = Perfect syntax: valid, well-formed, correct field names, will execute
- 11 = Mostly correct: minor syntax issues but likely works
- 7 = Some syntax problems: may have execution issues
- 3 = Major syntax errors: likely won't execute
- 0 = Invalid syntax: completely broken

Provide your score (0-15) and rationale."""

            syntax_judge = mlflow.genai.make_judge(
                name="syntax_correctness",
                instructions=syntax_instructions,
                model="openai:/gpt-4o-mini"
            )
            judges.append(syntax_judge)
            self.judge_prompts["syntax_correctness"] = syntax_instructions
        except Exception as e:
            print(f"  Warning: Syntax judge failed: {e}")

        # 2. Semantic Correctness Judge (20 points)
        try:
            semantic_instructions = """Evaluate if the MongoDB query semantically matches the user's intent.

User Question: {{ inputs }}
AI Output: {{ outputs }}

The output contains "MONGODB_QUERY:" followed by the actual MongoDB query JSON.
Evaluate if the MONGODB QUERY correctly addresses what the user asked.

Check:
- Are the correct fields being queried?
- Are the filters appropriate for the question?
- Are the operations ($match, $group, $sum, etc.) correct?
- Does the query structure match the user's intent?

Score from 0-20:
- 20 = Perfect match: query will answer exactly what was asked
- 15 = Mostly correct: minor semantic issues or field choices
- 10 = Partially correct: some misunderstanding of intent
- 5 = Mostly wrong: major semantic issues, wrong fields/operations
- 0 = Completely wrong: doesn't address the question at all

Provide your score (0-20) and rationale."""

            semantic_judge = mlflow.genai.make_judge(
                name="semantic_correctness",
                instructions=semantic_instructions,
                model="openai:/gpt-4o-mini"
            )
            judges.append(semantic_judge)
            self.judge_prompts["semantic_correctness"] = semantic_instructions
        except Exception as e:
            print(f"  Warning: Semantic judge failed: {e}")

        # 3. Query Efficiency Judge (15 points)
        try:
            efficiency_instructions = """Evaluate MongoDB query efficiency.

User Query: {{ inputs }}
AI Output: {{ outputs }}

The output contains "MONGODB_QUERY:" followed by the actual MongoDB query JSON.
Evaluate the MONGODB QUERY (not the response text) for efficiency.

Consider:
- Are $match filters applied early in the pipeline?
- Is there appropriate use of $limit?
- Are indexes likely being used (simple filters on key fields)?
- Is the query unnecessarily complex?
- For aggregations: is the pipeline well-structured?

Score from 0-15:
- 15 = Highly efficient: early filters, appropriate limits, index-friendly
- 11 = Reasonably efficient: good structure, minor optimization opportunities
- 7 = Moderately efficient: works but could be optimized
- 3 = Inefficient but functional: performance issues likely
- 0 = Very inefficient: major performance problems

Provide your score (0-15) and rationale."""

            efficiency_judge = mlflow.genai.make_judge(
                name="query_efficiency",
                instructions=efficiency_instructions,
                model="openai:/gpt-4o-mini"
            )
            judges.append(efficiency_judge)
            self.judge_prompts["query_efficiency"] = efficiency_instructions
        except Exception as e:
            print(f"  Warning: Efficiency judge failed: {e}")

        # 3. Data Correctness Judge (25 points)
        try:
            data_correctness_instructions = """Evaluate if the data in the response appears correct.

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

Provide your score (0-25) and rationale."""

            data_judge = mlflow.genai.make_judge(
                name="data_correctness",
                instructions=data_correctness_instructions,
                model="openai:/gpt-4o-mini"
            )
            judges.append(data_judge)
            self.judge_prompts["data_correctness"] = data_correctness_instructions
            print("  [OK] Data Correctness judge")
        except Exception as e:
            print(f"  [WARNING] Data correctness judge failed: {e}")

        # 4. Completeness Judge (10 points)
        try:
            completeness_instructions = """Evaluate response completeness.

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

Provide your score (0-10) and rationale."""

            completeness_judge = mlflow.genai.make_judge(
                name="completeness",
                instructions=completeness_instructions,
                model="openai:/gpt-4o-mini"
            )
            judges.append(completeness_judge)
            self.judge_prompts["completeness"] = completeness_instructions
            print("  [OK] Completeness judge")
        except Exception as e:
            print(f"  [WARNING] Completeness judge failed: {e}")

        # 5. Natural Language Quality Judge (10 points)
        try:
            natural_language_instructions = """Evaluate natural language quality.

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

Provide your score (0-10) and rationale."""

            nl_judge = mlflow.genai.make_judge(
                name="natural_language",
                instructions=natural_language_instructions,
                model="openai:/gpt-4o-mini"
            )
            judges.append(nl_judge)
            self.judge_prompts["natural_language"] = natural_language_instructions
            print("  [OK] Natural Language judge")
        except Exception as e:
            print(f"  [WARNING] Natural language judge failed: {e}")

        # 6. Relevance Judge (5 points)
        try:
            relevance_instructions = """Evaluate response relevance to the query.

User Query: {{ inputs }}
AI Response: {{ outputs }}

Does the response directly address the query without unnecessary information?

Score from 0-5:
- 5 = Perfectly relevant, focused response
- 3 = Mostly relevant, some extra info
- 1 = Partially relevant
- 0 = Not relevant

Provide your score (0-5) and rationale."""

            relevance_judge = mlflow.genai.make_judge(
                name="relevance",
                instructions=relevance_instructions,
                model="openai:/gpt-4o-mini"
            )
            judges.append(relevance_judge)
            self.judge_prompts["relevance"] = relevance_instructions
            print("  [OK] Relevance judge")
        except Exception as e:
            print(f"  [WARNING] Relevance judge failed: {e}")

        # 7. Formatting Judge (5 points)
        try:
            formatting_instructions = """Evaluate response formatting.

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

Provide your score (0-5) and rationale."""

            formatting_judge = mlflow.genai.make_judge(
                name="formatting",
                instructions=formatting_instructions,
                model="openai:/gpt-4o-mini"
            )
            judges.append(formatting_judge)
            self.judge_prompts["formatting"] = formatting_instructions
            print("  [OK] Formatting judge")
        except Exception as e:
            print(f"  [WARNING] Formatting judge failed: {e}")

        print(f"\n[OK] Created {len(judges)} evaluation judges\n")
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
            print("[OK] Registered MongoDB prompt to registry")
        except Exception as e:
            print(f"[WARNING] Prompt registration skipped (may already exist): {e}")

    def predict_fn(self, inputs: str) -> str:
        """
        Prediction function for mlflow.genai.evaluate()

        Args:
            inputs: Query text string (passed as "inputs" parameter)

        Returns:
            AI response string with MongoDB query context embedded
        """
        # inputs is the query text directly
        query = inputs

        print(f"\nProcessing: {query[:70]}...")

        start_time = time.time()

        # Run workflow
        result = asyncio.run(self.workflow.process(
            user_message=query,
            session_id=f"eval_{int(time.time())}",
            user_id="evaluator"
        ))

        execution_time = time.time() - start_time
        print(f"  Completed in {execution_time:.2f}s")

        # Extract MongoDB query from metadata for judges to evaluate
        mongodb_query = result.get('metadata', {}).get('query', {})
        response_text = result['response']

        # Return structured response that includes both the query and response
        # This allows judges to evaluate the MongoDB query directly
        if mongodb_query:
            return f"""MONGODB_QUERY: {json.dumps(mongodb_query, indent=2)}

RESPONSE: {response_text}"""
        else:
            # For non-data queries (chat agent), just return response
            return response_text

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
        print("UNIFIED PROCUREMENT ASSISTANT EVALUATION")
        print("=" * 70)
        print(f"MLflow Experiment: procurement-assistant-evaluation")
        print(f"Run Name: {self.run_name}\n")

        # Load queries
        queries_df = self.load_queries(queries_file)
        if sample_size:
            queries_df = queries_df.head(sample_size)

        print(f"Loaded {len(queries_df)} evaluation queries\n")

        # Register prompts
        self._register_prompts()

        # Start MLflow run
        with mlflow.start_run(run_name=self.run_name) as run:
            print(f"MLflow Run ID: {run.info.run_id}\n")

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
                print(f"Logged schema with {len(self.schema)} fields")

            # Log system prompts as artifacts
            self._log_system_prompts()

            # Log judge prompts as artifacts
            self._log_judge_prompts()

            # Log evaluation criteria as artifact
            self._log_evaluation_criteria()

            # Run MLflow GenAI evaluation
            print("\n" + "=" * 70)
            print("RUNNING EVALUATION")
            print("=" * 70 + "\n")

            results = mlflow.genai.evaluate(
                data=queries_df,
                predict_fn=self.predict_fn,
                scorers=self.judges if self.judges else []
            )

            print("\n" + "=" * 70)
            print("EVALUATION COMPLETE")
            print("=" * 70)

            # Log evaluation results table
            self._log_evaluation_results(results, queries_df)

            # Log aggregated metrics to MLflow UI
            self._log_aggregated_metrics(results)

            # Print summary
            self._print_summary(results)

            print(f"\nView results: http://localhost:5000")
            print(f"Run ID: {run.info.run_id}")
            print(f"\nTo see detailed sample-wise scores:")
            print(f"   METHOD 1 - Traces Tab (Interactive):")
            print(f"     1. Click 'Traces' tab in your run")
            print(f"     2. Click on any trace to expand it")
            print(f"     3. Scroll down to see 'Assessments' section")
            print(f"     4. View all 8 criterion scores with rationales")
            print(f"")
            print(f"   METHOD 2 - Artifacts Tab (Reference):")
            print(f"     1. Click 'Artifacts' tab")
            print(f"     2. Open 'evaluation_criteria.json' - full scoring system and criteria\n")

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

        print(f"Logged {len(self.system_prompts)} system prompts\n")

    def _log_judge_prompts(self):
        """Log judge prompts as artifacts"""
        if not hasattr(self, 'judge_prompts') or not self.judge_prompts:
            return

        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        judge_prompts_dir = Path(temp_dir) / "judge_prompts"
        judge_prompts_dir.mkdir(exist_ok=True)

        # Log individual judge prompts as txt files
        for judge_name, prompt in self.judge_prompts.items():
            prompt_file = judge_prompts_dir / f"{judge_name}.txt"
            prompt_file.write_text(prompt)

        # Log combined JSON file
        all_judges_file = judge_prompts_dir / "all_judges.json"
        all_judges_file.write_text(json.dumps(self.judge_prompts, indent=2))

        mlflow.log_artifacts(str(judge_prompts_dir), "judge_prompts")
        shutil.rmtree(temp_dir)

        print(f"Logged {len(self.judge_prompts)} judge prompts\n")

    def _log_evaluation_criteria(self):
        """Log evaluation criteria and scoring system as artifact"""
        criteria = {
            "evaluation_framework": {
                "name": "Unified Procurement Assistant Evaluation",
                "version": "2.1",
                "total_points": 100,
                "description": "Comprehensive evaluation across 8 criteria covering query generation, result accuracy, and response quality. Judges evaluate the actual MongoDB query (not just the response) for query-related criteria."
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
                            "description": "MongoDB query syntax validity and execution success",
                            "evaluation_target": "MongoDB query JSON from workflow metadata"
                        },
                        {
                            "name": "Semantic Correctness",
                            "points": 20,
                            "description": "Query matches user intent with correct fields and operations",
                            "evaluation_target": "MongoDB query JSON - checks if correct fields, filters, and operations are used"
                        },
                        {
                            "name": "Query Efficiency",
                            "points": 15,
                            "description": "Optimal filter placement, appropriate limits, index-friendly operations",
                            "evaluation_target": "MongoDB query JSON - evaluates pipeline structure and optimization"
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
                "date_created": datetime.now().isoformat(),
                "evaluation_approach": {
                    "description": "Judges receive both MongoDB query and final response for comprehensive evaluation",
                    "output_format": "MONGODB_QUERY: {json}\\n\\nRESPONSE: {text}",
                    "query_judges": ["syntax_correctness", "semantic_correctness", "query_efficiency"],
                    "response_judges": ["data_correctness", "completeness", "natural_language", "relevance", "formatting"]
                }
            }
        }

        # Log as JSON artifact
        mlflow.log_dict(criteria, "evaluation_criteria.json")
        print("Logged evaluation criteria and scoring system\n")

    def _log_evaluation_results(self, results, queries_df):
        """Log evaluation results summary with query information"""
        # Removed: evaluation_results_summary.json is redundant
        # All information is available in:
        # - Traces tab: Individual query scores with rationales
        # - Metrics tab: Aggregated scores
        # - evaluation_criteria.json: Scoring system documentation
        pass

    def _log_aggregated_metrics(self, results):
        """
        Extract and log aggregated metrics from evaluation results to MLflow UI
        This makes overall scores visible in the Metrics tab
        """
        print("\nLogging aggregated metrics to MLflow UI...")

        try:
            # Try to get scores from result_df (DataFrame with evaluation results)
            if hasattr(results, 'result_df') and results.result_df is not None and not results.result_df.empty:
                print(f"  Found result_df with {len(results.result_df)} rows")

                # Define criteria with max scores (Total: 100 points)
                # Note: MLflow GenAI stores scores in columns named "/value" not "/score"
                criteria_max_scores = {
                    "syntax_correctness": 15,
                    "semantic_correctness": 20,
                    "query_efficiency": 15,
                    "data_correctness": 20,
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

                            # Log the average score with max in metric name for clarity
                            mlflow.log_metric(f"{criterion_name}_out_of_{max_score}", avg_score)

                            percentage = (avg_score / max_score * 100) if max_score > 0 else 0
                            metrics_logged.append(f"{criterion_name}: {avg_score:.2f}/{max_score} ({percentage:.1f}%)")
                            total_score += avg_score
                            criteria_count += 1

                # Log overall metrics
                if criteria_count > 0:
                    mlflow.log_metric("overall_score_out_of_100", total_score)

                    # Calculate and log category totals
                    query_gen = 0
                    result_acc = 0
                    response_qual = 0

                    for criterion_name in criteria_max_scores.keys():
                        value_col = f"{criterion_name}/value"
                        if value_col in results.result_df.columns:
                            avg = pd.to_numeric(results.result_df[value_col], errors='coerce').dropna().mean()
                            if criterion_name in ["syntax_correctness", "semantic_correctness", "query_efficiency"]:
                                query_gen += avg
                            elif criterion_name in ["data_correctness", "completeness"]:
                                result_acc += avg
                            elif criterion_name in ["natural_language", "relevance", "formatting"]:
                                response_qual += avg

                    mlflow.log_metric("query_generation_out_of_50", query_gen)
                    mlflow.log_metric("result_accuracy_out_of_30", result_acc)
                    mlflow.log_metric("response_quality_out_of_20", response_qual)

                    metrics_logged.append(f"overall_score: {total_score:.2f}/100")

                    print(f"  Logged {len(metrics_logged)} aggregated metrics to Metrics tab")
                    for metric in metrics_logged[:4]:
                        print(f"     - {metric}")
                    if len(metrics_logged) > 4:
                        print(f"     - ... and {len(metrics_logged) - 4} more")
                else:
                    print("  [WARNING] No criterion scores found in result_df")
            else:
                print("  [WARNING] result_df is empty or not available")
                print("     Scores are available in the Traces tab -> Assessments section")

        except Exception as e:
            import traceback
            print(f"  [WARNING] Could not extract aggregated metrics: {e}")
            print(f"     Error details: {traceback.format_exc()}")
            print(f"     Scores are still available in the Traces tab -> Assessments section")

    def _print_summary(self, results):
        """Print evaluation summary"""
        print("\nEVALUATION SUMMARY")
        print("=" * 70)

        # MLflow GenAI evaluate() returns results object with tables
        # Metrics are aggregated in the MLflow UI, not directly accessible here
        print("\nEvaluation complete! Results logged to MLflow.")
        print("\nTo view detailed scores:")
        print("  1. Open MLflow UI: http://localhost:5000")
        print("  2. Go to the 'Traces' tab in your run")
        print("  3. View individual scores for each criterion")
        print("  4. Check the 'Metrics' tab for aggregated scores")

        # Print what we know
        print("\nJudges Executed:")
        print("  - Syntax Correctness (0-15 points)")
        print("  - Semantic Correctness (0-20 points)")
        print("  - Query Efficiency (0-15 points)")
        print("  - Data Correctness (0-20 points)")
        print("  - Completeness (0-10 points)")
        print("  - Natural Language (0-10 points)")
        print("  - Relevance (0-5 points)")
        print("  - Formatting (0-5 points)")

        print("\nTotal Possible: 100 points")

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
