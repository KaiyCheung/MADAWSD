import time
import random
import openai

class Agent:
    def __init__(self, model_name: str, name: str, temperature: float, sleep_time: float=0) -> None:

        self.model_name = model_name
        self.name = name
        self.temperature = temperature
        self.memory_lst = []
        self.sleep_time = sleep_time

    def query(self, messages: "list[dict]", api_key: str, temperature: float) -> str:
        response = openai.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            api_key=api_key,
        )
        gen = response['choices'][0]['message']['content']
        return gen


    def set_meta_prompt(self, meta_prompt: str):
        self.memory_lst.append({"role": "system", "content": f"{meta_prompt}"})

    def add_event(self, event: str):
        self.memory_lst.append({"role": "user", "content": f"{event}"})

    def add_memory(self, memory: str):
        self.memory_lst.append({"role": "assistant", "content": f"{memory}"})
        #print(f"----- {self.name} -----\n{memory}\n")

    def ask(self, temperature: float=None):
        return self.query(self.memory_lst, api_key=self.openai_api_key, temperature=temperature if temperature else self.temperature)

