"""
MongoDB Query Integration
Reuses the query system from experiment.ipynb
"""
import json
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from openai import OpenAI
from typing import Dict, Any, cast
import os
from pathlib import Path
from .prompts.prompts import SYSTEM_PROMPT


class MongoDBQueryAgent:
    """MongoDB query agent for procurement data"""

    def __init__(
        self,
        mongo_uri: str,
        db_name: str,
        collection_name: str,
        openai_api_key: str = ''
    ):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.openai_client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
        self.schema = self._get_collection_schema()
        self.system_prompt_template = SYSTEM_PROMPT # self._load_system_prompt()

    # def _load_system_prompt(self) -> str:
    #     """Load system prompt from file"""
    #     prompt_path = Path(__file__).parent / "prompts" / "mongodb_query_prompt2.txt"
    #     with open(prompt_path, "r") as f:
    #         return f.read()

    def _get_collection_schema(self, sample_size: int = 100) -> Dict:
        """Get collection schema by sampling documents"""
        sample_docs = list(self.collection.aggregate([{"$sample": {"size": sample_size}}]))

        if not sample_docs:
            return {}

        fields = {}
        for doc in sample_docs:
            for key, value in doc.items():
                if key == "_id":
                    continue
                if key not in fields:
                    fields[key] = {"types": {}}
                value_type = type(value).__name__
                if value_type not in fields[key]["types"]:
                    fields[key]["types"][value_type] = 0
                fields[key]["types"][value_type] += 1

        # Determine primary type
        for field_name, field_info in fields.items():
            types = field_info["types"]
            if len(types) > 1 and "NoneType" in types:
                types_without_none = {k: v for k, v in types.items() if k != "NoneType"}
                if types_without_none:
                    primary_type = max(types_without_none.items(), key=lambda x: x[1])[0]
                else:
                    primary_type = "NoneType"
            else:
                primary_type = max(types.items(), key=lambda x: x[1])[0]

            fields[field_name]["type"] = primary_type

        return fields

    def _parse_datetime_placeholders(self, query):
        """Parse datetime placeholders to Python datetime objects"""
        def replace_datetime_placeholder(obj):
            if isinstance(obj, dict):
                if ("__datetime__" in obj and len(obj) == 1) or ("$date" in obj and len(obj) == 1):
                    date_str = obj.get("__datetime__") or obj.get("$date")
                    try:
                        if 'T' in date_str:
                            date_str_clean = date_str.replace('Z', '')
                            return datetime.fromisoformat(date_str_clean)
                        else:
                            return datetime.strptime(date_str, "%Y-%m-%d")
                    except Exception as e:
                        print(f"Failed to parse date '{date_str}': {e}")
                        return obj
                else:
                    return {k: replace_datetime_placeholder(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_datetime_placeholder(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith("__datetime__:"):
                date_str = obj.split(":", 1)[1]
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except:
                    return obj
            return obj

        return replace_datetime_placeholder(query)

    def _clean_document_for_json(self, doc):
        """Convert datetime and ObjectId objects to JSON-serializable formats"""
        if isinstance(doc, dict):
            return {key: self._clean_document_for_json(value) for key, value in doc.items()}
        elif isinstance(doc, list):
            return [self._clean_document_for_json(item) for item in doc]
        elif isinstance(doc, datetime):
            return doc.isoformat()
        elif isinstance(doc, ObjectId):
            return str(doc)
        return doc

    def _execute_query(self, query_params: Dict) -> Dict:
        """Execute MongoDB query safely"""
        MAX_RESULTS = 100

        try:
            operation = query_params.get("operation")
            filter_query = self._parse_datetime_placeholders(query_params.get("filter", {}))

            if operation == "find":
                projection = query_params.get("projection", {})
                sort = query_params.get("sort", {})
                limit = min(query_params.get("limit", MAX_RESULTS), MAX_RESULTS)

                cursor = self.collection.find(filter_query, projection)
                if sort:
                    cursor = cursor.sort(list(sort.items()))
                cursor = cursor.limit(limit)

                results = [self._clean_document_for_json(doc) for doc in cursor]
                return {
                    "success": True,
                    "operation": "find",
                    "results": results,
                    "count": len(results)
                }

            elif operation == "count":
                count = self.collection.count_documents(filter_query)
                return {
                    "success": True,
                    "operation": "count",
                    "count": count
                }

            elif operation == "aggregate":
                pipeline = query_params.get("pipeline", [])

                # Validate pipeline
                if not pipeline or not isinstance(pipeline, list):
                    return {
                        "success": False,
                        "error": "Aggregation pipeline must be a non-empty array"
                    }

                # Validate each stage
                for i, stage in enumerate(pipeline):
                    if not isinstance(stage, dict):
                        return {
                            "success": False,
                            "error": f"Pipeline stage {i} must be an object, got {type(stage)}"
                        }
                    if len(stage) != 1:
                        return {
                            "success": False,
                            "error": f"Pipeline stage {i} must have exactly one field, got {len(stage)} fields: {list(stage.keys())}"
                        }

                pipeline = self._parse_datetime_placeholders(pipeline)

                # Auto-limit aggregations
                has_limit = any("$limit" in stage for stage in pipeline)
                if not has_limit:
                    pipeline.append({"$limit": MAX_RESULTS})

                print(f"Executing pipeline: {json.dumps(pipeline, default=str, indent=2)}")

                results = list(self.collection.aggregate(pipeline))
                results = [self._clean_document_for_json(doc) for doc in results]

                return {
                    "success": True,
                    "operation": "aggregate",
                    "results": results,
                    "count": len(results)
                }

            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation: {operation}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def query(self, user_query: str) -> Dict[str, Any]:
        """
        Convert natural language to MongoDB query and execute

        Args:
            user_query: Natural language question

        Returns:
            Dict with response, data, and metadata
        """
        # Build MongoDB function definition with correct typing
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "execute_mongodb_query",
                    "description": "Execute a MongoDB query on the procurement purchase_orders collection",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": ["find", "aggregate", "count"],
                                "description": "MongoDB operation type"
                            },
                            "filter": {
                                "type": "object",
                                "description": "MongoDB filter query. Use datetime objects: {\"purchase_date\": {\"$gte\": {\"__datetime__\": \"2014-01-01\"}}}"
                            },
                            "projection": {
                                "type": "object",
                                "description": "Fields to include/exclude (for find)"
                            },
                            "sort": {
                                "type": "object",
                                "description": "Sort specification"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max results to return"
                            },
                            "pipeline": {
                                "type": "array",
                                "items": {
                                    "type": "object"
                                },
                                "description": "Aggregation pipeline stages"
                            }
                        },
                        "required": ["operation"],
                        "additionalProperties": False
                    }
                }
            }
        ]

        # Create schema context and build system message from template
        schema_context = json.dumps(self.schema, indent=2)
        system_message = self.system_prompt_template.format(schema_context=schema_context)

        # Call LLM to generate query
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": system_message
                    },
                    {
                        "role": "user",
                        "content": user_query
                    }
                ],
                tools=cast(Any, tools),  # Type hint workaround for strict type checking
                tool_choice="required"  # Force function calling (not text response)
            )

            # Parse function call
            if not response.choices[0].message.tool_calls:
                return {
                    "response": "I couldn't generate a valid query for that question.",
                    "data": None,
                    "success": False
                }

            tool_call = response.choices[0].message.tool_calls[0]

            # Handle function call - cast to Any to bypass strict type checking
            # The OpenAI API will always return a function tool call for our use case
            tool_call_any = cast(Any, tool_call)

            if not hasattr(tool_call_any, 'function') or not tool_call_any.function:
                return {
                    "response": "Invalid tool call format.",
                    "data": None,
                    "success": False
                }

            query_params = json.loads(tool_call_any.function.arguments)

            # Log the generated query
            print(f"\n📝 Generated query: {json.dumps(query_params, indent=2, default=str)}")

            # Execute query
            results = self._execute_query(query_params)

            if not results["success"]:
                return {
                    "response": f"Query failed: {results.get('error')}",
                    "data": None,
                    "success": False
                }

            # Format response with LLM explanation
            response_text = self.convert_results_to_human_language_llm(user_query, results)

            return {
                "response": response_text,
                "data": results.get("results", []),
                "count": results.get("count", 0),
                "success": True,
                "query": query_params
            }

        except Exception as e:
            return {
                "response": f"Error processing query: {str(e)}",
                "data": None,
                "success": False,
                "error": str(e)
            }

    def _simple_format_results(self, results: Dict) -> str:
        """Fast simple formatting without LLM"""
        operation = results.get("operation")
        count = results.get("count", 0)
        data = results.get("results", [])

        if operation == "count":
            return f"Total: {count:,}"

        if operation == "aggregate":
            if not data:
                return "No results found."

            # Check if this is a single aggregate result (like count, sum, avg)
            if len(data) == 1:
                result = data[0]

                # Handle $count results
                if "total" in result and len(result) == 1:
                    return f"Total: {result['total']:,}"

                # Handle grouped results with _id
                if "_id" in result:
                    parts = []

                    # Format _id first
                    id_value = result["_id"]
                    if isinstance(id_value, dict):
                        id_parts = [f"{k}={v}" for k, v in id_value.items()]
                        parts.append(", ".join(id_parts))
                    elif id_value is not None:
                        parts.append(str(id_value))

                    # Format other fields
                    for key, value in result.items():
                        if key != "_id":
                            if isinstance(value, float):
                                parts.append(f"{key}: {value:,.2f}")
                            elif isinstance(value, int):
                                parts.append(f"{key}: {value:,}")
                            else:
                                parts.append(f"{key}: {value}")

                    return " | ".join(parts) if parts else str(result)

                # Single result without _id
                parts = []
                for key, value in result.items():
                    if isinstance(value, float):
                        parts.append(f"{key}: {value:,.2f}")
                    elif isinstance(value, int):
                        parts.append(f"{key}: {value:,}")
                    else:
                        parts.append(f"{key}: {value}")
                return " | ".join(parts) if parts else str(result)

            # Multiple results - show summary
            return f"Found {count:,} results"

        if operation == "find":
            if count == 0:
                return "No matching records found."
            return f"Found {count:,} records."

        return f"Query returned {count:,} results."

    def convert_results_to_human_language_llm(self, user_query: str, results: Dict) -> str:
        """Convert query results to human-readable format using LLM (matches notebook)"""
        # Sample results for LLM
        sample_results = results.get("results", [])[:5]
        count = results.get("count", 0)

        # Clean datetime objects for JSON
        sample_results = [self._clean_document_for_json(doc) for doc in sample_results]

        try:
            # Prepare minimal context (like notebook)
            context = f"Q: {user_query}\nResults ({count}): {json.dumps(sample_results[:2], indent=2)}"

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Answer in 1-2 sentences."
                        "markdown format."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                max_completion_tokens=100
            )

            return response.choices[0].message.content.strip() if response.choices[0].message.content else "No explanation."
        except Exception as e:
            print(f"LLM explanation failed: {e}")
            return self._simple_format_results(results)
