import getpass
import os
from pathlib import Path

# Load environment variables from .env file if it exists
from dotenv import load_dotenv
load_dotenv()


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("OPENAI_API_KEY")

from typing import Annotated, TypedDict

try:
    from langgraph.graph.message import AnyMessage, add_messages
except ImportError:
    # Fallback for older versions
    AnyMessage = str
    def add_messages(a, b):
        return a + b

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# Use OpenAI with Hackathon API
from langchain_openai import ChatOpenAI
from tools import (
    consult_policy,
    frequent_questions,
    db_get,
    check_server_health,
    get_stats,
    calculate_price,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from datetime import datetime
from pathlib import Path

# Load system prompt from file
SYSTEM_PROMPT_PATH = Path(__file__).parent / "config" / "system_prompt.txt"
EXAMPLES_PATH = Path(__file__).parent / "EXAMPLES.md"

def load_system_prompt() -> str:
    """Load the system prompt from config/system_prompt.txt"""
    try:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: System prompt file not found at {SYSTEM_PROMPT_PATH}")
        return "You are a helpful AI assistant for Palace Resorts call center."

def load_examples() -> str:
    """Load examples from EXAMPLES.md"""
    try:
        with open(EXAMPLES_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Examples file not found at {EXAMPLES_PATH}")
        return ""

# Load the prompts and examples
SYSTEM_PROMPT = load_system_prompt()
EXAMPLES = load_examples()

class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            configuration = config.get("configurable", {})
            customer_info = configuration.get("customer_info", None)
            agent_info = configuration.get("agent_info", None)
            
            # Build user context
            user_context = self._build_user_context(customer_info, agent_info)
            state = {**state, "user_info": user_context}
            
            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}
    
    def _build_user_context(self, customer_info: dict, agent_info: dict) -> str:
        """Build formatted user context from customer and agent information"""
        context_parts = []
        
        if customer_info:
            context_parts.append("CUSTOMER INFORMATION:")
            for key, value in customer_info.items():
                if value:
                    context_parts.append(f"  {key}: {value}")
        
        if agent_info:
            context_parts.append("\nAGENT INFORMATION:")
            for key, value in agent_info.items():
                if value:
                    context_parts.append(f"  {key}: {value}")
        
        return "\n".join(context_parts) if context_parts else "No user information available"


# Using OpenAI with Hackathon API endpoint
# The hackathon API requires a custom header "api-key" instead of "Authorization"
openai_endpoint = os.getenv("OPENAI_ENDPOINT", "https://api.hicap.ai/v2/openai")
openai_api_key = os.getenv("OPENAI_API_KEY")

# Create ChatOpenAI with custom headers for hackathon API
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7,
    base_url=openai_endpoint,
    api_key=openai_api_key,
    default_headers={"api-key": openai_api_key}
)

# Build the primary assistant prompt with loaded system prompt and examples
primary_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "{system_prompt}"
            "\n\n--- EXAMPLES FOR REFERENCE ---\n"
            "{examples}"
            "\n\n--- CURRENT CONTEXT ---"
            "\nCurrent user:\n<User>\n{user_info}\n</User>"
            "\nCurrent time: {time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(
    system_prompt=SYSTEM_PROMPT,
    examples=EXAMPLES,
    time=datetime.now
)

# Define tools for Palace Resorts operations
part_1_tools = [
    # Policy/FAQ helpers
    consult_policy,
    frequent_questions,
    # Backend API wrappers
    db_get,
    check_server_health,
    get_stats,
    calculate_price,
    # TODO: add booking, update, cancel tools when implemented
    # book_reservation,
    # update_reservation,
    # cancel_reservation,
]
part_1_assistant_runnable = primary_assistant_prompt | llm.bind_tools(part_1_tools)


# Import LangGraph components
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import tools_condition, ToolNode

# Remove IPython dependency (not needed)
# from IPython.display import Image, display

builder = StateGraph(State)

# Define nodes: these do the work
builder.add_node("assistant", Assistant(part_1_assistant_runnable))
builder.add_node("tools", ToolNode(part_1_tools))
# Define edges: these determine how the control flow moves
builder.add_edge(START, "assistant")
builder.add_conditional_edges(
    "assistant",
    tools_condition,
)
builder.add_edge("tools", "assistant")

# The checkpointer lets the graph persist its state
# this is a complete memory for the entire graph.
memory = InMemorySaver()
part_1_graph = builder.compile(checkpointer=memory)

# Example usage function
def run_agent(call_transcription: str, customer_info: dict = None, agent_info: dict = None):
    """
    Run the AI Copilot agent with call transcription and context.
    
    Args:
        call_transcription: The live transcription of the customer call
        customer_info: Dictionary with customer details (name, age, dates, etc.)
        agent_info: Dictionary with agent details (name, id, etc.)
    
    Example:
        customer_info = {
            "name": "Maria Rodriguez",
            "age": 35,
            "party_size": "2 adults",
            "travel_purpose": "10th Anniversary celebration",
            "check_in": "October 21, 2025",
            "check_out": "October 25, 2025",
            "dietary_restrictions": "Vegetarian"
        }
        
        agent_info = {
            "name": "Sarah Johnson",
            "id": "AGT-001"
        }
        
        response = run_agent(
            call_transcription="Hi, I'm looking to book a room for my anniversary...",
            customer_info=customer_info,
            agent_info=agent_info
        )
    """
    config = {
        "configurable": {
            "customer_info": customer_info or {},
            "agent_info": agent_info or {},
            "thread_id": "1",
        }
    }
    
    # Create initial state with the call transcription
    input_message = {
        "messages": [("user", call_transcription)]
    }
    
    # Use the full graph
    result = part_1_graph.invoke(input_message, config)
    return result


if __name__ == "__main__":
    # Test the agent with example data
    test_customer_info = {
        "name": "Maria Rodriguez",
        "age": 35,
        "party_size": "2 adults",
        "travel_purpose": "10th Anniversary + Birthday celebration",
        "check_in": "October 21, 2025",
        "check_out": "October 25, 2025",
        "nights": 4,
        "room_preference": "Ocean view",
        "dietary_restrictions": "Vegetarian (both guests)"
    }
    
    test_agent_info = {
        "name": "Sarah Johnson",
        "id": "AGT-001",
        "location": "Cancun Call Center"
    }
    
    test_call = """
    Hi, yes, I'm Maria Rodriguez. I'm looking to book a room for my husband and me. 
    We're celebrating our 10th wedding anniversary next month on October 21st through the 25th.
    I'm turning 35 that week too, so it's a double celebration! 
    We're looking for something romantic with an ocean view if possible. We're vegetarians, by the way.
    """
    
    print("Testing AI Copilot Agent...")
    print("=" * 80)
    response = run_agent(test_call, test_customer_info, test_agent_info)
    print("\nAgent Response:")
    print(response)