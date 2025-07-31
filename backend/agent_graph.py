from typing import TypedDict, Annotated, List, Dict, Any, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
# ToolExecutor and ToolInvocation are no longer needed in newer langgraph versions
from langchain.tools import tool
from sqlalchemy import text
from database import SessionLocal, Transaction, User
import operator
import json
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize the LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Define the agent state structure
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add] # reducer function so multiple nodes can run in parallel
    query_type: str # classify as transaction, summary, or general
    sql_query: str
    query_results: List[Dict]
    analysis: str
    final_response: str

# Tool definitions - functions the agent can call
@tool
def execute_sql_query (query: str) -> List[Dict]:
    """Execute a SQL query against the database and return results."""
    
    db = SessionLocal()
    try:
        # Execute the query
        result = db.execute(text(query))

        # convert results to list of dicts
        rows = []
        for row in result:
            rows.append(dict(row._mapping))

        return rows
    except Exception as e:
        return [{"error": f"SQL Error: {str(e)}"}]
    finally:
        db.close()

@tool
def get_schema_info() -> str:
    """Get info about the database schema dynamically"""

    db = SessionLocal()
    try:
        # Get table info from sqlite metadata
        tables_query = """
        SELECT name, sql
        FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name;
        """

        tables_result = db.execute(text(tables_query))

        schema_info = "Database Schema (dynamically retrieved): \n\n"

        for table_row in tables_result:
            table_name = table_row[0] # Avi: IS THIS RETRIEVING THE RIGHT TABLE NAME????
            create_sql = table_row[1]

            schema_info += f"Table: {table_name}\n"
            schema_info += f"Create Statement: {create_sql}\n"

            # Get detailed colun info using PRAGMA
            columns_query = f"PRAGMA table_info({table_name});"
            columns_result = db.execute(text(columns_query))

            schema_info += "Columns:\n"
            for col in columns_result:
                # PRAGMA returns: (cid, name, type, notnull, dflt_value, pk)
                col_name = col[1]
                col_type = col[2]
                is_nullable = "NOT NULL" if col[3] else "NULL"
                is_pk = "PRIMARY KEY" if col[5] else ""

                schema_info += f" - {col_name}: {col_type} {is_nullable} {is_pk}\n"

            # Get foreign key information
            fk_query = f"PRAGMA foreign_key_list({table_name});"
            fk_result = db.execute(text(fk_query))
            fk_list = list(fk_result)

            if fk_list:
                schema_info += "Foreign Keys:\n"
                for fk in fk_list:
                    # PRAGMA returns: (id, seq, table, from, to, on_update, on_delete, match)
                    schema_info += f" - {fk[3]} -> {fk[2]}.{fk[4]}\n"
                
            schema_info += "\n"

        # Add helpful context for the LLM
        schema_info += """
Additional Context:
- For demo purposes, use user_id = 1 or email = 'demo@example.com'
- In the transactions table:
  - amount is FLOAT (positive values, expenses and income both positive)
  - date is stored as DATETIME
  - category is stored as JSON (array of category strings)
  - name contains the transaction description/merchant
"""

        return schema_info

    except Exception as e:
        return f"Error retrieving schema: {str(e)}"
    finally:
        db.close()

@tool
def calculate_summary(data: List[dict], summary_type: str) -> Dict:
    """Calculate summaries and aggregations on transaciton data"""

    if not data or "error" in data[0]:
        return {"error": "No valid data to summarize"}
    
    # Convert to pandas df for easier analysis
    df = pd.DataFrame(data)

    if summary_type == "category breakdown":
        # Group by category and sum amounts
        if 'category' in df.columns:
            # Parse JSON category field
            categories = []
            for cats in df['category']:
                if isinstance(cats, str):
                    cats = json.loads(cats)
                if cats:
                    categories.extend(cats)
            
            category_counts = pd.Series(categories).value_counts().to_dict()
            return{"category_breakdown": category_counts}
    
    elif summary_type == "monthly_trend":
        # Group by month
        df['date'] = pd.to_datetime(df['date'])
        df['month'] = df['date'].dt.to_period('M')
        monthly = df.groupby('month')['amount'].sum().to_dict()
        # Convert period objects to strings
        monthly_str = {str(k): v for k, v in monthly.items()}
        return {"monthly_trend": monthly_str}

    return {"error": "Unknown summary type"}

# Node functions - these get called when establishing the graph itself
def classify_query(state: AgentState) -> AgentState:
    """Node 1: Classify the user's query to determine how to handle it."""
    messages = state["messages"]
    last_message = messages[-1].content

    # Prompt fed into LLM call to categorize - this is just an fstring
    classification_prompt = f"""
    Classify this user query into one of these categories:
    - "transaction": Questions about specific transactions, spending, or financial data
    - "summary": Questions asking for aggregations, trends, or analysis
    - "general": General conversation, greetings, or non-financial questions
    
    User query: "{last_message}"
    
    Respond with just the category name.
    """

    response = llm.invoke([HumanMessage(content=classification_prompt)])
    query_type = response.content.strip().lower()

    # Validate the classification
    if query_type not in ["transaction", "summary", "general"]:
        query_type = "general"
    
    # Output from this node is just the query_type from state object
    state["query_type"] = query_type
    return state

def analyze_transactions(state: AgentState) -> AgentState:
    """Node 2a: Generate and execute SQL queries for transaction data"""
    messages = state["messages"]
    last_message = messages[-1].content

    # Get schema info - invoke function defined earlier
    schema = get_schema_info.invoke({})

    # Generate SQL Query
    sql_prompt = f"""
    {schema}
    
    User query: "{last_message}"
    
    Generate a SQL query to answer this question. 
    Important notes:
    - Use user_id = 1 for the demo user
    - date is in DATETIME format
    - category is stored as JSON array
    - ensure all SQL is SQLite3 compatible
    
    FLEXIBLE MATCHING GUIDELINES:
    - For merchant/store names: Use LIKE with % wildcards for partial matching
      Example: For "walmart", use "name LIKE '%walmart%' OR name LIKE '%wal-mart%'"
    - For categories: Use JSON_EXTRACT or check if category array contains similar terms
      Example: For "restaurants", check for "food", "dining", "restaurant", etc.
    - Be case-insensitive: Use LOWER() function on both sides
    - Consider common variations and abbreviations

    FOR CATEGORY SEARCHES:
    - WRONG: JSON_EXTRACT(category, '$[*]') - wildcards not supported
    - RIGHT: Use simple LIKE on the category column: category LIKE '%Food%'
    - OR use JSON_EACH: FROM transactions t, JSON_EACH(t.category) je WHERE je.value LIKE '%Food%'
    
    CATEGORY MAPPINGS (use these when user asks about broad categories):
    - "restaurants/dining/food" → check for: 'Food and Drink', 'Restaurants', 'Fast Food', 'Coffee'
    - "shopping/retail" → check for: 'Shops', 'General Merchandise', 'Clothing', 'Department Stores'
    - "gas/fuel" → check for: 'Gas Stations', 'Transportation'
    - "groceries" → check for: 'Grocery', 'Supermarkets'
    - "entertainment" → check for: 'Entertainment', 'Recreation'
    
    Return ONLY the SQL query, no explanation.
    """

    sql_response = llm.invoke([HumanMessage(content=sql_prompt)])
    sql_query = sql_response.content.strip()

    # Remove any markdown formatting if present
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

    state["sql_query"] = sql_query
    print(sql_query) # LOGGING

    # Execute the query, write results to state
    results = execute_sql_query.invoke({"query": sql_query})
    state["query_results"] = results

    return state

def generate_insights(state: AgentState) -> AgentState:
    """Node 3: Analyze query results and generate insights, add context, identify patterns, make data meaningful"""

    results = state["query_results"]
    query = state["messages"][-1].content

    if not results or "error" in results[0]:
        state["analysis"] = "I couldn't retrieve the data. Let me try a different approach."
        return state
    
    # Create analysis prompt - AVI: CHANGED TO 50 ROWS VS 10
    analysis_prompt = f"""
    User asked: "{query}"
    
    Query results: {json.dumps(results[:50], default=str)}  # Limit to first 50 rows
    Total results: {len(results)} rows
    
    Provide a brief, insightful analysis of this data. Focus on:
    - Direct answer to the user's question
    - Key patterns or trends
    - Actionable insights if applicable
    
    Keep it conversational and helpful.
    """

    # Invoke llm with analysis prompt, write results to state
    analysis_response = llm.invoke([HumanMessage(content=analysis_prompt)])
    state["analysis"] = analysis_response.content

    return state

def general_chat(state: AgentState) -> AgentState:
    """Node 2b: Handle general conversation w/out database access."""

    messages = state["messages"]

    # Add system context about being a financial assistant
    system_prompt = """You are PennyWise, a friendly financial assistant. 
    While the user isn't asking about specific transactions right now, 
    you can still provide general financial advice and maintain a helpful conversation.
    Keep responses concise and friendly."""

    response = llm.invoke([
        HumanMessage(content=system_prompt),
        *messages
    ])

    state["final_response"] = response.content
    return state

def format_response(state: AgentState) -> AgentState:
    """Node 4: Format the final response for the user"""

    # Skip if we already have a final response from general chat
    if state.get("final_response"):
        return state
    
    # Format transaction / summary responses
    if state["query_type"] in ["transaction", "summary"]:
        analysis = state.get("analysis", "")
        results = state.get("query_results", [])

        # Add data summary if we have results
        if results and "error" not in results[0]:
            response = f"{analysis}\n\n"

            # Add a sample of the data if its not too large
            if len(results) <= 5:
                response += "Here's the data I found:\n"
                for row in results:
                    # Format each row nicely
                    if 'name' in row and 'amount' in row and 'date' in row:
                        date_str = row['date'].split('T')[0] if 'T' in str(row['date']) else row['date']
                        amount_str = f"${abs(row['amount']):.2f}"
                        type_str = "spent" if row['amount'] < 0 else "received"
                        response += f"- {date_str}: {row['name']} - {amount_str} {type_str}\n"
            elif len(results) > 5:
                response += f"\n(Showing analysis of {len(results)} transactions)"
        
        else:
            response = analysis

        state["final_response"] = response
    
    return state

# Define routing logic
def route_after_classification(state: AgentState) -> Literal["analyze_transactions", "general_chat"]:
    """Routing function: Decides which node to go to after classification."""

    query_type = state["query_type"]

    if query_type in ["transaction", "summary"]:
        return "analyze_transactions"
    else:
        return "general_chat"

# Build the graph!!!!
def create_agent_graph():
    """Create and compile the LangGraph agent."""

    # Initialize the graph with our state type
    graph = StateGraph(AgentState)

    # Add nodes to the graph
    graph.add_node("classify_query", classify_query)
    graph.add_node("analyze_transactions", analyze_transactions)
    graph.add_node("generate_insights", generate_insights)
    graph.add_node("general_chat", general_chat)
    graph.add_node("format_response", format_response)

    # Define the edges b/w nodes
    graph.set_entry_point("classify_query")

    # Conditional routing after classification
    graph.add_conditional_edges(
        "classify_query",
        route_after_classification,
        {
            "analyze_transactions": "analyze_transactions",
            "general_chat": "general_chat"
        }
    )

    # Linear flow for transaction path
    graph.add_edge("analyze_transactions", "generate_insights")
    graph.add_edge("generate_insights", "format_response")

    # General chat goes straight to response formatting
    graph.add_edge("general_chat", "format_response")

    # All paths end at format_response
    graph.add_edge("format_response", END)

    # Compile the graph
    return graph.compile()

# Create a single instance of the agent
agent = create_agent_graph()

# Helper function for easy invocation
async def process_query(user_query: str, conversation_history: List[Dict] = None):
    """
    Process a user query through the agent.

    Args:
        user_query: The user's natural language query
        conversation_history: Previous messages in the conversation

    Returns:
        The agent's response as a string
    """
    # Build message history
    messages = []
    if conversation_history:
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

    # Add current query
    messages.append(HumanMessage(content=user_query))

    # Create initial state
    initial_state = {
        "messages": messages,
        "query_type": "",
        "sql_query": "",
        "query_results": [],
        "analysis": "",
        "final_response": ""
    }

    # Run the agent!!
    result = await agent.ainvoke(initial_state)

    return result["final_response"]