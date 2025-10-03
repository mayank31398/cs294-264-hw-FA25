import subprocess
import os

class LimitsExceeded(Exception):
    """Raised when the agent has reached its step limit."""


class SWEEnvironment:
    """
    Minimal interface to the SWEBench execution environment.

    Students may use their own wrapper. The environment must expose:
    - execute(command: str) -> str: Run a shell command and return stdout, or raise ValueError on failure
    """

    def __init__(self, instance: dict):
        from utils import get_sb_environment
        self.env = get_sb_environment(instance)
     
    # -------------------- REQUIRED TOOLS --------------------
    def run_bash_cmd(self, command: str) -> str:
        """
        Run the command in a bash shell and return the output or throw a ValueError
        if the process returns non-zero exit code.

        Args;
            command (str): the shell command to run

        Returns:
            The output of running the shell command
        """
        try:
            output = self.env.execute(command)["output"]
        except subprocess.TimeoutExpired as e:
            output = e.output.decode("utf-8", errors="replace") if e.output else ""
            raise ValueError(output)
        except TimeoutError:
            raise ValueError("TimeoutError")
        return output
    
    def generate_patch(self, result: str) -> str:
        """
        Generate a patch from the result (for SWE-Bench)
        """
        try:
            patch_output = self.env.execute("git add -A && git diff --cached")["output"]

            if patch_output.strip():
                return patch_output
            else:
                return f"{result}\n\nNo changes detected to generate a patch."
        except Exception as e:
            return f"{result}\n\nError running git commands: {e}"
    
    # -------------------- TODO(student): add more functions here if you want --------------------
    def replace_in_file(self, file_path: str, from_line: int, to_line: int, content: str) -> str:
        """
        Replace the content of the file from the given line to the given line with the given content.
        
        Args:
            file_path (str): Path to the file to modify
            from_line (int): Starting line number (1-indexed)
            to_line (int): Ending line number (1-indexed, inclusive)
            content (str): New content to replace the lines with
            
        Returns:
            str: Success message or error message
        """
        try:
            # Escape content for sed - escape backslashes, forward slashes, ampersands, and newlines
            escaped_content = content.replace('\\', '\\\\').replace('/', '\\/').replace('&', '\\&').replace('\n', '\\n')
            
            # Use sed to replace the lines in the container
            cmd = f"sed -i '{from_line},{to_line}c\\{escaped_content}' {file_path}"
            self.env.execute(cmd)["output"]
            
            return f"Successfully replaced lines {from_line}-{to_line} in {file_path}"
        except Exception as e:
            return f"Error replacing content in {file_path}: {str(e)}"
    
    def show_file(self, file_path: str, start_line: int = 1, num_lines: int = -1) -> str:
        """
        Show the content of the file with line numbers. Optionally show only a range of lines.
        
        Args:
            file_path (str): Path to the file to display
            start_line (int): Starting line number (1-indexed, default 1)
            num_lines (int): Number of lines to show (-1 for all lines, default -1)
            
        Returns:
            str: File contents with line numbers or error message
        """
        try:
            start_line = int(start_line)
            num_lines = int(num_lines)

            # Get total lines first
            total_lines_output = self.env.execute(f"wc -l < {file_path}")["output"].strip()
            total_lines = int(total_lines_output) if total_lines_output else 0
            
            # Calculate range
            if num_lines == -1:
                end_line = total_lines
            else:
                end_line = min(start_line - 1 + num_lines, total_lines)
            
            # Use awk to add line numbers and extract the range
            cmd = f"awk 'NR>={start_line} && NR<={end_line} {{printf \"%4d|%s\\n\", NR, $0}}' {file_path}"
            numbered_content = self.env.execute(cmd)["output"]
            
            header = f"Contents of {file_path} (lines {start_line}-{end_line} of {total_lines}):\n"
            return header + numbered_content
        except Exception as e:
            return f"Error reading file {file_path}: {str(e)}"
    
    def find_in_file(self, file_path: str, search_string: str) -> str:
        """
        Search for a string in a file and return the line numbers where it appears.
        
        Args:
            file_path (str): Path to the file to search
            search_string (str): String to search for
            
        Returns:
            str: Line numbers and content where the string appears
        """
        try:
            # Escape special characters for grep
            escaped_search = search_string.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')
            
            # Use grep with line numbers
            cmd = f'grep -n "{escaped_search}" {file_path} || true'
            output = self.env.execute(cmd)["output"]
            
            if output.strip():
                # Format output with padding like before
                lines = output.strip().split('\n')
                formatted = []
                for line in lines:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        line_num = parts[0]
                        content = parts[1]
                        formatted.append(f"{int(line_num):4d}|{content}\n")
                return f"Found '{search_string}' in {file_path}:\n" + "".join(formatted)
            else:
                return f"No matches found for '{search_string}' in {file_path}"
        except Exception as e:
            return f"Error searching file {file_path}: {str(e)}"
    
    def write_file(self, file_path: str, content: str) -> str:
        """
        Write content to a file, creating it if it doesn't exist or overwriting it if it does.
        
        Args:
            file_path (str): Path to the file to write
            content (str): Content to write to the file
            
        Returns:
            str: Success message or error message
        """
        try:
            # Escape content for heredoc - escape backslashes and dollar signs
            escaped_content = content.replace('\\', '\\\\').replace('$', '\\$')
            
            # Use cat with heredoc to write file in container
            # EOF delimiter is unlikely to appear in code
            cmd = f"cat > {file_path} << 'ENDOFFILE'\n{content}\nENDOFFILE"
            self.env.execute(cmd)
            
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"Error writing to file {file_path}: {str(e)}"

class DumbEnvironment:
    """
    Dumb environment that just executes the command
    """

    def execute(self, command: str) -> str:
        """
        Run the command in bash and return the output

        Args;
            command (str): the shell command to run

        Returns:
            The output of running the shell command
        """
        result = subprocess.run(command, capture_output=True, shell=True, check=False)
        output = f"--STDOUT--\n{result.stdout.decode()}\n--STDERR--\n{result.stderr.decode()}"
        if result.returncode:
            raise ValueError(output)
        return output

    def skip(self, *args, **kwargs) -> None:
        return
