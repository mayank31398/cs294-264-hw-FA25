class ResponseParser:
    """
    Parses LLM responses to extract a single function call using a rigid textual format.

    The LLM must output exactly one function call at the end of its response.
    Do NOT use JSON or XML. Use rfind to locate the final markers.
    """

    BEGIN_CALL = "----BEGIN_FUNCTION_CALL----"
    END_CALL = "----END_FUNCTION_CALL----"
    ARG_SEP = "----ARG----"

    # Students should include this exact template in the system prompt so the LLM follows it.
    response_format = f"""
your_thoughts_here
...
{BEGIN_CALL}
function_name
{ARG_SEP}
arg1_name
arg1_value (can be multiline)
{ARG_SEP}
arg2_name
arg2_value (can be multiline)
...
{END_CALL}
"""

    def parse(self, text: str) -> dict:
        """
        Parse the function call from `text` using string.rfind to avoid confusion with
        earlier delimiter-like content in the reasoning.

        Returns a dictionary: {"thought": str, "name": str, "arguments": dict}
        """
        # Find END_CALL via rfind
        end_pos = text.rfind(self.END_CALL)
        if end_pos == -1:
            raise ValueError("No END_FUNCTION_CALL marker found")
        
        # Find the matching BEGIN_CALL before END_CALL
        begin_pos = text.rfind(self.BEGIN_CALL, 0, end_pos)
        if begin_pos == -1:
            raise ValueError("No BEGIN_FUNCTION_CALL marker found before END_FUNCTION_CALL")
        
        # Extract thought (everything before BEGIN_CALL)
        thought = text[:begin_pos].strip()
        
        # Extract function call content between markers
        call_content = text[begin_pos + len(self.BEGIN_CALL):end_pos].strip()
        
        # Split by ARG_SEP to get function name and arguments
        parts = call_content.split(self.ARG_SEP)
        if len(parts) < 1:
            raise ValueError("No function name found in function call")

        # First part is the function name
        function_name = parts[0].strip()
        parts = parts[1:]

        # Parse arguments (name-value pairs)
        arguments = {}
        for i in range(len(parts)):
            arg_value = parts[i].strip()
            arg, value = arg_value.split("\n")
            arguments[arg] = value
        
        return {
            "thought": thought,
            "name": function_name,
            "arguments": arguments
        }
