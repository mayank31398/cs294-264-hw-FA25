from abc import ABC, abstractmethod
import os
from openai import OpenAI

try:
    from vllm import LLM as VLLM
except ImportError:
    pass


class LLM(ABC):
    """Abstract base class for Large Language Models."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a response from the LLM given a prompt.
        Must include any required stop-token logic at the caller level.
        """
        raise NotImplementedError


class OpenAIModel(LLM):
    """
    Example LLM implementation using OpenAI's Responses API.

    TODO(student): Implement this class to call your chosen backend (e.g., OpenAI GPT-5 mini)
    and return the model's text output. You should ensure the model produces the response
    format required by ResponseParser and include the stop token in the output string.
    """

    def __init__(self, stop_token: str, model_name: str = "gpt-5-mini", openai_model: bool = True):
        self.stop_token = stop_token
        self.model_name = model_name
        self.openai_model = openai_model

        if openai_model:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        else:
            self.client = VLLM(model_name)

    def generate(self, prompt: str) -> str:
        if self.openai_model:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                stop=[self.stop_token],
                # temperature=0.0
            )
            
            # Get the text content and ensure stop token is present
            text = response.choices[0].message.content
        else:
            text = self.client.generate(prompt)[0].outputs[0].text

        if text and not text.endswith(self.stop_token):
            text += self.stop_token

        return text
