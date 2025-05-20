import os
import json
from code.utils.agent import Agent
from tqdm import tqdm
from sklearn.metrics import f1_score, precision_score, recall_score
import openai
import re
import time
from json_repair import repair_json


openai_api_key=""

NAME_LIST=[
    "Affirmative side",
    "Negative side",
    "Moderator",
]

class DebatePlayer(Agent):
    def __init__(self, model_name: str, name: str, temperature:float, openai_api_key: str, sleep_time: float) -> None:
        super(DebatePlayer, self).__init__(model_name, name, temperature, sleep_time)
        self.openai_api_key = openai_api_key


class Debate:
    def __init__(self,
            model_name: str='', 
            temperature: float=0, 
            num_players: int=3, 
            openai_api_key: str=None,
            config: dict=None,
            max_round: int=3,
            sleep_time: float=0
        ) -> None:

        self.model_name = model_name
        self.temperature = temperature
        self.num_players = num_players
        self.openai_api_key = openai_api_key
        self.config = config
        self.max_round = max_round
        self.sleep_time = sleep_time

        self.init_prompt()

        # creat&init agents
        self.creat_agents()
        self.init_agents()


    def init_prompt(self):
        def prompt_replace(key):
            self.config[key] = self.config[key].replace("##debate_topic##", self.config["debate_topic"])
        prompt_replace("player_meta_prompt")
        prompt_replace("moderator_meta_prompt")
        prompt_replace("affirmative_prompt")
        prompt_replace("judge_prompt_last2")

    def creat_agents(self):
        # creates players
        self.players = [
            DebatePlayer(model_name=self.model_name, name=name, temperature=self.temperature, openai_api_key=self.openai_api_key, sleep_time=self.sleep_time) for name in NAME_LIST
        ]
        self.affirmative = self.players[0]
        self.negative = self.players[1]
        self.moderator = self.players[2]

    def init_agents(self):
        # start: set meta prompt
        self.affirmative.set_meta_prompt(self.config['player_meta_prompt'])
        self.negative.set_meta_prompt(self.config['player_meta_prompt'])
        self.moderator.set_meta_prompt(self.config['moderator_meta_prompt'])
        
        # start: first round debate, state opinions
        #print(f"===== Debate Round-1 =====\n")
        self.affirmative.add_event(self.config['affirmative_prompt'])
        self.aff_ans = self.affirmative.ask()
        #print("ans ============= " + self.aff_ans)
        self.affirmative.add_memory(self.aff_ans)
        self.config['base_answer'] = self.aff_ans

        match = re.search(r"Answer[:：]\s*(.*?)(?=\s|$)", self.aff_ans)
        extracted_text = match.group(1)
        self.aff = extracted_text
        if self.aff[-1] == '.':
            self.aff = self.aff[:-1]

        self.negative.add_event(self.config['negative_prompt'].replace('##aff_ans##', self.aff_ans))
        self.neg_ans = self.negative.ask()
        self.negative.add_memory(self.neg_ans)

        match = re.search(r"Answer[:：]\s*(.*?)(?=\s|$)", self.neg_ans)
        extracted_text = match.group(1)
        self.neg = extracted_text
        if self.neg[-1] == '.':
            self.neg = self.neg[:-1]
        self.moderator.add_event(self.config['moderator_prompt'].replace('##aff_ans##', self.aff_ans).replace('##neg_ans##', self.neg_ans).replace('##round##', 'first'))
        self.mod_ans = self.moderator.ask()
        tempans = self.mod_ans

        while tempans[0] != '{' or tempans[-1] != '}':
            tempans = check(self.mod_ans)
        
        tempans = repair_json(tempans)
        self.mod_ans = tempans

        if self.mod_ans[-1] != '}':
            self.mod_ans = self.mod_ans[:-1]
        self.moderator.add_memory(self.mod_ans)
        self.mod_ans = eval(self.mod_ans)

        if 'Debate_answer' in self.mod_ans:
            self.mod_ans["debate_answer"] = self.mod_ans["Debate_answer"]
        if 'Debate_Answer' in self.mod_ans:
            self.mod_ans["debate_answer"] = self.mod_ans["Debate_Answer"]
        if 'debate answer' in self.mod_ans:
            self.mod_ans["debate_answer"] = self.mod_ans["debate answer"]
        if 'Debate answer' in self.mod_ans:
            self.mod_ans["debate_answer"] = self.mod_ans["Debate answer"]
        if 'Debate Answer' in self.mod_ans:
            self.mod_ans["debate_answer"] = self.mod_ans["Debate Answer"]
        if 'debate_answer' not in self.mod_ans:
            self.mod_ans['debate_answer'] = ""

    def round_dct(self, num: int):
        dct = {
            1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth', 6: 'sixth', 7: 'seventh', 8: 'eighth', 9: 'ninth', 10: 'tenth'
        }
        return dct[num]

    def run(self):
        for round in range(self.max_round - 1):
            if self.mod_ans["debate_answer"] != '' and self.mod_ans["debate_answer"] != 'N/A' and self.mod_ans["debate_answer"] != 'n/a' and len(self.mod_ans["debate_answer"]) <= 15:
                break
            elif self.neg == self.aff:
                self.mod_ans["debate_answer"] = self.aff
                print("---gongshi---")
                break
            else:
                print(f"===== Debate Round-{round+2} =====\n")
                self.affirmative.add_event(self.config['debate_prompt'].replace('##oppo_ans##', self.neg_ans))
                self.aff_ans = self.affirmative.ask()
                self.affirmative.add_memory(self.aff_ans)
                
                match = re.search(r"Answer[:：]\s*(.*?)(?=\s|$)", self.aff_ans)
                extracted_text = match.group(1)
                self.aff = extracted_text
                if self.aff[-1] == '.':
                    self.aff = self.aff[:-1]
                self.negative.add_event(self.config['debate_prompt'].replace('##oppo_ans##', self.aff_ans))
                self.neg_ans = self.negative.ask()
                self.negative.add_memory(self.neg_ans)

                match = re.search(r"Answer[:：]\s*(.*?)(?=\s|$)", self.neg_ans)
                extracted_text = match.group(1)
                self.neg = extracted_text
                if self.neg[-1] == '.':
                    self.neg = self.neg[:-1]
                self.moderator.add_event(self.config['moderator_prompt'].replace('##aff_ans##', self.aff_ans).replace('##neg_ans##', self.neg_ans).replace('##round##', self.round_dct(round+2)))
                self.mod_ans = self.moderator.ask()
                tempans = self.mod_ans
                while tempans[0] != '{':
                    tempans = check(self.mod_ans)
                    
                tempans = repair_json(tempans)
                self.mod_ans = tempans

                if self.mod_ans[-1] != '}':
                    self.mod_ans = self.mod_ans[:-1]


                self.moderator.add_memory(self.mod_ans)
                self.mod_ans = eval(self.mod_ans)
                if 'Debate_answer' in self.mod_ans:
                    self.mod_ans["debate_answer"] = self.mod_ans["Debate_answer"]
                    
                if 'Debate_Answer' in self.mod_ans:
                    self.mod_ans["debate_answer"] = self.mod_ans["Debate_Answer"]
                    
                if 'debate answer' in self.mod_ans:
                    self.mod_ans["debate_answer"] = self.mod_ans["debate answer"]
                    
                if 'Debate answer' in self.mod_ans:
                    self.mod_ans["debate_answer"] = self.mod_ans["Debate answer"]
                    
                if 'Debate Answer' in self.mod_ans:
                    self.mod_ans["debate_answer"] = self.mod_ans["Debate Answer"]
                    
                if 'debate_answer' not in self.mod_ans:
                    self.mod_ans['debate_answer'] = ""
                

                

        if self.mod_ans["debate_answer"] != '' and self.mod_ans["debate_answer"] != 'N/A' and self.mod_ans["debate_answer"] != 'n/a' and len(self.mod_ans["debate_answer"]) <= 15:
            self.config.update(self.mod_ans)
            self.config['success'] = True

        else:
            judge_player = DebatePlayer(model_name=self.model_name, name='Judge', temperature=self.temperature, openai_api_key=self.openai_api_key, sleep_time=self.sleep_time)
            aff_ans = self.affirmative.memory_lst[2]['content']
            neg_ans = self.negative.memory_lst[2]['content']
            judge_player.set_meta_prompt(self.config['moderator_meta_prompt'])

            # extract answer candidates
            judge_player.add_event(self.config['judge_prompt_last1'].replace('##aff_ans##', aff_ans).replace('##neg_ans##', neg_ans))
            ans = judge_player.ask()
            judge_player.add_memory(ans)

            # select one from the candidates
            judge_player.add_event(self.config['judge_prompt_last2'])
            ans = judge_player.ask()
            judge_player.add_memory(ans)
            
            ans = repair_json(ans)
            ans = eval(ans)

            if ans["debate_answer"] != '':
                self.config['success'] = True
                # save file
            self.config.update(ans)
            self.players.append(judge_player)

def check(sentence):
    response = openai.ChatCompletion.create(
        model="",
        api_key="",
        messages=[
            {'role': 'system', 'content': 'You need to determine if the text you receive belongs to this format:  {\"Whether there is a preference\": \"Yes or No\", \"Supported Side\": \"Affirmative or Negative\", \"Reason\":  \"\", \"debate_answer\": \"\"}. If yes, print original content, if no, organize the text into the format and print it, the use of quotation marks must be taken care of to ensure the correct JSON format, for example "aaa": "bbb" is correct and "aaa": "b"b"bb" is wrong. Don\'t output text like ``` json either. do not output other irrelevant content.'},
            {'role': 'user', 'content': sentence}
            ],
    )
    gen = response.choices[0].message.content
    return gen

dataset = ["apple", "bank", "bat", "cell", "crane", "date", "digit", "gum", "java", "letter",
        "match", "nail", "pitcher", "pupil", "ring", "rock", "ruler", "seal", "spring", "trunk"]
sense = [("fruit", "company"), ("river", "bank"), ("equipment", "mammal"), ("biology", "prison"), ("bird", "machine"), ("romantic", "fruit"), ("anatomy", "number"), 
         ("mouth", "bubblegum"), ("island", "program"), ("mail", "alphabet"), ("lighter", "sports"), ("finger", "metal"), ("sports", "jug"), ("eye", "student"), 
         ("jewelry", "arena"), ("stone", "music"), ("measure", "governor"), ("close", "animal"), ("device", "season"), ("car", "botany")]

def call_model_per_line(text, idx):
    word = dataset[idx]
    x = sense[idx][0]
    y = sense[idx][1]

    lines = text.split('\n')

    results = []
    output = []

    current_script_path = os.path.abspath(__file__)
    MAD_path = current_script_path.rsplit("/", 1)[0]


    for line in tqdm(lines, desc="Processing " + word):
        debate_topic = "In this sentence: '" + line + "', classify the occurrence of the word '" + word + "' for " +  x + " or for " + y + ". Output the reason before output the answer. For example:\nReason: Give your reasons. Answer: " + x + " or " + y + "\nDon't output irrelevant content."

        config = json.load(open(f"{MAD_path}/code/utils/config4all.json", "r"))

        config['debate_topic'] = debate_topic
        debate = Debate(num_players=3, openai_api_key=openai_api_key, config=config, temperature=0, sleep_time=0)
        debate.run()

        gen = config["debate_answer"].lower()
        output.append(gen)

        gen = 1 if gen == x else 0
        gen = int(gen)
        results.append(gen)
        time.sleep(0.8)

    return results,output


def read_text_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return text

def read_labels_from_file(file_path):
    labels = []
    with open(file_path, 'r') as file:
        for line in file:
            label = int(line.strip())
            labels.append(label)
    return labels

def save_list_to_file(list_data, file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
        for item in list_data:
            file.write(f"{item}\n")

def save_f1_to_file(number, file_path):
    with open(file_path, 'w') as file:
        file.write(str(number))

f1 = 0.0
precision = 0.0
recall = 0.0
f1list = []

prepath = ""
datapath = ""
goldpath = ""

for idx in tqdm(range(len(dataset)), desc="Waiting-debate"):
    word = dataset[idx]
    file_path = prepath + word + datapath
    true_labels = prepath + word + goldpath
    pre_path = prepath + word + "/test.pred.txt"

    text = read_text_from_file(file_path)

    results, output = call_model_per_line(text, idx)
    labels = read_labels_from_file(true_labels)

    precision += precision_score(labels, results) 
    recall += recall_score(labels, results)
    f1 += f1_score(labels, results)

    save_list_to_file(output, pre_path)

save_list_to_file(f1list, "")
f1 /= 20.0
precision /= 20.0
recall /= 20.0

print("-------End-------\n")

print(f"Precision: {precision:.4f}")
print(f"Recall: {recall:.4f}")
print(f"F1 Score: {f1:.4f}\n")