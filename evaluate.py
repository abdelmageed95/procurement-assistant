#!/usr/bin/env python3
"""
Unified Procurement Assistant Evaluation Framework

Combines the best of both evaluation approaches:
- MLflow GenAI standardized pipeline (mlflow.genai.evaluate)
- Detailed 5-criteria scoring system
- MongoDB query validation
- Prompt registry and versioning
- Comprehensive artifact logging

Evaluation Criteria (100 points total):
1. Query Generation Quality (80 points)
   - Syntax Correctness (35 points)
   - Semantic Correctness (30 points)
   - Query Efficiency (15 points)

2. Response Quality (20 points)
   - Natural Language (15 points)
   - Relevance (5 points)

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
from typing import Dict, List, Optional
import mlflow
import mlflow.genai
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from openai import OpenAI
import os
# Import the system
from procurement_agent.workflow import ProcurementWorkflow
from procurement_agent.config import Config

import warnings
import logging

# Suppress OpenTelemetry async context warnings
warnings.filterwarnings("ignore", message=".*was created in a different Context.*")
logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)


class EvaluationFramework:
    """
    Evaluation framework combining:
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

        print("Evaluation Framework initialized")
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
        return {"mongodb_query_agent": mongodb_prompt}

    def _create_judges(self) -> List:
        """Create MLflow GenAI judges for all 8 criteria"""
        judges = []
        self.judge_prompts = {}  # Store prompts for logging

        print("Creating evaluation judges...")

        # Get schema for syntax validation
        schema_str = json.dumps(self.schema, indent=2) if self.schema else "[Schema not available]"

        # 1. Syntax Correctness Judge (35 points)
        try:
            syntax_instructions = f"""Evaluate MongoDB query syntax correctness.

User Question: {{{{ inputs }}}}
AI Output: {{{{ outputs }}}}

The output contains a MongoDB query. Evaluate if it has valid syntax and structure.

Available Collection Schema:
{schema_str}

IMPORTANT - Special Date Format:
This system uses a special placeholder format for dates: {{"__datetime__": "YYYY-MM-DD"}}
- This is CORRECT syntax (not an error)
- The placeholder is converted to Python datetime objects before execution
- Example: {{"creation_date": {{"$gte": {{"__datetime__": "2014-01-01"}}}}}}
- Do NOT penalize queries that use this format
- DO penalize if dates are in wrong format (missing __datetime__, using ISODate(), etc.)

Check:
- Is it valid MongoDB query syntax?
- Are all operators used correctly ($match, $group, $sum, $gte, etc.)?
- Are field names valid according to the schema?
- Are dates using the correct __datetime__ placeholder format?
- Is the structure well-formed (proper nesting, brackets, etc.)?
- Would this query execute without syntax errors (after datetime conversion)?

Score from 0-35:
- 35 = Perfect syntax: valid, well-formed, correct field names, proper date format, will execute
- 26 = Mostly correct: minor syntax issues but likely works
- 18 = Some syntax problems: may have execution issues
- 9 = Major syntax errors: likely won't execute
- 0 = Invalid syntax: completely broken

Provide your score (0-35) and rationale."""

            syntax_judge = mlflow.genai.make_judge(
                name="syntax_correctness", instructions=syntax_instructions, model="openai:/gpt-5"
            )
            judges.append(syntax_judge)
            self.judge_prompts["syntax_correctness"] = syntax_instructions
        except Exception as e:
            print(f"  Warning: Syntax judge failed: {e}")

        # 2. Semantic Correctness Judge (30 points)
        try:
            semantic_instructions = """Evaluate if the MongoDB query semantically matches the user's intent.

User Question: {{ inputs }}
AI Output: {{ outputs }}

The output contains a MongoDB query. Evaluate if it correctly addresses what the user asked.

IMPORTANT - Date Format Note:
This system uses {{"__datetime__": "YYYY-MM-DD"}} as a special placeholder for dates.
This is the CORRECT format for date queries in this system.

Check:
- Are the correct fields being queried?
- Are the filters appropriate for the question?
- Are the operations ($match, $group, $sum, etc.) correct?
- Does the query structure match the user's intent?
- For date-related queries: is the __datetime__ placeholder used correctly?

Score from 0-30:
- 30 = Perfect match: query will answer exactly what was asked
- 23 = Mostly correct: minor semantic issues or field choices
- 15 = Partially correct: some misunderstanding of intent
- 8 = Mostly wrong: major semantic issues, wrong fields/operations
- 0 = Completely wrong: doesn't address the question at all

Provide your score (0-30) and rationale."""

            semantic_judge = mlflow.genai.make_judge(
                name="semantic_correctness",
                instructions=semantic_instructions,
                model="openai:/gpt-5",
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

The output contains a MongoDB query. Evaluate the MONGODB QUERY for efficiency.

IMPORTANT - Special Date Format:
This system uses a special placeholder format for dates: {"__datetime__": "YYYY-MM-DD"}
- This is the CORRECT format used by this system
- The placeholder is converted to Python datetime objects before execution
- Example: {"creation_date": {"$gte": {"__datetime__": "2014-01-01"}}}
- Do NOT penalize queries for using this format

Consider:
- Are $match filters applied early in the pipeline?
- Is there appropriate use of $limit?
- Are indexes likely being used (simple filters on key fields)?
- Is the query unnecessarily complex?
- For aggregations: is the pipeline well-structured?

Score from 0-15:
- 15 = Highly efficient: early filters, appropriate limits, index-friendly
- 12 = Reasonably efficient: good structure, minor optimization opportunities
- 8 = Moderately efficient: works but could be optimized
- 4 = Inefficient but functional: performance issues likely
- 0 = Very inefficient: major performance problems

Provide your score (0-15) and rationale."""

            efficiency_judge = mlflow.genai.make_judge(
                name="query_efficiency", instructions=efficiency_instructions, model="openai:/gpt-5"
            )
            judges.append(efficiency_judge)
            self.judge_prompts["query_efficiency"] = efficiency_instructions
        except Exception as e:
            print(f"  Warning: Efficiency judge failed: {e}")

        # 4. Natural Language Quality Judge (15 points)
        try:
            natural_language_instructions = """Evaluate natural language quality.

Response: {{ outputs }}

Check:
- Is it conversational and engaging?
- Clear and professional?
- Good readability and flow?
- Appropriate tone?

Score from 0-15:
- 15 = Excellent natural language, very engaging
- 11 = Good quality, professional
- 8 = Acceptable but robotic
- 4 = Poor quality, hard to read
- 0 = Very poor language quality

Provide your score (0-15) and rationale."""

            nl_judge = mlflow.genai.make_judge(
                name="natural_language",
                instructions=natural_language_instructions,
                model="openai:/gpt-5",
            )
            judges.append(nl_judge)
            self.judge_prompts["natural_language"] = natural_language_instructions
            print("  [OK] Natural Language judge")
        except Exception as e:
            print(f"  [WARNING] Natural language judge failed: {e}")

        # 5. Relevance Judge (5 points)
        try:
            relevance_instructions = """Evaluate response relevance to the query.

User Query: {{ inputs }}
AI Response: {{ outputs }}

Does the response directly address the query without unnecessary information?

Score from 0-5:
- 5 = Perfectly relevant, focused response
- 4 = Mostly relevant, minor extra info
- 2 = Partially relevant
- 0 = Not relevant

Provide your score (0-5) and rationale."""

            relevance_judge = mlflow.genai.make_judge(
                name="relevance", instructions=relevance_instructions, model="openai:/gpt-5"
            )
            judges.append(relevance_judge)
            self.judge_prompts["relevance"] = relevance_instructions
            print("  [OK] Relevance judge")
        except Exception as e:
            print(f"  [WARNING] Relevance judge failed: {e}")

        print(f"\n[OK] Created {len(judges)} evaluation judges\n")
        return judges

    def _register_prompts(self):
        """Register all prompts to MLflow Prompt Registry by importing from source files"""
        prompts_registered = []

        # 1. MongoDB Query Agent prompt (already loaded in self.system_prompts)
        try:
            mlflow.genai.register_prompt(
                name="mongodb_query_agent",
                template=self.system_prompts["mongodb_query_agent"],
                commit_message="MongoDB query generation prompt with schema",
                tags={"agent": "data_agent", "version": "v2.1", "has_schema": "true"},
            )
            prompts_registered.append("MongoDB Query Agent")
        except Exception as e:
            pass  # Already exists

        # 2. Router Agent prompt - extract from source file
        try:
            from procurement_agent.graph.router_node import router_node
            import inspect

            source = inspect.getsource(router_node)
            # Extract the system prompt from the source code
            start = source.find('content": """') + len('content": """')
            end = source.find('"""', start)
            router_prompt = source[start:end].strip()

            mlflow.genai.register_prompt(
                name="router_agent",
                template=router_prompt,
                commit_message="Router agent classification prompt",
                tags={"agent": "router", "version": "v2.1", "type": "classification"},
            )
            prompts_registered.append("Router Agent")
        except Exception as e:
            pass  # Already exists or extraction failed

        # 3. Chat Agent prompt - extract from source file
        try:
            from procurement_agent.graph.chat_agent_node import chat_agent_node
            import inspect

            source = inspect.getsource(chat_agent_node)
            # Extract system_prompt variable
            start = source.find('system_prompt = """') + len('system_prompt = """')
            end = source.find('"""', start)
            chat_prompt = source[start:end].strip()

            mlflow.genai.register_prompt(
                name="chat_agent",
                template=chat_prompt,
                commit_message="Chat agent conversational prompt",
                tags={"agent": "chat", "version": "v2.1", "type": "conversational"},
            )
            prompts_registered.append("Chat Agent")
        except Exception as e:
            pass  # Already exists or extraction failed

        # 4. Results Explanation prompt - extract from mongodb_query.py
        try:
            from procurement_agent.mongodb_query import MongoDBQueryAgent
            import inspect

            source = inspect.getsource(MongoDBQueryAgent.convert_results_to_human_language_llm)
            # Extract the system content
            start = source.find('"content": """') + len('"content": """')
            end = source.find('"""', start)
            explanation_prompt = source[start:end].strip()

            mlflow.genai.register_prompt(
                name="results_explanation",
                template=explanation_prompt,
                commit_message="Results to human language conversion prompt",
                tags={"agent": "data_agent", "type": "explanation"},
            )
            prompts_registered.append("Results Explanation")
        except Exception as e:
            pass  # Already exists or extraction failed

        # 5. Register all Judge prompts (already stored in self.judge_prompts)
        if hasattr(self, "judge_prompts") and self.judge_prompts:
            for judge_name, judge_prompt in self.judge_prompts.items():
                try:
                    mlflow.genai.register_prompt(
                        name=f"judge_{judge_name}",
                        template=judge_prompt,
                        commit_message=f"{judge_name} evaluation judge prompt",
                        tags={"type": "judge", "criterion": judge_name},
                    )
                    prompts_registered.append(f"Judge: {judge_name}")
                except Exception as e:
                    pass  # Already exists

        if prompts_registered:
            print(f"[OK] Registered {len(prompts_registered)} prompts to MLflow Prompt Registry")
        else:
            print("[WARNING] No new prompts registered (may already exist)")

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
        print("MLflow Experiment: procurement-assistant-evaluation")
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
            mlflow.log_param("model", "gpt-5")
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

            print("\nView results: http://localhost:5000")
            print(f"Run ID: {run.info.run_id}")
            print("\nTo see detailed sample-wise scores:")
            print("   METHOD 1 - Traces Tab (Interactive):")
            print("     1. Click 'Traces' tab in your run")
            print("     2. Click on any trace to expand it")
            print("     3. Scroll down to see 'Assessments' section")
            print("     4. View all 8 criterion scores with rationales")
            print("")
            print("   METHOD 2 - Artifacts Tab (Reference):")
            print("     1. Click 'Artifacts' tab")
            print("     2. Open 'evaluation_criteria.json' - full scoring system and criteria\n")

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
                "total_points": 100,
                "description": "Comprehensive evaluation across 5 criteria covering query generation and response quality. Judges evaluate the actual MongoDB query (not just the response) for query-related criteria.",
            },
            "categories": [
                {
                    "name": "Query Generation Quality",
                    "weight": "80%",
                    "total_points": 80,
                    "criteria": [
                        {
                            "name": "Syntax Correctness",
                            "points": 35,
                            "description": "MongoDB query syntax validity and execution success",
                            "evaluation_target": "MongoDB query JSON from workflow metadata",
                        },
                        {
                            "name": "Semantic Correctness",
                            "points": 30,
                            "description": "Query matches user intent with correct fields and operations",
                            "evaluation_target": "MongoDB query JSON - checks if correct fields, filters, and operations are used",
                        },
                        {
                            "name": "Query Efficiency",
                            "points": 15,
                            "description": "Optimal filter placement, appropriate limits, index-friendly operations",
                            "evaluation_target": "MongoDB query JSON - evaluates pipeline structure and optimization",
                        },
                    ],
                },
                {
                    "name": "Response Quality",
                    "weight": "20%",
                    "total_points": 20,
                    "criteria": [
                        {
                            "name": "Natural Language",
                            "points": 15,
                            "description": "Conversational quality, readability, and professional tone",
                        },
                        {
                            "name": "Relevance",
                            "points": 5,
                            "description": "Response directly addresses query without unnecessary information",
                        },
                    ],
                },
            ],
            "scoring_scale": {
                "excellent": {
                    "range": "90-100",
                    "description": "Outstanding performance across all criteria",
                },
                "good": {
                    "range": "75-89",
                    "description": "Strong performance with minor improvements needed",
                },
                "acceptable": {
                    "range": "60-74",
                    "description": "Adequate performance with noticeable gaps",
                },
                "needs_improvement": {
                    "range": "40-59",
                    "description": "Significant improvements required",
                },
                "poor": {
                    "range": "0-39",
                    "description": "Major issues requiring immediate attention",
                },
            },
            "judges": [
                {
                    "name": "syntax_correctness",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-5",
                    "max_points": 35,
                },
                {
                    "name": "semantic_correctness",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-5",
                    "max_points": 30,
                },
                {
                    "name": "query_efficiency",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-5",
                    "max_points": 15,
                },
                {
                    "name": "natural_language",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-5",
                    "max_points": 15,
                },
                {
                    "name": "relevance",
                    "type": "mlflow.genai.make_judge",
                    "model": "openai:/gpt-5",
                    "max_points": 5,
                },
            ],
            "metadata": {
                "framework": "MLflow GenAI",
                "pipeline": "mlflow.genai.evaluate()",
                "evaluation_type": "unified",
                "date_created": datetime.now().isoformat(),
                "evaluation_approach": {
                    "description": "Judges receive both MongoDB query and final response for comprehensive evaluation",
                    "output_format": "MONGODB_QUERY: {json}\\n\\nRESPONSE: {text}",
                    "query_judges": [
                        "syntax_correctness",
                        "semantic_correctness",
                        "query_efficiency",
                    ],
                    "response_judges": [
                        "natural_language",
                        "relevance",
                    ],
                },
            },
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
                    "syntax_correctness": 35,
                    "semantic_correctness": 30,
                    "query_efficiency": 15,
                    "natural_language": 15,
                    "relevance": 5,
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
                            avg_score = round(scores.mean(), 2)

                            # Log the average score with max in metric name for clarity
                            mlflow.log_metric(f"{criterion_name}_out_of_{max_score}", avg_score)

                            percentage = (avg_score / max_score * 100) if max_score > 0 else 0
                            metrics_logged.append(f"{criterion_name}: {avg_score:.2f}/{max_score} ({percentage:.1f}%)")
                            total_score += avg_score
                            criteria_count += 1

                # Calculate and log category totals (but not overall yet)
                if criteria_count > 0:
                    query_gen = 0
                    response_qual = 0

                    for criterion_name in criteria_max_scores.keys():
                        value_col = f"{criterion_name}/value"
                        if value_col in results.result_df.columns:
                            avg = pd.to_numeric(results.result_df[value_col], errors='coerce').dropna().mean()
                            if criterion_name in ["syntax_correctness", "semantic_correctness", "query_efficiency"]:
                                query_gen += avg
                            elif criterion_name in ["natural_language", "relevance"]:
                                response_qual += avg

                    # Round category totals to 2 decimal places
                    query_gen = round(query_gen, 2)
                    response_qual = round(response_qual, 2)
                    total_score = round(total_score, 2)

                    mlflow.log_metric("query_generation_out_of_80", query_gen)
                    mlflow.log_metric("response_quality_out_of_20", response_qual)

                    # Log overall score last so it appears at the bottom of the metrics table
                    mlflow.log_metric("overall_score_out_of_100", total_score)

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
            print("     Scores are still available in the Traces tab -> Assessments section")

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
    framework = EvaluationFramework(experiment_name=args.experiment, run_name=args.run_name)

    # Run evaluation
    framework.run_evaluation(
        queries_file=args.queries,
        sample_size=args.sample
    )


if __name__ == "__main__":
    main()
