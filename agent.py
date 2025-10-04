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

import os
from typing import List, Callable, Dict, Any
import time
import yaml

from response_parser import ResponseParser
from llm import LLM, OpenAIModel
import inspect

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
        # Create required root nodes: system -> user -> instructor
        system_prompt = """You are a Smart ReAct agent designed to solve software engineering tasks.

Your task is to understand the problem, explore the codebase, identify the bug or issue, and implement a fix.

WORKFLOW:
1. First, understand the problem statement thoroughly
2. Explore the codebase to locate relevant files
3. Read and analyze the code to identify the root cause
4. Implement a fix by modifying the necessary files
5. Test your fix to ensure it works correctly
6. When you're confident the issue is resolved, call the finish function

IMPORTANT GUIDELINES:
- Always reason through your actions step by step
- Use the available tools to explore and modify code
- Test your changes before submitting
- If you get stuck or make repeated mistakes, use add_instructions_and_backtrack to reset
- Be methodical and thorough in your approach
- Every response MUST end with a function call in the specified format"""
        
        self.system_message_id = self.add_message("system", system_prompt)
        self.user_message_id = self.add_message("user", "")
        self.instructions_message_id = self.add_message("instructor", "")
        
        # NOTE: mandatory finish function that terminates the agent
        self.add_functions([self.finish])

    # -------------------- MESSAGE TREE --------------------
    def add_message(self, role: str, content: str) -> int:
        """
        Create a new message and add it to the tree.

        The message must include fields: role, content, timestamp, unique_id, parent, children.
        Maintain a pointer to the current node and the root node.
        """
        message_id = len(self.id_to_message)
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "unique_id": message_id,
            "parent": self.current_message_id if self.current_message_id != -1 else None,
            "children": []
        }
        
        # Add to the list
        self.id_to_message.append(message)
        
        # Update parent's children if not root
        if self.current_message_id != -1:
            self.id_to_message[self.current_message_id]["children"].append(message_id)
        
        # Update current message id
        self.current_message_id = message_id
        
        # Set root message id if this is the first message
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
        
        # Build path from root to current message
        path = []
        current = self.current_message_id
        while current is not None:
            path.append(current)
            current = self.id_to_message[current]["parent"]
        
        # Reverse to get root-to-current order
        path.reverse()
        
        # Build context from the path
        context_parts = []
        for message_id in path:
            context_parts.append(self.message_id_to_context(message_id))
            
        return "\n".join(context_parts)

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
            result (str): the result generated by the agent

        Returns:
            The result passed as an argument.  The result is then returned by the agent's run method.
        """
        return result 

    def add_instructions_and_backtrack(self, instructions: str, at_message_id: int):
        """
        The agent should call this function if it is making too many mistakes or is stuck.

        The function changes the content of the instruction node with 'instructions' and
        signals that we should backtrack to 'at_message_id'. The actual backtracking happens
        in the run loop after the tool result is added.

        Returns a short success string.
        """
        # Validate the message id FIRST before making any changes
        if not (0 <= at_message_id < len(self.id_to_message)):
            raise ValueError(f"Invalid message_id {at_message_id} for backtracking (valid range: 0-{len(self.id_to_message)-1})")
        
        # Update the instructions message content only after validation
        self.set_message_content(self.instructions_message_id, instructions)
        
        return f"Successfully updated instructions. Will backtrack to message {at_message_id}"

    # -------------------- MAIN LOOP --------------------
    def run(self, task: str, instance_id: str, max_steps: int) -> str:
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
        
        os.makedirs("outputs", exist_ok=True)
        f = open(f"outputs/{instance_id}.txt", "w")
        
        for step in range(max_steps):
            try:
                # Build context from the message tree
                assistant_id = self.add_message("assistant", "")
                context = self.get_context()

                # print(step)
                response = self.llm.generate(context)

                # print(response)
                self.set_message_content(assistant_id, response)

                print(self.get_context())
                f.write(self.get_context() + "\n")
                f.write("*" * 100 + "\n")
                f.write(response + "\n")
                parsed = self.parser.parse(response)
                f.write(str(parsed) + "\n")
                f.write("*" * 100 + "\n\n\n\n\n")
                
                # Execute the tool
                function_name = parsed["name"]
                arguments = parsed["arguments"]
                
                if function_name in self.function_map:
                    tool = self.function_map[function_name]
                    try:
                        if function_name == "finish":
                            if "git" not in arguments.get("result", ""):
                                raise ValueError("finish result must be a git diff")

                            result = self.finish(str(arguments.get("result", "")))
                            self.add_message("tool", f"Finished with result: {result}")
                            return result
                        elif function_name == "add_instructions_and_backtrack":
                            # Special handling for backtracking
                            result = tool(**arguments)
                            self.add_message("tool", str(result))
                            # Now actually perform the backtracking
                            # The backtrack target is in arguments["at_message_id"]
                            backtrack_target = int(arguments["at_message_id"])
                            self.current_message_id = backtrack_target
                            f.write(f">>> Backtracked to message {backtrack_target}\n")
                            print(f">>> Backtracked to message {backtrack_target}")

                        result = tool(**arguments)
                        self.add_message("tool", str(result))
                            
                    except Exception as e:
                        error_msg = f"Error executing {function_name}: {str(e)}"
                        self.add_message("tool", error_msg)
                else:
                    error_msg = f"Unknown function: {function_name}"
                    self.add_message("tool", error_msg)
                    
            except Exception as e:
                error_msg = f"Error in step {step}: {str(e)}"
                self.add_message("tool", error_msg)
                
        # If we reach here, we've exceeded max steps
        return "Maximum steps exceeded without completion"
    
    def save_history(self, file_name: str):
        """Save the agent's attributes as a YAML file."""
        data = {
            "name": self.name,
            "timestamp": int(time.time()),
            "id_to_message": self.id_to_message,
            "root_message_id": self.root_message_id,
            "current_message_id": self.current_message_id,
            "function_map": {name: func.__name__ for name, func in self.function_map.items()}
        }
        with open(file_name, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    def message_id_to_context(self, message_id: int) -> str:
        """
        Helper function to convert a message id to a context string.
        """
        message = self.id_to_message[message_id]
        header = f'----------------------------\n|MESSAGE(role="{message["role"]}", id={message["unique_id"]})|\n'
        content = message["content"]
        if message["role"] == "system":
            tool_descriptions = []
            for tool in self.function_map.values():
                signature = inspect.signature(tool)
                docstring = inspect.getdoc(tool)
                tool_description = f"Function: {tool.__name__}{signature}\n{docstring}\n"
                tool_descriptions.append(tool_description)

            tool_descriptions = "\n".join(tool_descriptions)
            return (
                f"{header}{content}\n"
                f"--- AVAILABLE TOOLS ---\n{tool_descriptions}\n\n"
                f"--- RESPONSE FORMAT ---\n{self.parser.response_format}\n"
            )
        elif message["role"] == "instructor":
            return f"{header}YOU MUST FOLLOW THE FOLLOWING INSTRUCTIONS AT ANY COST. OTHERWISE, YOU WILL BE DECOMISSIONED.\n{content}\n"
        else:
            return f"{header}{content}\n"

def main():
    from envs import DumbEnvironment
    llm = OpenAIModel("----END_FUNCTION_CALL----", "gpt-5-mini", True)
    parser = ResponseParser()

    env = DumbEnvironment()
    dumb_agent = ReactAgent("dumb-agent", parser, llm)
    dumb_agent.add_functions([env.execute, env.skip])
    result = dumb_agent.run("List all files in the current directory.", "dumb", max_steps=10)
    print(result)

if __name__ == "__main__":
    # Optional: students can add their own quick manual test here.
    main()