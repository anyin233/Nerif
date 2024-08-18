import os
import numpy as np
from openai import OpenAI

from nerif_agent import SimpleEmbeddingAgent, SimpleChatAgent

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


def similarity_dist(vec1, vec2, func="cosine"):
    if func == "cosine":
        return 1 - (vec1 @ vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    else:
        return np.linalg.norm(vec1 - vec2)


class NerifVeification:
    def __init__(self, possible_value: list[str] = None, proxy_url=None, api_key=None, model="text-embedding-3-small"):
        if possible_value is None:
            possible_value = ["True", "False"]
        if possible_value == [] or possible_value is None:
            possible_value = ["True", "False"]
        self.possible = [x.lower() for x in possible_value]
        self.embedding = SimpleEmbeddingAgent(proxy_url, api_key, model)
        self.possible_embed = []
        for index in range(len(self.possible)):
            self.possible_embed.append(self.embedding.encode(self.possible[index]))

    def verify(self, text: str):
        if text.lower() in self.possible:
            return True
        return False

    def force_fit(self, text: str, similarity="cosine"):
        text_embed = self.embedding.encode(text)
        min_dist = similarity_dist(text_embed, self.possible_embed[0], similarity)
        min_id = 0
        for index in range(1, len(self.possible_embed)):
            dist = similarity_dist(text_embed, self.possible_embed[index], similarity)
            if dist < min_dist:
                min_dist = dist
                min_id = index
        return self.possible[min_id]


class Nerif:
    def __init__(self, model="gpt-4o", proxy_url=None, api_key=None, temperature=0):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.model = model
        self.prompt = (
            "Given the following text, determine if the statement is true or false.\n"
            "Only answer with 'True' or 'False'."
        )
        self.agent = SimpleChatAgent(proxy_url=proxy_url, api_key=api_key, model=model, temperature=temperature,
                                     default_prompt=self.prompt)
        self.verification = NerifVeification()

    def judge(self, text, max_retry=5):
        user_prompt = (f"Now the question is:"
                       f"<question>\n "
                       f"{text}"
                       f"</question>\n"
                       f"True or False? (Remeber, only) answer with 'True' or 'False'.")
        try_id = 0
        result = ""

        while try_id < max_retry:
            result = self.agent.chat(user_prompt, max_tokens=10)
            if self.verification.verify(result):
                if result == "True":
                    return True
                else:
                    return False
            try_id += 1
            self.agent.temperature = max(1, self.agent.temperature + 0.1)
        result = self.verification.force_fit(result)

        if result == "True":
            return True
        else:
            return False

    @classmethod
    def instance(cls, text, max_retry=5, model="gpt-4o", api_key=None, proxy_url=None):
        new_instance = cls(model=model, api_key=api_key, proxy_url=proxy_url)
        return new_instance.judge(text, max_retry=max_retry)


def nerif(text, proxy_url=None, api_key=None, model="text-embedding-3-small"):
    return Nerif.instance(text, proxy_url=proxy_url, api_key=api_key, model=model)


class NerifMatch:
    def __init__(self, choice_dict, model="gpt-4o", api_key=None, proxy_url=None, temperature=0):
        self.choice = choice_dict
        self.model = model
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.prompt = (
            "Given the following text, determine the best route to take.\n"
            "If it is hard to make the decision, choose the one you think is the most proper.\n"
            "<options>"
        )
        index = 0
        for _, value in self.choice.items():
            index += 1
            self.prompt += (f"<option>"
                            f"<id>{index}</id>"
                            f"<description>{value}</description>"
                            f"</option>\n")
        self.prompt += "</options>"
        self.prompt += "Choose the best route from the following options.\n" "Only give me the choice ID, only a number"
        self.agent = SimpleChatAgent(proxy_url=proxy_url, api_key=api_key, model=model, temperature=temperature,
                                     default_prompt=self.prompt)
        self.verification = NerifVeification(possible_value=[str(x) for x in range(1, index + 1)])

    def id_to_key(self, index):
        return list(self.choice.keys())[index - 1]

    def match(self, text, max_retry=5):
        true_prompt = self.route.replace("REPLACE_ME", text)
        try_id = 0
        while try_id < max_retry:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": true_prompt,
                    }
                ],
                model=self.model,
            )
            choice = response.choices[0].message.content
            if self.verification.verify(choice):
                # pass verification
                return self.id_to_key(int(choice))
            else:
                format_value = self.verification.simple_format(choice)
                if format_value is not None:
                    return self.id_to_key(int(format_value))

            try_id += 1
        raise Exception("Failed to verify the result in switch.")

    @classmethod
    def instance(cls, dict, text, max_retry=5, model="gpt-4o", api_key=os.environ.get("OPENAI_API_KEY")):
        isinstance = cls(dict, model=model, api_key=api_key)
        return isinstance.match(text, max_retry=max_retry)
