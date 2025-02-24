from util import *
from LLMCaller import *
from typing import Dict, List, Union

# TO DO
ROOT_PATH = "/path/to/FilmAgent"
model = "gpt-4o"
# TO DO

topics=["Reconcilation in a friend reunion", "A quarrel and breakup scene", "Casual meet-up with an old friend", "Emergency meeting after a security breach", "Late night brainstorming for a startup", "Family argument during dinner", "Emotional farewell at the roadside", "Heated debate over investments in the office", "Heated family discussion ending in a heartfelt apology", "Office gossip turning into a major understanding", "Celebratory end of project cheers with team members", "Planning a secret escape from a mundane routine", "Unexpected guest crashes a small house party", "An employee's emotional breakdown after being terminated", "Confession of a long-held secret among close friends"]

class FilmCrafter:
    
    def __init__(self, topic: str, ID) -> None:
        self.topic = topic
        self.store_path = os.path.join(ROOT_PATH, f"store\cot\{ID}")
        self.log_path = os.path.join(self.store_path, "prompt.txt")
        self.profile_path = os.path.join(self.store_path, "actors_profile.json") 
        self.action_description_path = os.path.join(ROOT_PATH, "Locations\\actions.txt")
        self.shot_description_path = os.path.join(ROOT_PATH, "Locations\\shots.txt")
        self.script_path = os.path.join(self.store_path, "script.json")

        # The maximum number of characters in a film
        self.character_limit = 4
        
        if not os.path.exists(self.store_path):
            os.makedirs(self.store_path) 
        

    def call(self, identity: str, params: Dict, trans2json: bool = True) -> Union[str, dict, list]:
        prompt = read_prompt(os.path.join(ROOT_PATH, f"Prompt\COT_Prompt\{identity}.txt") )
        prompt = prompt_format(prompt, params)
        log_prompt(self.log_path, prompt)
        result = LLMCall(prompt, model)
        if trans2json:
            result = clean_text(result)
            result = GPTResponse2JSON(result)
        log_prompt(self.log_path, result)
        return result

    
    def casting(self):
        params = {"{topic}": self.topic, "{character_limit}": self.character_limit}
        result = self.call("director_1", params)
        write_json(self.profile_path, result)
        
        
    def script_(self):
        profile = read_json(self.profile_path)
        male_characters = ", ".join(list(map(lambda x: x['name'], 
                                             filter(lambda x: x['gender'].lower() == 'male', profile))))
        female_characters = ", ".join(list(map(lambda x: x['name'], 
                                               filter(lambda x: x['gender'].lower() == 'female', profile))))
        optional_positions = ""
        base_path = os.path.join(ROOT_PATH, "Locations")
        for entry in os.listdir(base_path):
            full_path = os.path.join(base_path, entry)
            if os.path.isdir(full_path):
                ps = json.dumps(read_json(os.path.join(full_path, "position.json")))
                optional_positions = optional_positions + f"**{entry}**: {ps}\n"
                
        all_actions = read_prompt(self.action_description_path)
        all_shots = read_prompt(self.shot_description_path)

        params = {"{topic}": self.topic, 
                  "{male_characters}": male_characters,
                  "{female_characters}": female_characters,
                  "{profiles}": profile,
                  "{optional_positions}": optional_positions,
                  "{all_actions}": all_actions,
                  "{all_shots}": all_shots
                  }
        result = self.call("script", params)
        write_json(self.script_path, result)

                    
if __name__ == '__main__':
    id=14
    f = FilmCrafter(topic = topics[id-1], ID=id)
    f.casting()
    f.script_()
    
