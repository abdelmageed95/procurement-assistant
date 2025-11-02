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
from .prompts.data_columns import DGS_PURCHASING_DATA_DICT


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
        self._save_schema_to_file()  # Save schema every time
        self.system_prompt_template = SYSTEM_PROMPT # self._load_system_prompt()

    # def _load_system_prompt(self) -> str:
    #     """Load system prompt from file"""
    #     prompt_path = Path(__file__).parent / "prompts" / "mongodb_query_prompt2.txt"
    #     with open(prompt_path, "r") as f:
    #         return f.read()

    def _get_collection_schema(self, sample_size: int = 100) -> Dict:
        # TODO: ensure that sample values are not empty or None
        """
        Get enriched collection schema with business context.

        Returns field names, types, AND business descriptions from data_columns.py
        """
        # CSV to MongoDB field mapping
        CSV_TO_MONGODB_FIELD_MAP = {
            "Creation Date": "creation_date",
            "Purchase Date": "purchase_date",
            "Fiscal Year": "fiscal_year",
            "LPA Number": "lpa_number",
            "Purchase Order Number": "purchase_order_number",
            "Requisition Number": "requisition_number",
            "Acquisition Type": "acquisition_type",
            "Sub-Acquisition Type": "sub_acquisition_type",
            "Acquisition Method": "acquisition_method",
            "Sub-Acquisition Method": "sub_acquisition_method",
            "Department Name": "department_name",
            "Supplier Code": "supplier_code",
            "Supplier Name": "supplier_name",
            "Supplier Qualifications": "supplier_qualifications",
            "Supplier Zip Code": "supplier_zip_code",
            "CalCard": "cal_card",
            "Item Name": "item_name",
            "Item Description": "item_description",
            "Quantity": "quantity",
            "Unit Price": "unit_price",
            "Total Price": "total_price",
            "Classification Codes": "classification_codes",
            "Normalized UNSPSC": "normalized_unspsc",
            "Commodity Title": "commodity_title",
            "Class": "class",
            "Class Title": "class_title",
            "Family": "family",
            "Family Title": "family_title",
            "Segment": "segment",
            "Segment Title": "segment_title",
            "Location": "location"
        }

        sample_docs = list(self.collection.aggregate([{"$sample": {"size": sample_size}}]))

        if not sample_docs:
            return {}

        fields = {}
        for doc in sample_docs:
            for key, value in doc.items():
                if key == "_id":
                    continue
                if key not in fields:
                    fields[key] = {"types": {}, "sample_values": set()}
                value_type = type(value).__name__
                if value_type not in fields[key]["types"]:
                    fields[key]["types"][value_type] = 0
                fields[key]["types"][value_type] += 1

                # Collect sample values (limit to 5)
                if len(fields[key]["sample_values"]) < 5:
                    fields[key]["sample_values"].add(str(value))

        # Create reverse mapping
        mongodb_to_csv = {v: k for k, v in CSV_TO_MONGODB_FIELD_MAP.items()}

        # Determine primary type and enrich with business context
        for field_name, field_info in fields.items():
            types = field_info["types"]

            # Determine primary type (prefer non-None types)
            if len(types) > 1 and "NoneType" in types:
                types_without_none = {k: v for k, v in types.items() if k != "NoneType"}
                if types_without_none:
                    primary_type = max(types_without_none.items(), key=lambda x: x[1])[0]
                else:
                    primary_type = "NoneType"
            else:
                primary_type = max(types.items(), key=lambda x: x[1])[0]

            fields[field_name]["type"] = primary_type

            # Calculate nullable status and percentage
            has_none = "NoneType" in types
            none_count = types.get("NoneType", 0)
            total_count = sum(types.values())

            fields[field_name]["nullable"] = has_none
            if has_none:
                fields[field_name]["null_percentage"] = round(none_count / total_count * 100, 1)

            # Convert sample_values from set to list
            fields[field_name]["sample_values"] = list(fields[field_name]["sample_values"])

            # Remove internal types dict (not needed in final schema)
            del fields[field_name]["types"]

            # ENRICHMENT: Add business description from data_columns.py
            if field_name in mongodb_to_csv:
                csv_field = mongodb_to_csv[field_name]
                if csv_field in DGS_PURCHASING_DATA_DICT:
                    fields[field_name]["description"] = DGS_PURCHASING_DATA_DICT[csv_field]

            # Add usage notes for converted fields
            if field_name.endswith("_str"):
                fields[field_name]["note"] = "Display only - use non-_str version for queries"
            elif field_name == "creation_date":
                fields[field_name]["note"] = "Datetime object - use for date queries with $gte, $lte"
            elif field_name == "purchase_date":
                fields[field_name]["note"] = "Datetime object - use for date queries (creation_date preferred)"
            elif field_name in ["total_price", "unit_price"]:
                fields[field_name]["note"] = "Float - use for numeric operations ($gt, $sum, $avg)"
            elif field_name == "quantity":
                fields[field_name]["note"] = "Integer - use for counting and arithmetic"
            elif field_name == "acquisition_number":
                fields[field_name]["type"] = "str"
                fields[field_name]["sample_values"].extend(["REQ0009786", "REQ0009048"])

        return fields

    def _save_schema_to_file(self):
        """Save the generated schema to data/collection_schema.json"""
        # Create data directory if it doesn't exist
        data_dir = Path(__file__).parent.parent / "data"
        data_dir.mkdir(exist_ok=True)

        # Save schema to JSON file (overwrites if exists)
        schema_file = data_dir / "collection_schema.json"
        with open(schema_file, 'w', encoding='utf-8') as f:
            json.dump(self.schema, f, indent=2, ensure_ascii=False)

        print(f"Schema saved to: {schema_file}")

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
        """
        Execute MongoDB query safely with two-tier approach:
        - Limited results (100) for fast chat summary
        - Complete results (unlimited) for technical details and downloads
        """
        MAX_SUMMARY_RESULTS = 100
        MAX_COMPLETE_RESULTS = 10000  # Safety limit to prevent memory issues

        try:
            operation = query_params.get("operation")
            filter_query = self._parse_datetime_placeholders(query_params.get("filter", {}))

            if operation == "find":
                projection = query_params.get("projection", {})
                sort = query_params.get("sort", {})

                # Execute LIMITED query for summary
                cursor_limited = self.collection.find(filter_query, projection)
                if sort:
                    cursor_limited = cursor_limited.sort(list(sort.items()))
                cursor_limited = cursor_limited.limit(MAX_SUMMARY_RESULTS)
                summary_results = [self._clean_document_for_json(doc) for doc in cursor_limited]

                # Execute COMPLETE query for downloads (with safety limit)
                cursor_complete = self.collection.find(filter_query, projection)
                if sort:
                    cursor_complete = cursor_complete.sort(list(sort.items()))
                cursor_complete = cursor_complete.limit(MAX_COMPLETE_RESULTS)
                complete_results = [self._clean_document_for_json(doc) for doc in cursor_complete]

                # Get total count
                total_count = self.collection.count_documents(filter_query)

                return {
                    "success": True,
                    "operation": "find",
                    "results": summary_results,  # For chat summary
                    "count": len(summary_results),
                    "complete_results": complete_results,  # For downloads
                    "total_count": total_count  # Actual total in database
                }

            elif operation == "count":
                count = self.collection.count_documents(filter_query)
                return {
                    "success": True,
                    "operation": "count",
                    "count": count,
                    "complete_results": [],  # No results for count operations
                    "total_count": count
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

                # Remove any existing $limit stage for complete query (if it doesn't have a limit and it for summary results)
                pipeline_without_limit = [stage for stage in pipeline if "$limit" not in stage]

                # Execute LIMITED query for summary
                pipeline_limited = pipeline_without_limit.copy()
                pipeline_limited.append({"$limit": MAX_SUMMARY_RESULTS})

                print(f"Executing LIMITED pipeline (summary): {json.dumps(pipeline_limited, default=str, indent=2)}")
                summary_results = list(self.collection.aggregate(pipeline_limited))
                summary_results = [self._clean_document_for_json(doc) for doc in summary_results]

                # Execute COMPLETE query for downloads (with safety limit)
                pipeline_complete = pipeline_without_limit.copy()
                pipeline_complete.append({"$limit": MAX_COMPLETE_RESULTS})

                print(f"Executing COMPLETE pipeline (downloads): {json.dumps(pipeline_complete, default=str, indent=2)}")
                complete_results = list(self.collection.aggregate(pipeline_complete))
                complete_results = [self._clean_document_for_json(doc) for doc in complete_results]

                # Get total count by running pipeline with $count
                pipeline_count = pipeline_without_limit.copy()
                pipeline_count.append({"$count": "total"})
                count_result = list(self.collection.aggregate(pipeline_count))
                total_count = count_result[0]["total"] if count_result else len(complete_results)

                return {
                    "success": True,
                    "operation": "aggregate",
                    "results": summary_results,  # For chat summary (limited to 100)
                    "count": len(summary_results),
                    "complete_results": complete_results,  # For downloads (up to 10,000)
                    "total_count": total_count  # Actual total in database
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
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_query},
                ],
                tools=cast(Any, tools),  # Type hint workaround for strict type checking
                tool_choice="required",  # Force function calling (not text response)
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
            print(f"\nGenerated query: {json.dumps(query_params, indent=2, default=str)}")

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
                "data": results.get("results", []),  # Limited results for summary
                "complete_results": results.get("complete_results", []),  # Complete results for downloads
                "count": results.get("count", 0),  # Count of summary results
                "total_count": results.get("total_count", 0),  # Total count in database
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
        """Convert query results to human-readable format using LLM"""
        all_results = results.get("results", [])
        count = results.get("count", 0)

        # Determine sample size based on total count
        if count <= 5:
            sample_size = count  # Show all
        elif count <= 20:
            sample_size = min(10, count)  # Show up to 10
        else:
            sample_size = 15  # For large result sets, show top 15

        sample_results = all_results[:sample_size]

        # Clean datetime objects for JSON
        sample_results = [self._clean_document_for_json(doc) for doc in sample_results]

        try:
            # Build context
            if count > sample_size:
                # Partial results
                context = (
                    f"User Question: {user_query}\n\n"
                    f"Query returned {count} total results.\n"
                    f"Top {sample_size} results:\n"
                    f"{json.dumps(sample_results, indent=2)}"
                )
            else:
                # All results
                context = (
                    f"User Question: {user_query}\n\n"
                    f"Query returned {count} results:\n"
                    f"{json.dumps(sample_results, indent=2)}"
                )

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a friendly, knowledgeable data analyst who explains California procurement data in natural, engaging language.

PERSONALITY:
- Conversational and warm (not robotic)
- Enthusiastic about insights and patterns
- Use natural transitions ("Interesting!", "Here's what stands out", "Let me break this down")
- Vary your sentence structure
- Tell a story with the data

FORMATTING RULES:
1. Start with a natural sentence, not "Found X results"
2. Use conversational intros
3. Mix narrative with data points
4. Highlight surprising insights with natural reactions
5. Use natural language without emojis
6. Format numbers clearly: $484M (not 484000000), $55.1M, etc.
7. Organize and well structured responses with markdown where appropriate or bullets for clarity and conciseness
8. If partial results, naturally suggest: "Want to see all the details? Check out the Technical Details button below"

STRUCTURE:
- Opening: Natural intro sentence about what the data shows
- Key findings: Top 5-10 results with context
- Insight: One interesting pattern or standout finding
- Closing: Friendly pointer to technical details if there's more data

AVOID:
- "Found X results" (too robotic)
- Bullet points only (mix with narrative)
- Dry statistical language
- Repeating "total", "results", "query returned"

EXAMPLE:
Instead of: "Found 83 departments. Top 10: 1. Health Care: $484M..."
Write: "Looking at spending across California's departments, Health Care Services absolutely dominates with $484M - that's nearly 65% of all procurement spending! Here are the top departments:

**Health Care Services** leads the pack at $484.4M
**Water Resources** comes in second at $55.1M
**Transportation** rounds out the top three at $54.3M
...

What really stands out is how concentrated the spending is - just these top 5 departments account for over 80% of the total budget.

Want the complete breakdown of all 83 departments? Click Technical Details below to see everything and download the data."
""",
                    },
                    {"role": "user", "content": context},
                ],
                max_completion_tokens=500,  # Allow longer responses for complete answers
            )

            return response.choices[0].message.content.strip() if response.choices[0].message.content else "No explanation."
        except Exception as e:
            print(f"LLM explanation failed: {e}")
            return self._simple_format_results(results)
