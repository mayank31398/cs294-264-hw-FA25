from abc import ABC, abstractmethod
from openai import OpenAI


try:
    from vllm import LLM as VLLM
except:
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
        # TODO(student): Initialize your OpenAI client or chosen LLM provider here.
        self.stop_token = stop_token
        self.model_name = model_name
        self.openai_model = openai_model

        if openai_model:
            self._client = OpenAI()
        else:
            self._client = VLLM(model_name)

        # raise NotImplementedError("OpenAIModel.__init__ must be implemented by the student")

    def generate(self, prompt: str) -> str:
        # TODO(student): Call the model, obtain text, and ensure the stop token is present.
        # Return the raw text including the terminal stop token required by the parser.

        try:
            if self.openai_model:
                response = self._client.responses.create(model="gpt-5", input=prompt).output_text
            else:
                response = self._client.generate(prompt)[0].outputs[0].text

            response += self.stop_token

            return response
        except Exception as e:
            raise RuntimeError(f"Failed to generate from OpenAI model: {e}")


if __name__ == "__main__":
    model = OpenAIModel("oops", model_name="/u/shawntan/proj/mayank/lm-engine/Qwen1.5-MoE-A2.7B", openai_model=False)
    print(model.generate("Hi, I am Mayank"))
