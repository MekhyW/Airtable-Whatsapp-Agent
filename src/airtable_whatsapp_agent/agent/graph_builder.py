"""
LangGraph builder for the autonomous agent.
Creates and configures the agent workflow graph.
"""

import logging
from typing import Any, Dict, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from .state_manager import StateManager, AgentGraphState
from .tool_registry import ToolRegistry
from ..models.agent import AgentState, AgentDecision, AgentAction
from ..auth.authenticator import Authenticator


logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds and configures the LangGraph workflow for the autonomous agent."""
    
    def __init__(
        self,
        state_manager: StateManager,
        tool_registry: ToolRegistry,
        authenticator: Authenticator,
        openai_api_key: str,
        model_name: str = "gpt-4-turbo-preview"
    ):
        """Initialize graph builder."""
        self.logger = logging.getLogger(__name__)
        self.state_manager = state_manager
        self.tool_registry = tool_registry
        self.authenticator = authenticator
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model_name,
            temperature=0.5,
            max_tokens=2000
        )
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentGraphState)
        workflow.add_node("authenticate", self._authenticate_node)
        workflow.add_node("analyze_input", self._analyze_input_node)
        workflow.add_node("make_decision", self._make_decision_node)
        workflow.add_node("execute_action", self._execute_action_node)
        workflow.add_node("handle_error", self._handle_error_node)
        workflow.add_node("generate_response", self._generate_response_node)
        workflow.set_entry_point("authenticate")
        workflow.add_conditional_edges(
            "authenticate",
            self._should_continue_after_auth,
            {
                "analyze": "analyze_input",
                "error": "handle_error",
                "end": END
            }
        )
        workflow.add_conditional_edges(
            "analyze_input",
            self._should_continue_after_analysis,
            {
                "decide": "make_decision",
                "error": "handle_error",
                "respond": "generate_response"
            }
        )
        workflow.add_conditional_edges(
            "make_decision",
            self._should_continue_after_decision,
            {
                "execute": "execute_action",
                "respond": "generate_response",
                "error": "handle_error"
            }
        )
        workflow.add_conditional_edges(
            "execute_action",
            self._should_continue_after_execution,
            {
                "decide": "make_decision",
                "respond": "generate_response",
                "error": "handle_error",
                "end": END
            }
        )
        workflow.add_conditional_edges(
            "handle_error",
            self._should_continue_after_error,
            {
                "retry": "analyze_input",
                "respond": "generate_response",
                "end": END
            }
        )
        workflow.add_edge("generate_response", END)
        return workflow.compile()
        
    async def _authenticate_node(self, state: AgentGraphState) -> AgentGraphState:
        """Authentication node."""
        self.logger.info(f"Authenticating user: {state['user_phone']}")
        try:
            is_authenticated = await self.authenticator.authenticate_user(state["user_phone"])
            if is_authenticated:
                permissions = await self.authenticator.get_user_permissions(state["user_phone"])
                state["available_tools"] = [tool.name for tool in self.tool_registry.get_available_tools(permissions)]
                state["metadata"]["permissions"] = permissions
                state["current_state"] = AgentState.PROCESSING
                self.logger.info(f"User authenticated with {len(permissions)} permissions")
            else:
                state["current_state"] = AgentState.ERROR
                state["last_error"] = "Authentication failed"
        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            state["current_state"] = AgentState.ERROR
            state["last_error"] = str(e)
        return state
        
    async def _analyze_input_node(self, state: AgentGraphState) -> AgentGraphState:
        """Analyze user input node."""
        self.logger.info("Analyzing user input")
        try:
            if not state["current_message"]:
                state["last_error"] = "No message to analyze"
                return state
            analysis_prompt = self._create_analysis_prompt(state)
            response = await self.llm.ainvoke(analysis_prompt)
            analysis = self._parse_analysis_response(response.content)
            state["metadata"]["analysis"] = analysis
            state["current_state"] = AgentState.PROCESSING
            self.state_manager.add_message_to_history(state["session_id"], state["current_message"], "user", state.get("message_type", "text"))
        except Exception as e:
            self.logger.error(f"Analysis error: {str(e)}")
            state["current_state"] = AgentState.ERROR
            state["last_error"] = str(e) 
        return state
        
    async def _make_decision_node(self, state: AgentGraphState) -> AgentGraphState:
        """Decision making node."""
        self.logger.info("Making decision")
        try:
            decision_prompt = self._create_decision_prompt(state)
            available_tools = self.tool_registry.get_all_tool_schemas(state["metadata"].get("permissions", []))
            if available_tools:
                response = await self.llm.ainvoke(decision_prompt, functions=available_tools)
            else:
                response = await self.llm.ainvoke(decision_prompt)
            decision = self._parse_decision_response(response, state)
            self.state_manager.record_decision(state["session_id"], decision)
            state["last_decision"] = decision
            for action in decision.actions:
                self.state_manager.add_pending_action(state["session_id"], action)
        except Exception as e:
            self.logger.error(f"Decision error: {str(e)}")
            state["current_state"] = AgentState.ERROR
            state["last_error"] = str(e)
        return state
        
    async def _execute_action_node(self, state: AgentGraphState) -> AgentGraphState:
        """Action execution node."""
        self.logger.info("Executing action")
        try:
            action = self.state_manager.get_next_action(state["session_id"])
            if not action:
                return state
            state["current_state"] = AgentState.EXECUTING_TASK
            if action.action_type == "tool_call":
                result = await self.tool_registry.execute_tool(action.tool_name, action.parameters, state["metadata"].get("permissions", []))
                self.state_manager.record_tool_result(state["session_id"], action.tool_name, result.result, result.success)
                if not result.success:
                    state["current_state"] = AgentState.ERROR
                    state["last_error"] = result.error
            elif action.action_type == "send_message":
                state["metadata"]["response_message"] = action.parameters.get("message")
            elif action.action_type == "wait_for_input":
                state["current_state"] = AgentState.WAITING_FOR_INPUT
        except Exception as e:
            self.logger.error(f"Execution error: {str(e)}")
            state["current_state"] = AgentState.ERROR
            state["last_error"] = str(e)
        return state
        
    async def _handle_error_node(self, state: AgentGraphState) -> AgentGraphState:
        """Error handling node."""
        self.logger.info(f"Handling error: {state.get('last_error')}")
        try:
            error_count = state["error_count"]
            if error_count < 3:  # Retry up to 3 times
                recovery_prompt = self._create_error_recovery_prompt(state)
                response = await self.llm.ainvoke(recovery_prompt)
                recovery = self._parse_recovery_response(response.content)
                if recovery.get("should_retry", False):
                    state["current_state"] = AgentState.PROCESSING
                    state["metadata"]["recovery_strategy"] = recovery
                else:
                    state["metadata"]["response_message"] = recovery.get("error_message", "I encountered an error and cannot complete this request.")
            else:
                # Too many errors, give up
                state["metadata"]["response_message"] = ("I'm experiencing technical difficulties. " "Please try again later or contact support.")
        except Exception as e:
            self.logger.error(f"Error handling failed: {str(e)}")
            state["metadata"]["response_message"] = ("I'm experiencing technical difficulties. " "Please try again later.")
        return state
        
    async def _generate_response_node(self, state: AgentGraphState) -> AgentGraphState:
        """Response generation node."""
        self.logger.info("Generating response")
        try:
            if "response_message" in state["metadata"]:
                response_text = state["metadata"]["response_message"]
            else:
                response_prompt = self._create_response_prompt(state)
                response = await self.llm.ainvoke(response_prompt)
                response_text = response.content
            self.state_manager.add_message_to_history(state["session_id"], response_text, "assistant", "text")
            state["metadata"]["final_response"] = response_text
            state["current_state"] = AgentState.IDLE
            
        except Exception as e:
            self.logger.error(f"Response generation error: {str(e)}")
            state["metadata"]["final_response"] = ("I apologize, but I'm having trouble generating a response. " "Please try again.")
        return state

    def _should_continue_after_auth(self, state: AgentGraphState) -> str:
        """Determine next step after authentication."""
        if state["current_state"] == AgentState.ERROR:
            return "error"
        elif state["current_message"]:
            return "analyze"
        else:
            return "end"
            
    def _should_continue_after_analysis(self, state: AgentGraphState) -> str:
        """Determine next step after input analysis."""
        if state["current_state"] == AgentState.ERROR:
            return "error"
        elif state["metadata"].get("analysis", {}).get("requires_action", False):
            return "decide"
        else:
            return "respond"
            
    def _should_continue_after_decision(self, state: AgentGraphState) -> str:
        """Determine next step after decision making."""
        if state["current_state"] == AgentState.ERROR:
            return "error"
        elif state["pending_actions"]:
            return "execute"
        else:
            return "respond"
            
    def _should_continue_after_execution(self, state: AgentGraphState) -> str:
        """Determine next step after action execution."""
        if state["current_state"] == AgentState.ERROR:
            return "error"
        elif state["pending_actions"]:
            return "execute"  # More actions to execute
        elif state["current_state"] == AgentState.WAITING_FOR_INPUT:
            return "end"  # Wait for user input
        else:
            return "respond"
            
    def _should_continue_after_error(self, state: AgentGraphState) -> str:
        """Determine next step after error handling."""
        if state["error_count"] < 3 and state["metadata"].get("recovery_strategy", {}).get("should_retry", False):
            return "retry"
        elif "response_message" in state["metadata"]:
            return "respond"
        else:
            return "end"

    def _create_analysis_prompt(self, state: AgentGraphState) -> List:
        """Create prompt for input analysis."""
        system_message = SystemMessage(content="""
You are an AI assistant that analyzes user messages to understand intent and determine if actions are needed.

Analyze the user's message and respond with a JSON object containing:
- intent: The user's primary intent (question, request, command, etc.)
- entities: Any important entities mentioned (names, dates, numbers, etc.)
- requires_action: Boolean indicating if this requires tool usage or actions
- urgency: Low, medium, or high
- context_needed: Any additional context that might be needed

Be concise and accurate in your analysis.
""")
        history = state["conversation_history"][-5:]  # Last 5 messages
        context = "\n".join([f"{msg['sender']}: {msg['message']}" for msg in history])
        human_message = HumanMessage(content=f"""
Current message: {state['current_message']}

Recent conversation:
{context}

Available tools: {', '.join(state['available_tools'])}

Please analyze this message.
""")
        return [system_message, human_message]
        
    def _create_decision_prompt(self, state: AgentGraphState) -> List:
        """Create prompt for decision making."""
        system_message = SystemMessage(content="""
You are an autonomous AI agent that makes decisions about what actions to take based on user requests.

You have access to various tools for:
- Managing Airtable records (contacts, projects, tasks)
- Sending WhatsApp messages and media
- Scheduling tasks
- Utility functions

Based on the user's message and analysis, decide what actions to take. You can:
1. Use tools to retrieve or modify data
2. Send messages or notifications
3. Schedule tasks
4. Ask for clarification

Always prioritize user safety and data privacy. Only perform actions that are clearly requested or necessary.
""")
        analysis = state["metadata"].get("analysis", {})
        human_message = HumanMessage(content=f"""
User message: {state['current_message']}
Analysis: {analysis}
Available tools: {state['available_tools']}

What actions should I take? Use function calls if tools are needed, or explain your reasoning.
""")
        return [system_message, human_message]
        
    def _create_error_recovery_prompt(self, state: AgentGraphState) -> List:
        """Create prompt for error recovery."""
        system_message = SystemMessage(content="""
You are helping recover from an error. Analyze the error and determine the best recovery strategy.

Respond with JSON containing:
- should_retry: Boolean indicating if we should retry
- error_message: User-friendly error message
- suggested_action: What the user should do
""")
        human_message = HumanMessage(content=f"""
Error: {state['last_error']}
Error count: {state['error_count']}
Last action: {state.get('last_decision')}

How should we recover from this error?
""")
        return [system_message, human_message]
        
    def _create_response_prompt(self, state: AgentGraphState) -> List:
        """Create prompt for response generation."""
        system_message = SystemMessage(content="""
Generate a helpful, friendly response to the user based on the conversation and any actions taken.

Be concise, clear, and professional. If actions were taken, summarize what was done.
If information was retrieved, present it in a useful format.
""")
        tool_results = state.get("tool_results", {})
        last_decision = state.get("last_decision")
        human_message = HumanMessage(content=f"""
User message: {state['current_message']}
Actions taken: {last_decision}
Tool results: {tool_results}

Generate an appropriate response.
""")
        return [system_message, human_message]

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse analysis response from LLM."""
        try:
            import json
            return json.loads(response)
        except:
            return {"intent": "unknown", "requires_action": False, "urgency": "low"}
            
    def _parse_decision_response(self, response, state: AgentGraphState) -> AgentDecision:
        """Parse decision response from LLM."""
        actions = []
        if hasattr(response, 'additional_kwargs') and 'function_call' in response.additional_kwargs:
            function_call = response.additional_kwargs['function_call']
            action = AgentAction(
                action_type="tool_call",
                tool_name=function_call['name'],
                parameters=json.loads(function_call['arguments']),
                reasoning=response.content or "Tool execution requested"
            )
            actions.append(action)
        elif response.content:
            action = AgentAction(
                action_type="send_message",
                parameters={"message": response.content},
                reasoning="Direct response to user"
            )
            actions.append(action)
        return AgentDecision(
            decision_type="action_sequence",
            confidence=0.8,
            reasoning=response.content or "Automated decision",
            actions=actions,
            metadata={}
        )
        
    def _parse_recovery_response(self, response: str) -> Dict[str, Any]:
        """Parse error recovery response."""
        try:
            import json
            return json.loads(response)
        except:
            return {
                "should_retry": False,
                "error_message": "I encountered an error. Please try again.",
                "suggested_action": "retry"
            }
            
    def get_compiled_graph(self):
        """Get the compiled LangGraph."""
        return self.graph