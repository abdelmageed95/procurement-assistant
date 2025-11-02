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
    START([User Message]) --> Guard[Input Guardrails]

    Guard -->|Safe| Fetch[Fetch Memory]
    Guard -->|Unsafe| END[Reject]

    Fetch --> Router[Router Agent]

    Router -->|data_query| DataAgent[Data Query Agent]
    Router -->|general_chat| ChatAgent[Chat Agent]

    DataAgent --> QueryGen[Generate MongoDB Query]
    QueryGen --> Execute[Execute Query]
    Execute --> Explain[LLM Explanation]
    Explain --> MemUpdate[Memory Update]

    ChatAgent --> ChatLLM[Generate Response]
    ChatLLM --> MemUpdate

    MemUpdate --> Output[Output Guardrails]
    Output --> END([Return Response])

    style Router fill:#FFE4B5
    style DataAgent fill:#87CEEB
    style ChatAgent fill:#98FB98
    style Guard fill:#FFB6C1
    style Fetch fill:#DDA0DD
    style MemUpdate fill:#DDA0DD
    style Output fill:#FFB6C1
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
git clone https://github.com/abdelmageed95/procurement-assistant.git
cd procurement-assistant
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```


### Step 4: Set Up Environment Variables

Edit `example.env` and rename it `.env`:

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

**Option A: Automatic download and import to MongoDB**
```bash
python3 setup_dataset.py
```

**Option B: Only import if you have the csv in your data dir**
```bash
python3 import_csv_to_mongodb.py
```

### Step 6: Run the Application

```bash
python3 run_server.py
```
Access the application at: **http://localhost:8000**

### Step 7: Evaluate
```bash
python evaluate.py  

# View results
mlflow ui --port 5000
# Navigate to: http://localhost:5000
```

---

##  Usage

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

## Data Import

The project includes two methods for dataset setup and import:

### Method 1: Automated Setup (Recommended)

The `setup_dataset.py` script handles the complete dataset setup process automatically:

**Features:**
- Downloads dataset from Kaggle automatically
- Creates data directory if needed
- Extracts ZIP file
- Renames CSV file (replaces spaces with underscores)
- Imports to MongoDB with proper type conversion
- All-in-one automated process

**Quick Start:**

```bash
# Complete automated setup (recommended for first-time setup)
python setup_dataset.py

# Custom database
python setup_dataset.py --database my_db

# Remote MongoDB
python setup_dataset.py --mongo-uri mongodb://host:27017/

# Keep ZIP file after extraction
python setup_dataset.py --keep-zip

# Don't clear existing data
python setup_dataset.py --no-clear
```

**What it does:**
1. Downloads: `https://www.kaggle.com/api/v1/datasets/download/sohier/large-purchases-by-the-state-of-ca`
2. Saves to: `data/large-purchases-by-the-state-of-ca.zip`
3. Extracts ZIP file to `data/` directory
4. Renames CSV file (spaces → underscores)
5. Imports to MongoDB with proper type conversion
6. Cleans up ZIP file (optional)

**Requirements:**
- `curl` command must be installed
- Internet connection for download

### Method 2: Manual CSV Import

If you already have the CSV file, use the standalone importer:

**Quick Start:**

```bash
# Basic usage
python import_csv_to_mongodb.py data.csv

# Custom database and collection
python import_csv_to_mongodb.py data.csv --database my_db --collection orders

# Remote MongoDB
python import_csv_to_mongodb.py data.csv --mongo-uri mongodb://user:pass@host:27017/

# Custom batch size
python import_csv_to_mongodb.py data.csv --batch-size 5000

# Append to existing data (don't clear)
python import_csv_to_mongodb.py data.csv --no-clear
```

### Common Features (Both Methods)

**Data Type Conversion:**
- Dates: `"01/15/2013"` → `datetime(2013, 1, 15)`
- Currency: `"$1,234.56"` → `1234.56` (float)
- Numbers: `"123"` → `123` (int)
- Empty strings → `None` (null)

**Command-Line Arguments:**

**setup_dataset.py** (Automated):
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--data-dir` | Optional | `data` | Data directory path |
| `--mongo-uri` | Optional | `mongodb://localhost:27017/` | MongoDB URI |
| `--database` | Optional | `procurement_db` | Database name |
| `--collection` | Optional | `purchase_orders` | Collection name |
| `--batch-size` | Optional | `1000` | Batch insert size |
| `--no-clear` | Flag | False | Append mode (don't clear) |
| `--keep-zip` | Flag | False | Keep ZIP after extraction |

**import_csv_to_mongodb.py** (Manual):
| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `csv_file` | **Required** | - | Path to CSV file |
| `--mongo-uri` | Optional | `mongodb://localhost:27017/` | MongoDB URI |
| `--database` | Optional | `procurement_db` | Database name |
| `--collection` | Optional | `purchase_orders` | Collection name |
| `--batch-size` | Optional | `1000` | Batch insert size |
| `--no-clear` | Flag | False | Append mode (don't clear) |


### Help

```bash
# Automated setup help
python setup_dataset.py --help

# Manual import help
python import_csv_to_mongodb.py --help
```

---

## Evaluation Framework

The project includes a **unified evaluation framework (v2.1)** that evaluates the actual MongoDB queries generated by the system using 8 LLM-as-judge criteria with comprehensive MLflow tracking.

### **Quick Start:**

```bash
# Run evaluation
python evaluate.py --sample 5      # Test with 5 queries
python evaluate.py                 # Full evaluation (all queries)

# View results
mlflow ui --port 5000
# Navigate to: http://localhost:5000
```

### **Key Innovation: Direct Query Evaluation**

Unlike typical LLM evaluation frameworks that only assess final responses, this system evaluates the **actual MongoDB queries**:

- **Output Format**: System returns both the generated MongoDB query and the final response
- **Query Judges**: Syntax, Semantic, and Efficiency judges evaluate the MongoDB query JSON
- **Response Judges**: Data Correctness, Completeness, Natural Language, Relevance, and Formatting judges evaluate the response
- **Schema Integration**: Syntax judge receives the full MongoDB collection schema for field validation

### **Unified Evaluation System:**

The `evaluate.py` framework combines:
- **MLflow GenAI Pipeline**: Standardized `mlflow.genai.evaluate()` framework
- **8 Custom Judges**: LLM-as-judge evaluators using `mlflow.genai.make_judge()`
- **MongoDB Query Evaluation**: Judges receive and evaluate actual generated queries
- **Prompt Logging**: All system and judge prompts logged to MLflow artifacts
- **Complete Tracking**: Schema, prompts, metrics, and traces

### **Advanced Features:**

The evaluation framework includes comprehensive MLflow GenAI capabilities:

**MLflow Artifacts Structure:**
```
Artifacts/
├── mongodb_schema.json              # Complete collection schema (35 fields)
├── evaluation_criteria.json         # Full scoring system documentation
├── system_prompts/                  # All agent system prompts
│   ├── mongodb_query_agent.txt
│   ├── router_agent.txt
│   ├── chat_agent.txt
│   └── all_prompts.json
└── judge_prompts/                   # All judge evaluation prompts (5 judges)
    ├── syntax_correctness.txt       # With schema and date format rules
    ├── semantic_correctness.txt     # Query intent matching
    ├── query_efficiency.txt         # Pipeline optimization
    ├── natural_language.txt         # Response quality
    ├── relevance.txt                # Response relevance
    └── all_judges.json
```

**Clean Metrics (8 total):**
```
Individual Criteria (5):
  - syntax_correctness_out_of_35: 31.25
  - semantic_correctness_out_of_30: 27.50
  - query_efficiency_out_of_15: 13.80
  - natural_language_out_of_15: 13.60
  - relevance_out_of_5: 4.75

Category Totals (2):
  - query_generation_out_of_80: 72.55
  - response_quality_out_of_20: 18.35

Overall Score (1):
  - overall_score_out_of_100: 90.90
```

**Learn More:**
- See [READMEs/EVALUATION.md](READMEs/EVALUATION.md) for complete evaluation guide

### **Evaluation Criteria:**

The framework uses a weighted scoring system (0-100 points) across two main dimensions:

#### **1. Query Generation Quality (80%)**

| Criterion | Points | Description | Evaluation Target |
|-----------|--------|-------------|-------------------|
| **Syntax Correctness** | 35 | Valid MongoDB syntax, correct operators, valid field names (schema-checked), proper date format | MongoDB Query JSON |
| **Semantic Correctness** | 30 | Query matches user intent, correct fields/operations, proper date handling | MongoDB Query JSON |
| **Query Efficiency** | 15 | Early filters, proper $limit, index-friendly, optimal structure | MongoDB Query JSON |

#### **2. Response Quality (20%)**

| Criterion | Points | Description | Evaluation Target |
|-----------|--------|-------------|-------------------|
| **Natural Language** | 15 | Conversational, readable, professional tone | Response |
| **Relevance** | 5 | Directly addresses query, focused | Response |

### **Features:**

**LLM-as-Judge Evaluation:**
- Uses GPT-5 to evaluate all 5 criteria with detailed rationales
- Evaluates actual MongoDB queries (not just responses)
- Provides objective, consistent scoring across runs
- Includes special date format awareness (`{"__datetime__": "YYYY-MM-DD"}`)

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

1. **Metrics Tab**: All 5 evaluation criteria scores
   - `avg_score` - Overall score (0-100)
   - `success_rate` - % of successful queries
   - `avg_execution_time` - Average time per query
   - Individual criterion averages (5 criteria):
     - `syntax_correctness_out_of_35`
     - `semantic_correctness_out_of_30`
     - `query_efficiency_out_of_15`
     - `natural_language_out_of_15`
     - `relevance_out_of_5`

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
- Unified evaluation system with 5 criteria (100-point scale)
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
- **Evaluation**: Comprehensive framework with MLflow tracking (5 criteria, 100-point scale, 53 test queries)
- **Evaluation Scoring**: 2-tier system (Query Gen 80%, Response Quality 20%)
- **Auto-Generated Files**: collection_schema.json (saved on startup)

---

**Built using LangGraph, FastAPI, MongoDB, and ChromaDB**

*An intelligent multi-agent system for procurement analysis*
