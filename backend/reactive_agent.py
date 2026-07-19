import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models import AgentRun
from backend.llm import anthropic_client, openai_client, call_llm
from backend.config import GROQ_MODEL
from backend import tools

logger = logging.getLogger(__name__)

# Standard Tool Definitions
TOOL_SCHEMAS = [
    {
        "name": "get_inventory_status",
        "description": "Get inventory stock levels, daily demand, safety stock, lead time, and calculated stockout risk level for SKUs.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku_query": {
                    "type": "string",
                    "description": "Optional search term to filter SKUs by name (e.g. 'MCU')."
                }
            }
        }
    },
    {
        "name": "get_supplier_risk",
        "description": "Get supplier categories, geopolitical/financial risks, and composite safety risk scores.",
        "parameters": {
            "type": "object",
            "properties": {
                "supplier_query": {
                    "type": "string",
                    "description": "Optional search term to filter suppliers by name."
                }
            }
        }
    },
    {
        "name": "get_shipment_delays",
        "description": "Get active shipments that are delayed or overdue, along with the calculated delay stockout impact on warehouses.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "recommend_warehouse",
        "description": "Recommend which warehouse is best suited to receive/route a new SKU shipment of a given quantity based on available capacity.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku_id_or_name": {
                    "type": "string",
                    "description": "The SKU ID or name being shipped."
                },
                "quantity": {
                    "type": "integer",
                    "description": "Quantity of units in the shipment."
                }
            },
            "required": ["sku_id_or_name", "quantity"]
        }
    },
    {
        "name": "get_top_risks",
        "description": "Get a unified list of the top risk items across inventory stockouts, supplier warnings, and shipment delays, prioritized by severity.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max number of risks to return. Defaults to 5."
                }
            }
        }
    },
    {
        "name": "suggest_alternate_supplier",
        "description": "Find alternative suppliers of the same category for a given SKU, sorted by lowest risk score (safest supplier first).",
        "parameters": {
            "type": "object",
            "properties": {
                "sku_id_or_name": {
                    "type": "string",
                    "description": "The SKU ID or name to find alternate suppliers for."
                }
            },
            "required": ["sku_id_or_name"]
        }
    }
]

SYSTEM_PROMPT = """You are a highly analytical, reactive AI Supply Chain Agent.
Your goal is to answer supply chain, inventory, and supplier operations questions by executing database-backed query tools.

You MUST follow these rules:
1. NEVER guess or make up figures. Always call the appropriate tool to retrieve live, real-time database details.
2. If the user asks a question, call the tool(s) first to query the database. Only answer the question once you have evaluated the tool outputs.
3. Be precise, citing real numbers, supplier names, SKU codes, and warehouse locations returned by the tools.
4. Keep your responses structured, clear, and action-oriented.
"""

def execute_tool_by_name(db: Session, name: str, args: dict) -> str:
    """Helper to dispatch tool arguments to real Python handlers in tools.py."""
    logger.info(f"Executing local Python tool: {name} with arguments: {args}")
    if args is None or not isinstance(args, dict):
        args = {}
    try:
        if name == "get_inventory_status":
            res = tools.get_inventory_status(db, sku_query=args.get("sku_query"))
        elif name == "get_supplier_risk":
            res = tools.get_supplier_risk(db, supplier_query=args.get("supplier_query"))
        elif name == "get_shipment_delays":
            res = tools.get_shipment_delays(db)
        elif name == "recommend_warehouse":
            res = tools.recommend_warehouse(db, sku_id_or_name=args.get("sku_id_or_name"), quantity=args.get("quantity"))
        elif name == "get_top_risks":
            res = tools.get_top_risks(db, limit=args.get("limit", 5))
        elif name == "suggest_alternate_supplier":
            res = tools.suggest_alternate_supplier(db, sku_id_or_name=args.get("sku_id_or_name"))
        else:
            return f"Error: Tool '{name}' is not defined."
            
        return json.dumps(res)
    except Exception as e:
        logger.exception(f"Error executing tool {name}")
        return f"Error executing tool {name}: {str(e)}"


async def run_reactive_agent(db: Session, question: str) -> dict:
    """
    Hand-rolled multi-turn tool-use loop:
    1. Saves reactive run.
    2. Runs up to 5 loop turns.
    3. Handles Claude tool blocks or OpenAI tool_calls.
    4. Traces thoughts and outputs.
    """
    run = AgentRun(
        run_type="reactive",
        status="running",
        started_at=datetime.utcnow(),
        summary=f"User Question: {question}"
    )
    db.add(run)
    db.commit()

    steps = []
    max_turns = 5
    turn = 0
    final_answer = ""
    
    # Check model provider
    is_claude = (anthropic_client is not None)
    
    # Initialize message list
    if is_claude:
        # Claude format
        claude_messages = [{"role": "user", "content": question}]
        claude_tools = []
        for schema in TOOL_SCHEMAS:
            claude_tools.append({
                "name": schema["name"],
                "description": schema["description"],
                "input_schema": schema["parameters"]
            })
    else:
        # OpenAI/Groq format
        openai_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ]
        openai_tools = []
        for schema in TOOL_SCHEMAS:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema["parameters"]
                }
            })

    while turn < max_turns:
        turn += 1
        logger.info(f"Reactive agent loop turn {turn}/{max_turns}")
        
        if is_claude:
            # ── CLAUDE TURN ──
            try:
                response = await anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2000,
                    system=SYSTEM_PROMPT,
                    tools=claude_tools,
                    messages=claude_messages
                )
                
                # Capture assistant content
                assistant_blocks = []
                tool_calls_detected = []
                
                for block in response.content:
                    if block.type == "text":
                        assistant_blocks.append(block.text)
                        steps.append({"role": "thought", "content": block.text})
                    elif block.type == "tool_use":
                        tool_calls_detected.append({
                            "id": block.id,
                            "name": block.name,
                            "args": block.input
                        })
                        steps.append({
                            "role": "tool_call",
                            "content": f"Call tool '{block.name}' with args: {block.input}"
                        })

                # Append assistant response to messages history
                claude_messages.append({"role": "assistant", "content": response.content})

                if not tool_calls_detected:
                    # Final text response is the answer
                    final_answer = "\n".join(assistant_blocks)
                    break

                # Execute tool calls and append response blocks
                tool_response_content = []
                for tc in tool_calls_detected:
                    tool_result_str = execute_tool_by_name(db, tc["name"], tc["args"])
                    steps.append({
                        "role": "tool_result",
                        "content": f"Tool '{tc['name']}' returned: {tool_result_str}"
                    })
                    tool_response_content.append({
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": tool_result_str
                    })
                
                # Append user tool_result block
                claude_messages.append({"role": "user", "content": tool_response_content})

            except Exception as e:
                logger.error(f"Claude agent turn failed: {e}")
                raise e
        else:
            # ── GROQ / OPENAI TURN ──
            try:
                response = await openai_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=openai_messages,
                    tools=openai_tools,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=2000
                )
                
                msg = response.choices[0].message
                openai_messages.append(msg)
                
                if msg.content:
                    steps.append({"role": "thought", "content": msg.content})
                    final_answer = msg.content

                if not msg.tool_calls:
                    # No tool calls generated, this is the terminal turn!
                    break

                # Execute tool calls
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    steps.append({
                        "role": "tool_call",
                        "content": f"Call tool '{name}' with args: {args}"
                    })
                    
                    # Execute database lookup
                    tool_result_str = execute_tool_by_name(db, name, args)
                    
                    steps.append({
                        "role": "tool_result",
                        "content": f"Tool '{name}' returned: {tool_result_str}"
                    })
                    
                    # Append result to message history
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": tool_result_str
                    })

            except Exception as e:
                logger.error(f"Groq agent turn failed: {e}")
                raise e

    if not final_answer:
        final_answer = "Error: Reactive agent reached maximum execution turns without generating a response."
        
    # Update Run database entry
    run.status = "success"
    run.completed_at = datetime.utcnow()
    run.summary = f"Question: {question}\nAnswer: {final_answer}"
    db.commit()

    return {
        "run_id": run.id,
        "answer": final_answer,
        "steps": steps
    }
