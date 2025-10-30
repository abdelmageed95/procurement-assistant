#  Procurement Data Assistant

A production-ready, intelligent conversational AI system that analyzes  purchase orders using natural language queries, MongoDB aggregations, and multi-agent routing.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange.svg)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-brightgreen.svg)

---

##  Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Data Import](#data-import)
- [Evaluation Framework](#evaluation-framework)
- [Query Examples](#query-examples)
- [Architecture Decisions](#architecture-decisions)
- [Detailed Documentation](#detailed-documentation)
- [Contributing](#contributing)

---

##  Overview

This project implements a **specialized multi-agent conversational system** for analyzing procurement data (used open-source CA state dataset 2012-2015, purchases over $5,000 as knowledge base for the data query agent). The system intelligently routes between data queries and general conversation:

### **Dual-Mode Intelligence:**
-  **Data Query Agent** - Answers questions using MongoDB aggregations and natural language explanations
-  **Chat Agent** - Handles greetings, help requests, and general conversation
-  **Smart Router** - Automatically classifies user intent and routes to the appropriate agent

### **Core Capabilities:**
-  **Intelligent Query Generation** - Natural language → MongoDB queries using OpenAI function calling
-  **Dual Memory System** - Short-term (MongoDB) + Long-term (ChromaDB) for context-aware responses
-  **Safety Guardrails** - Input/output validation focused on safety (not topic restriction)
-  **Complete Data Access** - View all results with Technical Details modal + CSV/JSON downloads
-  **Natural Language Responses** - Engaging, conversational explanations (not robotic)
-  **Real-time WebSocket** - Instant query results and detailed explanations
-  **Smart Resend** - Retry failed queries with automatic cleanup
-  **Session Management** - Persistent sessions across page refreshes, history browser, and session switching

---

##  Key Features

### 1. **Intelligent Multi-Agent Routing** 

The system automatically classifies user intent and routes to the appropriate agent:

```
User Message → Router Agent → Decision:
                              ├─ Data Query → MongoDB Agent
                              └─ General Chat → Chat Agent
```

**Examples:**
- "Hello!" → Chat Agent (greeting)
- "What is the average order value?" → Data Agent (query)
- "Thanks!" → Chat Agent (acknowledgment)
- "Show me top 5 suppliers" → Data Agent (aggregation)

### 2. **Complete Data Visibility with Two-Tier Query System** 

**Problem:** Users asking "What was the total spending by department?" need to see ALL results, not just the first 100. 

**Solution: Two-Tier Query Execution**
- **Tier 1 - Fast Summary** (Limited to 100): Quick response for chat display
- **Tier 2 - Complete Data** (Up to 10,000): Full dataset for downloads and analysis
- **Total Count Tracking**: Shows actual database totals vs available data

**How It Works:**
```
Query Execution:
├─ LIMITED Query (100 results) → Fast chat summary
├─ COMPLETE Query (10,000 results) → Technical Details & downloads
└─ COUNT Query → Actual total in database

User: "What was the total spending by department?"
Response: "Looking at spending across California's departments,
Health Care Services absolutely dominates with $484M - that's
nearly 65% of all procurement spending! Here are the top 10...

--> Want the complete breakdown of all 83 departments? Click
Technical Details below to see everything and download the data."

[Technical Details Button] → Opens modal with:
- Total results: 83 | Complete data available (83 records)
- ALL 83 results viewable (scrollable JSON)
- [📥 Download CSV] [📥 Download JSON] - Contains all 83 records
- Exact MongoDB query used
```

**Performance Benefits:**
-  **Fast chat responses** - Limited queries return quickly
-  **Complete data access** - Downloads include up to 10,000 records
-  **Safety limits** - 10K max prevents memory issues
-  **Transparency** - Clear messaging about total vs available counts

### 3. **Natural, Engaging Responses** 

**Personality:**
- Conversational not robotic
- Enthusiastic about insights and patterns
- Uses natural transitions
- Tells a story with the data
- Highlights surprising findings

### 4. **Session Persistence** 

**Features:**
- Sessions persist across page refreshes (localStorage)
- View all past sessions in History modal
- Load any previous conversation
- Delete unwanted sessions
- Create new sessions on demand
- Active session highlighted

**UI:**
- **New Session** button - Start fresh conversation
- **History** button - Browse all past sessions
- **Clear Chat** button - Clear current session

### 5. **Safety-Focused Guardrails** 

-  Safety checks only (allows chat + data queries)

**What's Protected:**
- Length limits (max 5000 chars)
- Harmful content detection
- Prompt injection attempts
- Basic PII detection (emails, SSNs)
- HTML/script tag stripping
- XSS prevention

**What's Allowed:**
- Greetings and casual chat
- Help requests
- Data queries
- Clarification questions

### 6. **Intelligent Query System**

- **Natural Language to MongoDB**: Converts questions like "How many purchases in 2014?" to MongoDB aggregation pipelines
- **Function Calling**: Uses OpenAI's function calling API (`tool_choice="required"`) for structured query generation
- **Date Handling**: Automatic datetime parsing with `__datetime__` placeholder system
- **Query Validation**: Ensures valid MongoDB operations (find, aggregate, count)
- **Error Recovery**: Helpful error messages with retry functionality

### 7. **Advanced Memory Management**

**Short-Term Memory (MongoDB):**
- Stores recent conversation history
- Fast access for current session context
- Message-level granularity
- Used for immediate context

**Long-Term Memory (ChromaDB):**
- Semantic search using Sentence Transformers
- Stores meaningful Q&A pairs
- Smart duplicate detection (last 5 messages)
- Context retrieval for similar queries

### 8. **Data Analysis Capabilities**

- **Aggregations**: Group by department, supplier, date ranges
- **Filtering**: Find orders by price, date, department
- **Statistics**: Average, sum, count, min, max
- **Sorting**: Order results by any field
- **Date Operations**: Year, quarter, month-based analysis

### 9. **Modern User Interface**

- **Real-time Chat**: WebSocket-based instant messaging
- **Smart Resend Button**: Automatically removes old responses when retrying
- **Technical Details Modal**: View complete results + download options
- **Welcome Message**: Fades on first user message
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Professional Styling**: Calm color palette, smooth animations

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Input                           │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                   Safety Guardrails                          │
│  • Length limits  • Harmful content  • PII detection         │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                    Router Agent (GPT-4o-mini)                │
│  Classifies: data_query OR general_chat                     │
└──────┬──────────────────────────────────────────┬───────────┘
       │                                           │
       ↓                                           ↓
┌─────────────────────┐              ┌─────────────────────────┐
│   Data Query Agent  │              │    General Chat Agent    │
│   • MongoDB Query   │              │   • Greetings           │
│   • LLM Explanation │              │   • Help & Guidance     │
│   • Technical Data  │              │   • Conversation        │
└─────────┬───────────┘              └──────────┬──────────────┘
          │                                     │
          ↓                                     ↓
┌─────────────────────────────────────────────────────────────┐
│                    Memory System                             │
│  Short-term (MongoDB)  +  Long-term (ChromaDB)              │
└─────────────────────────────────────────────────────────────┘
```

### Router Decision Logic

```
Input: "Hello!"
  ↓ Router Analysis
  → Keywords: greeting, casual
  → Decision: general_chat
  → Route to: Chat Agent
  → Response: "Hi! I'm here to help..."

Input: "What is the average order value?"
  ↓ Router Analysis
  → Keywords: what is, average, value (data question)
  → Decision: data_query
  → Route to: Data Agent
  → MongoDB Query: { $group: { _id: null, avg: { $avg: "$total_price" }}}
  → Response: "The average order value is approximately $237,301.49..."
```

### LangGraph Workflow

```mermaid
graph TD
    START([User Message]) --> Guard[Safety Guardrails]

    Guard -->|Safe| Router[Router Agent]
    Guard -->|Unsafe| END[Reject]

    Router -->|data_query| DataAgent[Data Query Agent]
    Router -->|general_chat| ChatAgent[Chat Agent]

    DataAgent --> QueryGen[Generate MongoDB Query]
    QueryGen --> Execute[Execute Query]
    Execute --> Explain[LLM Explanation]
    Explain --> Memory[Memory Update]

    ChatAgent --> ChatLLM[Generate Response]
    ChatLLM --> Memory

    Memory --> Output[Output Guardrails]
    Output --> END([Return Response])

    style Router fill:#FFE4B5
    style DataAgent fill:#87CEEB
    style ChatAgent fill:#98FB98
    style Guard fill:#FFB6C1
```

---

##  Project Structure

```
procurement_experiments/
│
├── procurement_agent/                 # Main application package
│   ├── api/                          # FastAPI application
│   │   ├── main.py                   # Server, WebSocket, REST endpoints
│   │   └── __init__.py
│   │
│   ├── graph/                        # LangGraph workflow components
│   │   ├── router_node.py            # Intent classification router
│   │   ├── chat_agent_node.py        # General conversation agent
│   │   ├── procurement_agent_node.py # Data query agent
│   │   ├── memory_nodes.py           # Memory fetch/update nodes
│   │   ├── guardrails.py             # Safety-focused guardrails
│   │   ├── duplicate_detection.py    # Smart deduplication
│   │   └── __init__.py
│   │
│   ├── memory/                       # Dual memory system
│   │   ├── short_term.py             # MongoDB conversation history
│   │   ├── long_term.py              # ChromaDB semantic memory
│   │   └── __init__.py
│   │
│   ├── prompts/                      # System prompts
│   │   └── prompts.py                # Query generation + explanations
│   │
│   ├── static/                       # Frontend assets
│   │   ├── index.html                # Chat UI with session management
│   │   ├── app.js                    # WebSocket + download functionality
│   │   └── style.css                 # Professional styling
│   │
│   ├── mongodb_query.py              # Enhanced query agent with natural responses
│   ├── workflow.py                   # Multi-agent LangGraph workflow
│   ├── config.py                     # Configuration management
│   └── __init__.py
│
├── experiment.ipynb                  # Original Jupyter notebook
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment variables template
└── README.md                         # This file
```

---

##  Installation

### Prerequisites

- Python 3.10+
- MongoDB 4.4+ (running locally or remote)
- OpenAI API key
- 4GB+ RAM (for Sentence Transformers embeddings)

### Step 1: Clone the Repository

```bash
git clone https://github.com/abdelmageed95/procurement-agent.git
cd procurement-agent
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```


### Step 4: Set Up Environment Variables

Edit `.env`:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-your_openai_api_key_here
LLM_MODEL=gpt-4o-mini

# MongoDB Configuration
MONGO_URI=mongodb://localhost:27017
MONGO_DB=procurement_db
MONGO_COLLECTION=purchase_orders

# Application Configuration
ENABLE_GUARDRAILS=true
LOG_LEVEL=INFO

# Memory Configuration
SHORT_TERM_LIMIT=10
LONG_TERM_TOP_K=3
```

### Step 5: Load Procurement Data

**Option A: Import from CSV**
```bash
mongoimport --db procurement_db --collection purchase_orders \
  --type csv --headerline --file procurement_data.csv
```

**Option B: Use existing MongoDB**
Update `MONGO_URI` to point to your existing database.

### Step 6: Run the Application

```bash
cd procurement_agent/api
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access the application at: **http://localhost:8000**

---

##  Usage

### Example Conversations

#### **General Chat**
```
User: "Hello!"
Agent: "Hi there! How can I help you?"
```

#### **Data Query with Complete Results**
```
User: "What was the total spending by department?"

Agent: "Looking at spending across California's departments, Health
Care Services absolutely dominates with $484M - that's nearly 65%
of all procurement spending!

**Health Care Services** leads the pack at $484.4M
**Water Resources** comes in second at $55.1M
**Transportation** rounds out the top three at $54.3M
**Public Health** follows at $43.6M
**Corrections and Rehabilitation** at $25.2M

What really stands out is how concentrated the spending is - just
these top 5 departments account for over 80% of the total budget.

Want the complete breakdown of all 83 departments? Click Technical
Details below to see everything and download the data."

[Technical Details Button]
```

Click "Technical Details" to see:
- All 83 results in scrollable JSON
- Download CSV button (opens in Excel)
- Download JSON button (for analysis)
- Exact MongoDB query used



### Supported Query Types

**Data Queries (Routed to Data Agent):**
- "How many purchases were made in 2014?"
- "What was the total spending by department?"
- "Show me orders over $50,000"
- "What is the average order value?"
- "Top 5 suppliers by order count"
- "Find orders from Department of Transportation"

**General Chat (Routed to Chat Agent):**
- "Hello!", "Hi there!", "Hey!"
- "Thanks!", "Thank you!"
- "What can you do?"
- "How does this work?"
- "Can you help me?"

---

## 📥 Data Import

### CSV to MongoDB Importer

The project includes a standalone command-line tool for importing CSV data into MongoDB with proper type conversion.

#### **Quick Start:**

```bash
# Basic usage
python import_csv_to_mongodb.py PURCHASE-ORDER_SAMPLE.csv

# Custom database and collection
python import_csv_to_mongodb.py data.csv --database my_db --collection orders

# Remote MongoDB
python import_csv_to_mongodb.py data.csv --mongo-uri mongodb://user:pass@host:27017/

# Custom batch size
python import_csv_to_mongodb.py data.csv --batch-size 5000

# Append to existing data (don't clear)
python import_csv_to_mongodb.py data.csv --no-clear
```

#### **Features:**

**Data Type Conversion:**
- Dates: `"01/15/2013"` → `datetime(2013, 1, 15)`
- Currency: `"$1,234.56"` → `1234.56` (float)
- Numbers: `"123"` → `123` (int)
- Empty strings → `None` (null)

**Command-Line Arguments:**
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `csv_file` | **Required** | - | Path to CSV file |
| `--mongo-uri` | Optional | `mongodb://localhost:27017/` | MongoDB URI |
| `--database` | Optional | `procurement_db` | Database name |
| `--collection` | Optional | `purchase_orders` | Collection name |
| `--batch-size` | Optional | `1000` | Batch insert size |
| `--no-clear` | Flag | False | Append mode (don't clear) |

**Progress Tracking:**
```
CALIFORNIA PROCUREMENT DATA IMPORTER
Connected to MongoDB: procurement_db.purchase_orders
Cleared 0 existing documents
Processing CSV: data.csv
   Batch size: 1000

   Inserted 1000 rows...
   Inserted 2000 rows...
   Inserted 3000 rows...

IMPORT SUMMARY
Total rows processed:    3,437
Dates converted:         3,437
Prices converted:        3,437
Errors:                  0

Collection 'purchase_orders' now has 3,437 documents
```

#### **Help:**

```bash
python import_csv_to_mongodb.py --help
```

---

## Evaluation Framework

The project includes a **unified evaluation framework** that combines MLflow GenAI standardized pipeline with detailed custom scoring across 7 criteria.

### **Quick Start:**

```bash
# Unified evaluation (RECOMMENDED)
python evaluate.py --sample 5      # Test with 5 queries
python evaluate.py                 # Full evaluation (all queries)

# Legacy evaluation systems (for comparison)
python evaluate_system.py --sample 5          # Detailed manual evaluation
python evaluate_system_genai.py --sample 5    # MLflow GenAI only
```

### **Why Unified?**

The new `evaluate.py` combines:
- **MLflow GenAI Pipeline**: Standardized `mlflow.genai.evaluate()` framework
- **7 Custom Judges**: All detailed criteria using `make_judge()`
- **Prompt Registry**: Automatic prompt versioning with `register_prompt()`
- **Complete Tracking**: System prompts, schema, workflow steps
- **UI Integration**: Results in MLflow Evaluations and Traces tabs

### **Advanced Features:**

The evaluation framework includes comprehensive MLflow GenAI capabilities:

**Advanced Tracking:**
- **System Prompts**: All agent system prompts (MongoDB, Router, Chat) logged
- **Prompt Versioning**: All LLM-as-judge prompts logged as artifacts with outputs
- **Token & Cost Tracking**: Monitor OpenAI API usage and estimated costs
- **Dataset Management**: Versioned MLflow datasets with lineage
- **Nested Runs**: Query-level metrics and debugging
- **Model Signature**: Explicit input/output schemas
- **LangGraph Tracing**: Automatic multi-step agent workflow capture
- **Schema Logging**: Complete MongoDB schema with business descriptions

**Additional Metrics:**
```
Token Usage & Cost:
  - total_tokens: 125,420
  - total_prompt_tokens: 98,230
  - total_completion_tokens: 27,190
  - total_cost_usd: $0.0312

Query-Level Analysis:
  - Individual query runs with detailed metrics
  - Per-query artifacts (generated queries, responses)
  - Easy failure debugging

Enhanced Artifacts:
  - system_prompts/ (MongoDB, Router, Chat agent prompts)
  - prompts/ (all LLM judge prompts + variables + outputs)
  - workflow_steps_complete.json (step-by-step execution)
  - generated_query.json (per query)
  - response.txt (per query)
  - mongodb_schema.json (complete schema)
  - model_signature.json
  - prompt_templates_used.json
```

**Learn More:**
- See [UNIFIED_EVALUATION.md](UNIFIED_EVALUATION.md) for complete unified evaluation guide
- See [MLFLOW_NAVIGATION_GUIDE.md](MLFLOW_NAVIGATION_GUIDE.md) for step-by-step UI navigation
- See [MLFLOW_UI_GUIDE.md](MLFLOW_UI_GUIDE.md) for complete artifact reference
- See [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md) for MLflow GenAI features overview

### **Evaluation Criteria:**

The framework uses a weighted scoring system (0-100 points) across three main dimensions:

#### **1. Query Generation Quality (45%)**

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Semantic Correctness** | 25% | Does the query match user intent? (LLM-as-judge) |
| **Query Efficiency** | 20% | Are $match stages early? Are limits applied? Optimal structure? |

#### **2. Result Accuracy (35%)**

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Data Correctness** | 25% | Are the results accurate? No fabricated data? (validates against DB) |
| **Completeness** | 10% | Does the query return all expected data? |

#### **3. Response Quality (20%)**

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Natural Language** | 10% | Is the response conversational and engaging? |
| **Relevance** | 5% | Does the response directly address the query? |
| **Formatting** | 5% | Is the response well-structured? |

### **Features:**

**LLM-as-Judge Evaluation:**
- Uses GPT-4o-mini to evaluate semantic correctness and response quality
- Provides objective, consistent scoring across runs

**MLflow Integration:**
- Tracks all metrics, parameters, and artifacts
- Supports comparison across multiple evaluation runs
- Stores detailed results JSON for analysis

**Query Categorization:**
- Automatically categorizes queries by type (aggregation, time-based, ranking, etc.)
- Provides category-level performance insights

**Comprehensive Reporting:**
```
EVALUATION SUMMARY
======================================================================
Success Rate: 100.0%
Failure Rate: 0.0%
Average Score: 99.25/100
Average Execution Time: 12.55s

Scores by Category:
  - aggregation_ranking: 100.00/100
  - aggregation_sum: 98.50/100

Scores by Criterion:
  - Completeness: 10.00
  - Data Correctness: 20.00
  - Formatting: 5.00
  - Natural Language: 10.00
  - Query Efficiency: 14.25
  - Relevance: 5.00
  - Semantic Correctness: 20.00
```

### **Query File Format:**

Create a text file with numbered queries (one per line):

```
1. What is the total spending across all departments in 2014?
2. Which department spent the most overall?
3. Show me the top 5 suppliers by total contract value
4. What was the average order value in 2013?
...
```

### **MLflow UI:**

View detailed evaluation results in the MLflow web interface:

#### **Starting MLflow UI:**

```bash
# Start MLflow UI (from project root)
source .venv/bin/activate
mlflow ui --port 5000

# Or use custom port
mlflow ui --port 8080
```

The UI will be available at: **http://localhost:5000**

#### **Navigating the MLflow UI:**

**Step 1: Experiments Dashboard**
- Open http://localhost:5000 in your browser
- You'll see all experiments listed
- Click on **"procurement-assistant-evaluation"** experiment

**Step 2: View All Runs**
- See a table of all evaluation runs with:
  - **Run Name**: e.g., `eval_20251030_164908`
  - **Created**: Timestamp of evaluation
  - **Duration**: How long the evaluation took
  - **Metrics Preview**: Key scores at a glance

**Step 3: Explore Run Details**

Click on any run name to see:

1. **Metrics Tab**: All 8 evaluation criteria scores
   - `avg_score` - Overall score (0-100)
   - `success_rate` - % of successful queries
   - `avg_execution_time` - Average time per query
   - Individual criterion averages:
     - `avg_syntax_correctness`
     - `avg_semantic_correctness`
     - `avg_query_efficiency`
     - `avg_data_correctness`
     - `avg_completeness`
     - `avg_natural_language`
     - `avg_relevance`
     - `avg_formatting`

2. **Parameters Tab**: Evaluation configuration
   - `total_queries` - Number of queries evaluated
   - `evaluation_date` - When evaluation was run
   - `model_version` - LLM model used

3. **Artifacts Tab**: Detailed results
   - Click **`evaluation_results_*.json`** to download
   - View per-query breakdown:
     - User query text
     - Generated MongoDB query
     - Response text
     - Individual scores by criterion
     - Success/failure status
     - Execution time

**Step 4: Compare Multiple Runs**
- Check boxes next to multiple runs
- Click **"Compare"** button
- See side-by-side comparison of:
  - All metrics across runs
  - Parameter differences
  - Performance trends
- Useful for tracking improvements over time

**Step 5: Visualizations**
- MLflow automatically generates charts for numeric metrics
- View score distributions and trends
- Export charts for reports

#### **Example MLflow Workflow:**

```bash
# 1. Run baseline evaluation
python evaluate_system.py --run-name baseline

# 2. Make system improvements
# ... (code changes) ...

# 3. Run new evaluation
python evaluate_system.py --run-name after-optimization

# 4. Start MLflow UI
mlflow ui

# 5. Compare runs in browser
# - Select both "baseline" and "after-optimization"
# - Click "Compare"
# - Analyze metric improvements
```

#### **Quick CLI Check:**

View results without starting UI:

```bash
# List all experiments
mlflow experiments list

# View specific run details
mlflow runs describe --run-id <run-id>

# View latest results JSON directly
find mlruns -name "evaluation_results_*.json" -type f | sort -r | head -1 | xargs cat | jq
```

### **Command-Line Arguments:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--queries` | Optional | `evaluate.txt` | Path to queries file |
| `--mlflow-experiment` | Optional | `procurement-assistant-evaluation` | MLflow experiment name |
| `--run-name` | Optional | `eval_YYYYMMDD_HHMMSS` | Custom run name |
| `--sample` | Optional | All queries | Evaluate only first N queries |

### **Help:**

```bash
python evaluate_system.py --help
```

---

##  Query Examples

### 1. Aggregation with Complete Data Access

**Query:** "What was the total spending by department?"

**Generated MongoDB:**
```json
{
  "operation": "aggregate",
  "pipeline": [
    {"$group": {"_id": "$department_name", "total_spending": {"$sum": "$total_price"}}},
    {"$sort": {"total_spending": -1}},
    {"$limit": 100}
  ]
}
```

**Chat Response:**
```
Looking at spending across California's departments, Health Care
Services absolutely dominates with $484M...

[Shows top 15 results with insights]

Click Technical Details to see all 83 departments and download data.
```

**Technical Details Modal:**
- Shows ALL 83 results
- Download CSV: `query-results-1234567890.csv`
- Download JSON: `query-results-1234567890.json`

### 2. Simple Count Query

**Query:** "How many purchases in 2014?"

**Generated MongoDB:**
```json
{
  "operation": "aggregate",
  "pipeline": [
    {"$match": {"creation_date": {"$gte": {"__datetime__": "2014-01-01"}, "$lt": {"__datetime__": "2015-01-01"}}}},
    {"$count": "total"}
  ]
}
```

**Response:** "Looking at 2014, California made 12,543 procurement purchases totaling $156.7M across all departments."

### 3. Find with Filter

**Query:** "Find orders over $50,000"

**Generated MongoDB:**
```json
{
  "operation": "find",
  "filter": {"total_price": {"$gt": 50000}},
  "sort": {"total_price": -1},
  "limit": 100
}
```

**Response:** "I found 1,234 orders over $50,000! The largest was a whopping $2.3M from the Department of Transportation. Here are the top orders..."

---

##  Architecture Decisions

### Why Multi-Agent Routing?

**Decision:** Separate agents for data queries vs. general chat

**Rationale:**
-  **Better UX**: System can greet users and provide help
-  **Specialized Agents**: Each agent excels at its specific task
-  **Flexible**: Easy to add more agent types in the future
-  **No Performance Impact**: Data queries go straight to MongoDB agent as before

### Why Two-Tier Query System?

**Decision:** Execute two queries per request (limited + complete)

**Rationale:**
-  **Fast Responses**: Limited query (100) returns quickly for chat
-  **Complete Data**: Complete query (10K) ensures downloads have all data
-  **User Expectations**: Users expect "download all" to actually download all
-  **Safety Balance**: 10K limit prevents memory issues while being practical
-  **Transparency**: Clear messaging about total vs available counts

**Implementation:**
```python
# Execute LIMITED query (100 results)
summary_results = collection.aggregate(pipeline + [{"$limit": 100}])

# Execute COMPLETE query (10,000 results)
complete_results = collection.aggregate(pipeline + [{"$limit": 10000}])

# Execute COUNT query (actual total)
total_count = collection.aggregate(pipeline + [{"$count": "total"}])
```

**Result:**
- Chat: Shows summary (top 100) with natural language
- Technical Details: Displays ALL results (up to 10K) in modal
- Downloads: CSV/JSON contain complete data (up to 10K)
- Frontend: Shows "Total: X | Available: Y | Summary: Z"

### Why Natural Language Responses?

**Decision:** Make LLM responses engaging and conversational

**Rationale:**
-  **Engagement**: Users prefer natural, story-driven explanations
-  **Insights**: Highlighting patterns makes data more actionable
-  **Readability**: Varied sentence structure is easier to scan
-  **Brand**: Professional yet approachable tone


### Why Session Persistence?

**Decision:** Store session ID in localStorage and restore on page load

**Rationale:**
-  **Better UX**: Users don't lose their work on accidental refresh
-  **Mobile Friendly**: Survives tab switches and app minimization
-  **History Management**: Easy to browse and resume old conversations
-  **Simple Implementation**: No server-side session management needed

### Why Safety-Only Guardrails?

**Decision:** Check safety, not topics (router handles routing)

**Rationale:**
-  **Separation of Concerns**: Router decides intent, guardrails ensure safety
-  **Flexibility**: Allows both chat and data queries
-  **Clear Responsibility**: Each component has one job
-  **Better Performance**: No redundant topic validation

**Protected:**
- Harmful content, prompt injection, PII, XSS

**Allowed:**
- Greetings, help, data queries, clarifications

---

## Detailed Documentation

For in-depth information about specific system components, see the specialized documentation in the READMEs directory:

### Core Systems

**Memory Management System**
- [READMEs/MEMORY_MANAGEMENT.md](READMEs/MEMORY_MANAGEMENT.md)
- Dual memory architecture (short-term + long-term)
- MongoDB conversation history
- ChromaDB semantic search
- Context building and retrieval
- Session management

**Guardrails System**
- [READMEs/GUARDRAILS.md](READMEs/GUARDRAILS.md)
- Two-layer safety validation
- Input validation (length, harmful content, prompt injection, PII)
- Output sanitization (HTML stripping, XSS prevention)
- Pattern libraries and testing
- Performance and monitoring

**Agent Workflow System**
- [READMEs/AGENT_WORKFLOW.md](READMEs/AGENT_WORKFLOW.md)
- Multi-agent architecture with LangGraph
- Router, Data Query, and Chat agents
- State management and transitions
- Node implementation patterns
- Workflow composition and testing

**Evaluation Framework**
- [READMEs/EVALUATION.md](READMEs/EVALUATION.md)
- Unified evaluation system with 7 criteria (100-point scale)
- MLflow GenAI integration
- Custom judges and scoring
- Result analysis and visualization
- Command-line options and best practices

### Additional Resources

**Unified Evaluation Guide**
- [UNIFIED_EVALUATION.md](UNIFIED_EVALUATION.md)
- Complete unified evaluation overview
- Feature comparison with legacy systems
- Migration guide
- Example output and workflows

**MLflow Navigation**
- [MLFLOW_NAVIGATION_GUIDE.md](MLFLOW_NAVIGATION_GUIDE.md)
- Step-by-step UI navigation
- Finding artifacts and metrics
- Comparing runs

**LangGraph Tracing**
- [LANGGRAPH_TRACING_GUIDE.md](LANGGRAPH_TRACING_GUIDE.md)
- Complete LangGraph workflow visualization in MLflow
- Node-level execution tracing
- Performance analysis and debugging
- Interactive trace exploration

**Implementation Overview**
- [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)
- MLflow GenAI features summary
- Testing validation
- Quick reference

---

##  License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---


## Acknowledgments

- **LangGraph** - Multi-agent workflow orchestration
- **OpenAI** - GPT-4o-mini for query generation and explanations
- **MongoDB** - Flexible document database for procurement data
- **ChromaDB** - Efficient vector storage for semantic memory
- **FastAPI** - Modern, fast web framework
- **Sentence Transformers** - Local embedding generation

---

## Project Stats

- **Lines of Code**: ~5,100 (Python + JavaScript)
- **Agents**: 3 (Router, Data Query, Chat)
- **Query Execution**: Two-tier (limited + complete)
- **Result Limits**: 100 (summary) / 10,000 (downloads)
- **Schema Fields**: 40+ fields with enriched metadata
- **Schema Metadata**: 6 types (type, nullable, null_percentage, sample_values, description, note)
- **Memory System**: Dual (MongoDB + ChromaDB)
- **Embedding Model**: all-MiniLM-L6-v2 (384 dims)
- **LLM**: gpt-4o-mini (cost-optimized)
- **Response Style**: Natural, conversational, engaging
- **Data Tools**: CSV importer with command-line interface
- **Evaluation**: Comprehensive framework with MLflow tracking (7 criteria, 100-point scale, 53 test queries)
- **Evaluation Scoring**: 3-tier system (Query Gen 45%, Accuracy 35%, Quality 20%)
- **Auto-Generated Files**: collection_schema.json (saved on startup)

---

**Built using LangGraph, FastAPI, MongoDB, and ChromaDB**

*An intelligent multi-agent system for procurement analysis*
