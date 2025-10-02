"""
Starter scaffold for the CS 294-264 HW1 ReAct agent.

Students must implement a minimal ReAct agent that:
- Maintains a message history tree (role, content, timestamp, unique_id, parent, children)
- Uses a textual function-call format (see ResponseParser) with rfind-based parsing
- Alternates Reasoning and Acting until calling the tool `finish`
- Supports tools: `run_bash_cmd`, `finish`, and `add_instructions_and_backtrack`

This file intentionally omits core implementations and replaces them with
clear specifications and TODOs.
"""

import time
from typing import List, Callable, Dict, Any

from response_parser import ResponseParser
from llm import LLM, OpenAIModel

class ReactAgent:
    """
    Minimal ReAct agent that:
    - Maintains a message history tree with unique ids
    - Builds the LLM context from the root to current node
    - Registers callable tools with auto-generated docstrings in the system prompt
    - Runs a Reason-Act loop until `finish` is called or MAX_STEPS is reached
    """

    def __init__(self, name: str, parser: ResponseParser, llm: LLM):
        self.name: str = name
        self.parser = parser
        self.llm = llm

        # Message tree storage
        self.id_to_message: List[Dict[str, Any]] = []
        self.root_message_id: int = -1
        self.current_message_id: int = -1

        # Registered tools
        self.function_map: Dict[str, Callable] = {}

        # Set up the initial structure of the history
        # Create required root nodes and a user node (task) and an instruction node.
        self.system_message_id = self.add_message("system", "You are a Smart ReAct agent. If the specified task is completed, call the finish function.")
        self.user_message_id = self.add_message("user", "")
        self.assistant_message_id = self.add_message("assistant", "")

        # NOTE: mandatory finish function that terminates the agent
        self.add_functions([self.finish])

    # -------------------- MESSAGE TREE --------------------
    def add_message(self, role: str, content: str) -> int:
        """
        Create a new message and add it to the tree.

        The message must include fields: role, content, timestamp, unique_id, parent, children.
        Maintain a pointer to the current node and the root node.
        """
        # Create new message with all required fields
        message_id = len(self.id_to_message)
        message = {
            "role": role,
            "content": content,
            "timestamp": int(time.time()),
            "unique_id": message_id,
            "parent": self.current_message_id if self.current_message_id != -1 else None,
            "children": []
        }
        
        # Add to storage
        self.id_to_message.append(message)
        
        # Update parent's children list if not root
        if self.current_message_id != -1:
            self.id_to_message[self.current_message_id]["children"].append(message_id)
        
        # Update current pointer
        self.current_message_id = message_id
        
        # Set root if this is the first message
        if self.root_message_id == -1:
            self.root_message_id = message_id
            
        return message_id

    def set_message_content(self, message_id: int, content: str) -> None:
        """Update message content by id."""
        if 0 <= message_id < len(self.id_to_message):
            self.id_to_message[message_id]["content"] = content
        else:
            raise ValueError(f"Invalid message_id: {message_id}")

    def get_context(self) -> str:
        """
        Build the full LLM context by walking from the root to the current message.
        """
        if self.current_message_id == -1:
            return ""
        
        # Build context by walking from root to current
        context_parts = []
        current_id = self.root_message_id
        
        while current_id != -1 and current_id < len(self.id_to_message):
            message = self.id_to_message[current_id]
            role = message["role"]
            content = message["content"]
            
            if role == "system":
                # Add tool descriptions to system message
                tool_descriptions = self._get_tool_descriptions()
                full_content = content + "\n\n" + tool_descriptions + "\n\n" + self.parser.response_format
                context_parts.append(f"System: {full_content}")
            elif role == "user":
                context_parts.append(f"User: {content}")
            elif role == "assistant":
                context_parts.append(f"Assistant: {content}")
            elif role == "tool":
                context_parts.append(f"Tool: {content}")
            elif role == "instructor":
                context_parts.append(f"Instructor: {content}")
            else:
                context_parts.append(f"{role.title()}: {content}")
            
            # Move to next message in the path
            if current_id == self.current_message_id:
                break
                
            # Find the next message in the path (this is a simplified version)
            # In a full implementation, we'd need to track the conversation path
            current_id += 1
            if current_id >= len(self.id_to_message):
                break
        
        return "\n\n".join(context_parts).strip()

    def _get_tool_descriptions(self) -> str:
        """Generate tool descriptions for the system prompt."""
        descriptions = []
        for name, func in self.function_map.items():
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            param_str = ", ".join(params)
            
            # Get docstring
            docstring = func.__doc__ or "No description available"
            
            descriptions.append(f"- {name}({param_str}): {docstring}")
        
        return "Available tools:\n" + "\n".join(descriptions)

    # -------------------- REQUIRED TOOLS --------------------
    def add_functions(self, tools: List[Callable]):
        """
        Add callable tools to the agent's function map.

        The system prompt must include tool descriptions that cover:
        - The signature of each tool
        - The docstring of each tool
        """
        for tool in tools:
            self.function_map[tool.__name__] = tool
    
    def finish(self, result: str):
        """The agent must call this function with the final result when it has solved the given task. The function calls "git add -A and git diff --cached" to generate a patch and returns the patch as submission.

        Args: 
            result (str); the result generated by the agent

        Returns:
            The result passed as an argument.  The result is then returned by the agent's run method.
        """
        return result 

    def add_instructions_and_backtrack(self, instructions: str, at_message_id: int):
        """
        The agent should call this function if it is making too many mistakes or is stuck.

        The function changes the content of the instruction node with 'instructions' and
        backtracks at the node with id 'at_message_id'. Backtracking means the current node
        pointer moves to the specified node and subsequent context is rebuilt from there.

        Returns a short success string.
        """
        # Update the instruction message content
        self.set_message_content(self.instructions_message_id, instructions)
        
        # Backtrack to the specified message
        if 0 <= at_message_id < len(self.id_to_message):
            self.current_message_id = at_message_id
            return "Instructions updated and backtracked successfully."
        else:
            return "Instructions updated but invalid backtrack message_id."

    # -------------------- MAIN LOOP --------------------
    def run(self, task: str, max_steps: int) -> str:
        """
        Run the agent's main ReAct loop:
        - Set the user prompt
        - Loop up to max_steps (<= 100):
            - Build context from the message tree
            - Query the LLM
            - Parse a single function call at the end (see ResponseParser)
            - Execute the tool
            - Append tool result to the tree
            - If `finish` is called, return the final result
        """
        # Set the user prompt
        self.set_message_content(self.user_message_id, task)
        
        for step in range(max_steps):
            try:
                # Build context from the message tree
                context = self.get_context()
                print(context)
                
                # Query the LLM
                response = self.llm.generate(context)
                print(response)
                print("--------------------------------")
    #             response = """To show the contents of all files in the current directory, I will execute the command `cat *`. This will display the contents of all files in the current directory. 

    # Let's execute the command and retrieve the output. 

    # ----BEGIN_FUNCTION_CALL----
    # execute
    # ----ARG----
    # command
    # ls
    # ----END_FUNCTION_CALL----"""
                
                # Add assistant message
                self.set_message_content(self.assistant_message_id, response)
                
                # Parse the function call
                parsed = self.parser.parse(response)
                print(parsed)
                function_name = parsed["name"]
                arguments = parsed["arguments"]

                # If finish is called, return the result
                if function_name == "finish":
                    return result
                
                # Execute the tool
                if function_name in self.function_map:
                    func = self.function_map[function_name]
                    try:
                        result = func(**arguments)
                        tool_result = f"Tool {function_name} executed successfully. Result: {result}"
                    except Exception as e:
                        tool_result = f"Tool {function_name} failed with error: {str(e)}"
                else:
                    tool_result = f"Unknown function: {function_name}"
                
                # Add tool result to the tree
                self.add_message("tool", tool_result)
                self.add_message("assistant", "")
            except Exception as e:
                # Add error message and continue
                error_msg = f"Error in step {step}: {str(e)}"
                self.add_message("tool", error_msg)
                continue
        
        # If we reach here, we've exceeded max_steps
        return "Maximum steps reached without completion."

def main():
    from envs import DumbEnvironment
    llm = OpenAIModel("----END_FUNCTION_CALL----", "gpt-4o-mini")
    parser = ResponseParser()

    env = DumbEnvironment()
    dumb_agent = ReactAgent("dumb-agent", parser, llm)
    dumb_agent.add_functions([env.execute])
    result = dumb_agent.run("Show the all files in the current directory.", max_steps=4)
    print(result)

if __name__ == "__main__":
    # Optional: students can add their own quick manual test here.
    main()