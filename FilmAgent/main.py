from util import *
from LLMCaller import *
from typing import Dict, List, Union
import random
import copy
import argparse


# TO DO
ROOT_PATH = "/path/to/FilmAgent"
# TO DO

class FilmCrafter:
    
    def __init__(self, topic: str) -> None:
        self.topic = topic
        self.log_path = cretae_new_path(os.path.join(ROOT_PATH, "Logs"), "txt")
        self.profile_path = os.path.join(ROOT_PATH, "Script\\actors_profile.json") 
        self.action_description_path = os.path.join(ROOT_PATH, "Locations\\actions.txt")
        self.shot_description_path = os.path.join(ROOT_PATH, "Locations\\shots.txt")
        # scenes
        self.scene_path = os.path.join(ROOT_PATH, "Script\scenes_1.json") 
        # + lines
        self.scene_path_1 = os.path.join(ROOT_PATH, "Script\scenes_2.json") 
        # + positions
        self.scene_path_2 = os.path.join(ROOT_PATH, "Script\scenes_3.json") 
        # + actions
        self.scene_path_3 = os.path.join(ROOT_PATH, "Script\scenes_4.json")
        # stage1_verify
        self.scene_path_4 = os.path.join(ROOT_PATH, "Script\scenes_5.json")
        # stage2_verify
        self.scene_path_5 = os.path.join(ROOT_PATH, "Script\scenes_6.json") 
        # + movement
        self.scene_path_6 = os.path.join(ROOT_PATH, "Script\scenes_7.json") 
        # + shot (stage3_verify)
        self.scene_path_7 = os.path.join(ROOT_PATH, "Script\scenes_8.json") 
        # The final script
        self.script_path = cretae_new_path(os.path.join(ROOT_PATH, "Script\script"), "json")
        
        # director's shot annotation
        self.director_shot_path = os.path.join(ROOT_PATH, "Script\director_shot.json")
        # cinematographer's shot annotation
        self.cinematographer_shot_path = os.path.join(ROOT_PATH, "Script\cinematographer_shot.json")

        # The maximum number of characters in a film
        self.character_limit = 4
        # The maximum number of scenes in a film
        self.scene_limit = 3
        # The maximum number of discussions between director and screenwriter
        self.stage1_verify_limit = 3
        # The maximum number of discussions between director, actor and screenwriter
        self.stage2_verify_limit = 3
        # The maximum number of discussions between director and cinematographer
        self.stage3_verify_limit = 4
        

    def call(self, identity: str, params: Dict, trans2json: bool = True) -> Union[str, dict, list]:
        prompt = read_prompt(os.path.join(ROOT_PATH, f"Prompt\{identity}.txt") )
        prompt = prompt_format(prompt, params)
        log_prompt(self.log_path, prompt)
        result = LLMCall(prompt, model)
        if trans2json:
            result = clean_text(result)
            result = GPTResponse2JSON(result)
        log_prompt(self.log_path, result)
        return result

    
    def casting(self):
        '''
            Role: Director

            Behavior: Create the main characters and their bios for the film script.
        '''
        params = {"{topic}": self.topic, "{character_limit}": self.character_limit}
        result = self.call("director_1", params)
        write_json(self.profile_path, result)
        
        
    def scenes_plan(self):
        '''
            Role: Director

            Behavior:
                Plan the outline of script, include:
                1. The number of scenes.
                2. The characters, location and main plot of each scene.
        '''
        profile = read_json(self.profile_path)
        male_characters = ", ".join(list(map(lambda x: x['name'], 
                                             filter(lambda x: x['gender'].lower() == 'male', profile))))
        female_characters = ", ".join(list(map(lambda x: x['name'], 
                                               filter(lambda x: x['gender'].lower() == 'female', profile))))
        
        params = {"{topic}": self.topic, 
                  "{male_characters}": male_characters,
                  "{female_characters}": female_characters,
                  "{scene_limit}": self.scene_limit}
        result = self.call("director_2", params)
        write_json(self.scene_path, result)
        
        
    def lines_generate(self):
        '''
            Role: Screenwriter

            Behavior: Write lines for the script.
        '''
        scenes = read_json(self.scene_path)
        script_outline = ""
        who = []
        where = []
        what = []
        for id,scene in enumerate(scenes):
            selected_roles = scene[return_most_similar("selected-characters", list(scene.keys()))]
            selected_location = scene[return_most_similar("selected-location", list(scene.keys()))]
            story_plot = scene[return_most_similar("story-plot", list(scene.keys()))]
            who.append(selected_roles)
            where.append(selected_location)
            what.append(story_plot)

            topic = scene[return_most_similar("sub-topic", list(scene.keys()))]
            characters = ", ".join(selected_roles)
            plot = story_plot
            location = selected_location
            goal = scene[return_most_similar("dialogue-goal", list(scene.keys()))]

            script_outline = script_outline + f"{id + 1}. **Scene {id + 1}**:\n   - topic: {topic}\n   - involved characters: {characters}\n   - plot: {plot}\n   - location: {location}\n   - dialogue goal: {goal}\n\n"
    
        params = {"{script_outline}": script_outline.strip()}
        result = self.call("screenwriter_1", params) 
        
        lines = []
        assert len(result) == len(scenes)
        for j in range(len(scenes)):
            line = {}
            line['scene_information'] = {}
            line['scene_information']['who'] = who[j]
            line['scene_information']['where'] = where[j]
            line['scene_information']['what'] = what[j]
            line['dialogues'] = result[j][return_most_similar("scene-dialogue", list(result[j].keys()))]
            lines.append(line)
        write_json(self.scene_path_1, lines)

                
                
    def position_mark(self):
        '''
            Role: Screenwriter

            Behavior: Choose an appropriate initial position for each character in each scene of the script.
        '''
        scenes = read_json(self.scene_path_1)
        script_information = ""
        optional_positions = ""
        for id,scene in enumerate(scenes):
            i = id + 1
            who = scene['scene_information']['who']
            where = scene['scene_information']['where']
            what = scene['scene_information']['what']

            script_information = script_information + f"{i}. **Scene {i}**:\n   - characters: {who}\n   - location: {where}\n   - plot: {what}\n\n"
            
            position_path = os.path.join(ROOT_PATH, f"Locations\{where}\position.json")
            positions = read_json(position_path)
            normal_position = [item for item in positions if item['fixed_angle'] == False]
            # This "if judgment" is related to the position, and camera settings in Unity.
            if len(who) >= len(positions) - len(normal_position) + 2:
                p = ""
                for it,position in enumerate(positions):
                    j = it + 1
                    p = p + f"   - Position {j}: " + position['description'] + '\n'
            else:
                p = ""
                for it,position in enumerate(normal_position):
                    j = it + 1
                    p = p + f"   - Position {j}: " + position['description'] + '\n'                    
            optional_positions = optional_positions + f"{i}. **Positions in {where}**:\n{p}\n"
                
        params = {"{script_information}": script_information.strip(), 
                        "{optional_positions}": optional_positions.strip()}
        result = self.call("screenwriter_2", params)
        
        assert len(result) == len(scenes)
        for j in range(len(scenes)):
            scenes[j]["initial position"] = result[j][return_most_similar("scene-position", list(result[j].keys()))]
        write_json(self.scene_path_2, scenes)
                            
                            
                            
    def action_mark(self):
        '''
            Role: Screenwriter

            Behavior: Choose appropriate actions for the characters engaged in the dialogue.
        '''
        scenes = read_json(self.scene_path_2)
        all_actions = read_prompt(self.action_description_path)
        data = []
        for scene in scenes:
            position_path = os.path.join(ROOT_PATH, f"Locations\{scene['scene_information']['where']}\position.json")
            positions = read_json(position_path)
            
            ini = ""
            for id,item in enumerate(scene['initial position']):
                if [it['sittable'] for it in positions if get_number(it['id']) == get_number(item['position'])][0]:
                    sit = "sittable"
                else:
                    sit = "unsittable"
                ini = ini + f"   - {item['character']}: " + f"{sit} Position {str(get_number(item['position']))}, standing\n"
            ini = "   " + ini.strip() 
            params = {"{initial}": ini, 
                        "{plot}": scene['scene_information']['what'],
                        "{dialogues}": scene['dialogues'],
                        "{all_actions}": all_actions}
            result = self.call("screenwriter_3", params)

            assert len(result) == len(scene['dialogues'])
            scene['dialogues'] = result
            data.append(scene)
            
        write_json(self.scene_path_3, data)
    
    
    
    def find_unknown_actions(self, scenes: List) -> List:
        '''
            Input: The complete script

            Output: The list of actions appearing in the script that are not set in Unity.
        '''
        unknown_actions = []
        all_actions = read_json(os.path.join(ROOT_PATH, "Locations\\actions.json"))
        for scene in scenes:
            for line in scene['dialogues']:
                for action in line['actions']:
                    if action['action'] not in all_actions.keys() and action['action'] not in unknown_actions:
                        unknown_actions.append(action['action'])
        
        return unknown_actions
    
    
    
    def stage1_verify(self):
        '''
            Role: Director and Screenwriter

            Behavior: The director and screenwriter have a comprehensive discussion about the script to improve it, focusing on the following three aspects: Action Reasonableness, Theme Consistency, Script Fluency.
        '''
        scenes = read_json(self.scene_path_3)
        current_script = []
        unknown_actions = self.find_unknown_actions(scenes)
        characters_position = ""
        for id,scene in enumerate(scenes):
            new_scene = {}
            new_scene['scene_information'] = scene['scene_information']
            new_scene['initial position'] = scene['initial position']
            new_scene['dialogues'] = []
            for line in scene['dialogues']:
                new_line = copy.deepcopy(line)
                for action in new_line['actions']:
                    action.pop("reasoning")
                new_scene['dialogues'].append(new_line)
            current_script.append(new_scene)
            
            position_path = os.path.join(ROOT_PATH, f"Locations\{scene['scene_information']['where']}\position.json")
            positions = read_json(position_path)
            p = []
            for position in scene['initial position']:
                position_id = get_number(position['position'])
                sittable = "sittable" if positions[position_id-1]['sittable'] else "unsittable"
                p.append(f"{position['character']}'s position: {sittable}")
            characters_position = characters_position + f"{id+1}. **Scene {id+1}**:\n{', '.join(p)}\n\n"

        all_actions = read_prompt(self.action_description_path)
        for i in range(self.stage1_verify_limit):
            params = {"{theme}": self.topic, 
                        "{original_script}": current_script,
                        "{all_actions}": all_actions,
                        "{unknown_actions}": ', '.join(unknown_actions)}
            feedback = self.call("director_3", params, trans2json=False)
            
            params = {"{theme}": self.topic,
                      "{feedback}": feedback, 
                        "{script}": current_script,
                        "{all_actions}": all_actions,
                        "{characters_position}": characters_position}
            revised_script = self.call("screenwriter_4", params)
            current_script = revised_script
            unknown_actions = self.find_unknown_actions(revised_script)
            # If there are still unknown actions, discuss again immediately.
            if len(unknown_actions)>0:
                continue
            
            params = {"{feedback}": feedback, 
                        "{revised_script}": revised_script}
            verify = self.call("director_4", params, trans2json=False)
            if verify.find("finalize") == -1:
                continue
            verify = verify[verify.find("finalize"):]
            if "True" in verify or "true" in verify:
                break

        write_json(self.scene_path_4, revised_script)
            
            
    
    def stage2_verify(self):
        '''
            Role: Actor, Director and Screenwriter

            Behavior: The actors suggest minor adjustments to the script lines, and the director and screenwriter discuss the revisions.
        '''
        scenes = read_json(self.scene_path_4)
        profiles = read_json(self.profile_path)
        feedback = {}
        scenes_for_actor = []
        for scene in scenes:
            item = {}
            item['scene_information'] = scene[return_most_similar('scene_information', list(scene.keys()))]
            item["dialogues"] = []
            for line in scene['dialogues']:
                new_line = {}
                new_line['speaker'] = line['speaker']
                new_line['content'] = line['content']
                item["dialogues"].append(new_line)
            scenes_for_actor.append(item)
            
        for profile in profiles:
            params = {"{character}": profile['name'], 
                        "{profile}": profile,
                        "{script}": scenes_for_actor}
            result = self.call("actor", params, trans2json=False)
            feedback[profile['name']] = result
            
        suggestions = ""
        for name, suggestion in feedback.items():
            suggestions = suggestions + f"   - **{name}**: {suggestion}\n"
        params = {"{suggestions}": suggestions,
                  "{character_profiles}": profiles,
                  "{draft_script}": scenes}
        result = self.call("director_5", params)
        
        if result[return_most_similar("adopted-suggestions", list(result.keys()))] == "None":
            write_json(self.scene_path_5, scenes)
        else:
            current_script = scenes_for_actor
            adopted_suggestions = result[return_most_similar("adopted-suggestions", list(result.keys()))]
            for sugg in adopted_suggestions:
                sugg.pop("reason")
            for i in range(self.stage2_verify_limit):
                params = {"{feedback}": adopted_suggestions, 
                            "{script}": current_script}
                revised_script = self.call("screenwriter_5", params)
                current_script = revised_script
                
                params = {"{feedback}": adopted_suggestions, 
                            "{revised_script}": revised_script}
                verify = self.call("director_6", params, trans2json=False)
                verify = verify[verify.find("finalize"):]
                if "True" in verify or "true" in verify:
                    break
                
            assert len(revised_script) == len(scenes)
            for id,scene in enumerate(scenes):
                assert len(scene['dialogues']) == len(revised_script[id]['dialogues'])
                for it,line in enumerate(scene['dialogues']):
                    assert line['speaker'] == revised_script[id]['dialogues'][it]['speaker']
                    line['content'] = revised_script[id]['dialogues'][it]['content']
            
            write_json(self.scene_path_5, scenes)

    
         
    def is_keep_standing(self, lines, character):
        '''
            Description: Check if the character remains standing throughout the script. 

            Input: The complete script, a character's name

            Output: True or False
        '''
        for line in lines:
            actions = line['actions']
            for action in actions:
                if action['character'] == character and action['state'] == 'sitting':
                    return False
        return True
    
    
    def moveable_options(self, scene):
        '''
            Input: The complete script

            Output:
                1. All movable characters (i.e., the characters that remain standing throughout the script)
                2. All positions that character can move to (i.e., the unoccupied positions)
        '''
        position_path = os.path.join(ROOT_PATH, f"Locations\{scene[return_most_similar('scene_information', list(scene.keys()))]['where']}\position.json")
        positions = read_json(position_path)
        occupied_positions = [get_number(item['position']) for item in scene[return_most_similar('initial position', list(scene.keys()))]]
        unoccupied_positions = [f"{item['id']}: {item['description']}" for item in positions if get_number(item['id']) not in occupied_positions]
        if len(unoccupied_positions) == 0:
            return None, None
        
        who = scene[return_most_similar('scene_information', list(scene.keys()))]['who']
        moveable_characters = []
        for character in who:
            if self.is_keep_standing(scene['dialogues'], character):
                moveable_characters.append(character)
        if len(moveable_characters) == 0:
            return None, None
                
        return moveable_characters, unoccupied_positions
        
    
    def move_mark(self):
        '''
            Role: Director

            Behavior: The director adds appropriate character movements into the script.
        '''
        scenes = read_json(self.scene_path_5)
        data = []
        for scene in scenes:
            moveable_characters, unoccupied_positions = self.moveable_options(scene)
            moved_charatcter, moveto_position = None, None
            if moveable_characters:
                move2destination = ""
                for pn in unoccupied_positions:
                    move2destination = move2destination + f"   - {pn}\n"
                move2destination = "   " + move2destination.strip()
                lines = []
                for id in range(len(scene['dialogues'])):
                    lines.append(f"<Insertion Position {id}>")
                    item = {}
                    item['speaker'] = scene['dialogues'][id]['speaker']
                    item['content'] = scene['dialogues'][id]['content']
                    lines.append(item)
                params = {"{moveable_characters}": moveable_characters,
                                "{story}": scene[return_most_similar('scene_information', list(scene.keys()))]['what'],
                                "{lines}": lines,
                                "{destinations}": move2destination,
                                "{current_positions}": scene[return_most_similar('initial position', list(scene.keys()))]}
                result = self.call("director_7", params)
                
                if 'insertion' in result.keys():
                    moved_charatcter = result['move']['character']
                    moveto_position = result['move']['destination']
                    scene['dialogues'].insert(get_number(result['insertion'][return_most_similar('insertion position', list(result['insertion'].keys()))]), result)
            
            # Update the characters' position in real time
            position_change = False
            for line in scene['dialogues']:
                if "move" not in line.keys():
                    line['current position'] = scene[return_most_similar('initial position', list(scene.keys()))]
                else:
                    position_change = True
                    line['current position'] = scene[return_most_similar('initial position', list(scene.keys()))]
                    continue
                if position_change:
                    line['current position'] = [item if item['character'] !=  moved_charatcter else {'character': moved_charatcter, 'position': moveto_position} for item in line['current position']]
                    
            data.append(scene)
            
        write_json(self.scene_path_6, data)
        
        
    def shot_mark(self):
        '''
            Input: None

            Output:
                1. Director's shot annotations
                2. Cinematographer's shot annotations
                3. The complete script before adding shot annotations
                4. The script after inserting the shot annotation points.
        '''
        scenes = read_json(self.scene_path_6)
        script = {}
        for ID,scene in enumerate(scenes):
            I = ID + 1
            script[f'scene {I}'] = []
            for id,item in enumerate(scene['dialogues']):
                line = {}
                i = id + 1
                if "speaker" in item.keys():
                    line['dialogue'] = f"{item['speaker']}: {item['content']}"
                    line['actions'] = item['actions']
                    # line['plot'] = ' '.join([it['reason'] for it in item['actions']])
                    line[f'selected-shot-{i}'] = "..."
                else:
                    line['move'] = {}
                    line['move']['character'] = item['move']['character']
                    line['move']['destination'] = item['move']['destination']
                    line[f'selected-shot-{i}'] = "..."
                script[f'scene {I}'].append(line)
                
        all_shots = read_prompt(self.shot_description_path)   
        params = {"{script}": script, "{all_shots}": all_shots}
        result1 = self.call("cinematographer", params)
        result2 = self.call("cinematographer", params)
        # result2 = self.call("director_8", params)
        for scene_id, scene in result1.items():
            for shot_id, shot in scene.items():
                shot.pop("reasoning")

        for scene_id, scene in result2.items():
            for shot_id, shot in scene.items():
                shot.pop("reasoning")
        
        write_json(self.director_shot_path, result2)
        write_json(self.cinematographer_shot_path, result1)

        return script, result1, result2, scenes


    def revise_shot_annotation(self, src, feedback):
        '''
            Input: Original shot annotation, revision suggestion

            Output: Revised shot annotation
        '''
        new = src
        for scene_id, scene in new.items():
            for shot_id, shot in scene.items():
                if shot['shot'] != feedback[scene_id][shot_id]['shot']:
                    continue

                need_update = feedback[scene_id][shot_id][return_most_similar("need update", list(feedback[scene_id][shot_id].keys()))]
                if isinstance(need_update, str) and need_update.lower() == "false":
                    continue
                if isinstance(need_update, bool) and not need_update:
                    continue
                shot['shot'] = feedback[scene_id][shot_id][return_most_similar("updated shot", list(feedback[scene_id][shot_id].keys()))]
                
        return new
    
    
    
    def stage3_verify(self):
        '''
            Role: Director and Cinematographer

            Behavior: The director and the cinematographer provide their own shot annotations, then discuss and revise them together, and finally, the director selects the better one.
        '''
        script, shot_mark_cinematographer, shot_mark_director, scenes = self.shot_mark()
        current_shot_c, current_shot_d = shot_mark_cinematographer, shot_mark_director
        all_shots = read_prompt(self.shot_description_path)
        for i in range(self.stage3_verify_limit):
            params = {"{identity_1}": "Director",
                      "{identity_2}": "Cinematographer",
                      "{script}": script,
                      "{shot_annotation}": current_shot_c,
                      "{all_shots}": all_shots
                      }
            result1 = self.call("shot_review", params)
            current_shot_c = self.revise_shot_annotation(current_shot_c, result1)
            
            params = {"{identity_1}": "Cinematographer",
                      "{identity_2}": "Director",
                      "{script}": script,
                      "{shot_annotation}": current_shot_d,
                      "{all_shots}": all_shots
                      }
            result2 = self.call("shot_review", params)
            current_shot_d = self.revise_shot_annotation(current_shot_d, result2)
        
        params = {"{shot_annotation_1}": current_shot_d,
                    "{shot_annotation_2}": current_shot_c,
                    "{script}": script,
                    "{all_shots}": all_shots
                    }
        result = self.call("director_9", params)
        last_shots = current_shot_d if result['better']=="1" else current_shot_c
        # last_shots = current_shot_d if result['better'].lower()=="director" else current_shot_c
        
        assert len(list(last_shots.keys())) == len(scenes)
        for id in range(len(list(last_shots.keys()))):
            i = id + 1
            assert len(list(last_shots[f'scene {i}'].keys())) == len(scenes[id]['dialogues'])
            for key,value in last_shots[f'scene {i}'].items():
                scenes[id]['dialogues'][get_number(key)-1]['selected shot'] = value[return_most_similar('shot', list(value.keys()))]
            
            
        write_json(self.scene_path_7, scenes)
        
    
    # Used for clean_script()
    def process_action(self, actions, v_characters, v_actions):
        new_actions = []
        for item in actions:
            new_item = {}
            new_item['character'] = return_most_similar(item['character'], v_characters)
            new_item['state'] = return_most_similar(item['state'], ['standing', 'sitting'])
            
            new_item['action'] = return_most_similar(item['action'], v_actions)
            if new_item['state'] == "standing" and ("Standing" in new_item['action'] or new_item['action'] == "Joyful Jump" or new_item['action'] == "Sit Down"):
                if new_item['action'] == "Standing Talking":
                    new_item['action'] = "Standing Talking " + str(random.randint(1, 6))
                if new_item['action'] == "Standing Angry":
                    new_item['action'] = "Standing Angry " + str(random.randint(1, 4))
                if new_item['action'] == "Standing Arguing":
                    new_item['action'] = "Standing Arguing " + str(random.randint(1, 2))
                if new_item['action'] == "Standing Agree":
                    new_item['action'] = "Standing Agree " + str(random.randint(1, 2))
                new_actions.append(new_item)
            elif new_item['state'] == "sitting" and ("Sitting" in new_item['action'] or new_item['action'] == "Stand Up"):
                if new_item['action'] == "Sitting Talking":
                    new_item['action'] = "Sitting Talking " + str(random.randint(1, 2))
                new_actions.append(new_item)
            else:
                pass
        return new_actions
    
    
    # Used for clean_script()  
    def process_shot(self, info, location, shot, v_shots):
        shot = return_most_similar(shot, v_shots)
        if shot == "Pan Shot":
            return "Pan Shot 1"
        elif shot == "Track Shot":
            return "Track Shot " + str(random.randint(1, int(info[location]['track'])))
        elif shot == "Long Shot":
            return "Long Shot " + str(random.randint(1, int(info[location]['long'])))
        else:
            return shot
        
        
    def clean_script(self):
        '''
            Description: Only keep the necessary information in the script and perform certain checks to avoid errors when executing the script in Unity.
        '''
        scenes = read_json(self.scene_path_7)
        profiles = read_json(self.profile_path)
        v_characters = [item['name'] for item in profiles]
        info = read_json(os.path.join(ROOT_PATH, "Locations\\rotateandtrack.json"))
        v_locations = [location for location in info.keys()]
        info_1 = read_json(os.path.join(ROOT_PATH, "Locations\\actions.json"))
        v_actions = [action for action in info_1.keys()]
        info_2 = read_json(os.path.join(ROOT_PATH, "Locations\\shots.json"))
        v_shots = [shot for shot in info_2.keys()]
        
        data = []
        for scene in scenes:
            new_scene = {}
            scene_information_key = return_most_similar('scene_information', list(scene.keys()))       
            new_scene['scene information'] = scene[scene_information_key]
            
            # verify
            for role in new_scene['scene information']['who']:
                role = return_most_similar(role, v_characters)
            new_scene['scene information']['where'] = return_most_similar(new_scene['scene information']['where'], v_locations)
            # verify    
            
            new_scene['scene'] = []
            for line in scene['dialogues']:
                new_line = {}
                selected_shot_key = return_most_similar('selected shot', list(line.keys()))
                current_position_key = return_most_similar('current position', list(line.keys()))
                # verify
                if 'speaker' in line.keys():
                    new_line['speaker'] = return_most_similar(line['speaker'], v_characters)
                    new_line['content'] = line['content']
                    new_line['actions'] = self.process_action(line['actions'], v_characters, v_actions)
                    new_line['shot'] = self.process_shot(info, scene[scene_information_key]['where'], line[selected_shot_key], v_shots)
                    new_line['current position'] = line[current_position_key]
                else:
                    new_line['move'] = {}
                    new_line['move']['character'] = return_most_similar(line['move']['character'], v_characters)
                    new_line['move']['destination'] = "Position " + str(get_number(line['move']['destination']))
                    new_line['shot'] = self.process_shot(info, scene[scene_information_key]['where'], line[selected_shot_key], v_shots)
                    new_line['current position'] = line[current_position_key]
                # verify
                    
                # verify
                for item in new_line['current position']:
                    item['character'] = return_most_similar(item['character'], v_characters)
                    item['position'] = "Position " + str(get_number(item['position']))
                # verify
                
                new_scene['scene'].append(new_line)
                
            initial_position_key = return_most_similar('initial position', list(scene.keys()))
            new_scene['initial position'] = scene[initial_position_key]
            for ini in new_scene['initial position']:
                ini['character'] = return_most_similar(ini['character'], v_characters)
                ini['position'] = "Position " + str(get_number(ini['position']))
            data.append(new_scene)
            
        write_json(self.script_path, data)
                    
                    
                    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', help="LLM to be called", type=str)
    args = parser.parse_args()
    model = args.model
    
    f = FilmCrafter(topic = "Reconcilation in a friend reunion")
    print("Characters selecting >>>")
    f.casting()
    print("Scenes planning >>>")
    f.scenes_plan()
    print("Lines generating >>>")
    f.lines_generate()
    print("Positions marking >>>")
    f.position_mark()
    print("Actions marking >>>")
    f.action_mark()
    print("Director discusses with screenwriter about the script >>>")
    f.stage1_verify()
    print("Actors give comments on the lines >>>")
    f.stage2_verify()
    print("Movement marking >>>")
    f.move_mark()
    print("Director discusses with cinematographer about the shots >>>")
    f.stage3_verify()
    print("Script cleaning >>>")
    f.clean_script()
