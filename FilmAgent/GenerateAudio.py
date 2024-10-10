import re
import os
import requests
import random
from util import *
from tqdm import tqdm
from LLMCaller import GPTTTS
# TO DO
Script_path = f"/path/to/script.json"
actos_path = f"/path/to/actors_profile.json"
Audio_path = f"The path to the folder where the audio files are stored."
# TO DO
if not os.path.exists(Audio_path):
    os.makedirs(Audio_path)


# ChatTTS
url = "http://xxx.xxx.xxx.xxx:xxxx/" # The API path where the chattts service is deployed
Chat_Speaker_female = [0, 1, 2, 3, 4]
Chat_Speaker_male = [0, 1, 2, 3, 4]
random.shuffle(Chat_Speaker_female) 
random.shuffle(Chat_Speaker_male) 
invalid_characters_map = {
    "!": ".",
    "?": ".",
    "'": ",",
    ':': ',',
    ';': ',',
    '!': '.',
    '(': ',',
    ')': ',',
    '[': ',',
    ']': ',',
    '>': ',',
    '<': ',',
    '-': ','
}
# OpenAI TTS
GPT_Speaker_female = ["alloy", "fable", "nova", "shimmer"]
GPT_Speaker_male = ["echo","onyx" ]
random.shuffle(GPT_Speaker_female) 
random.shuffle(GPT_Speaker_male) 


# Clear all audio generated last time
for filename in os.listdir(Audio_path):
    file_path = os.path.join(Audio_path, filename)
    os.remove(file_path)


# GPT: Assign a voice to each character
# name2gptspeaker = {}
# roles = read_json(actos_path)
# for role in roles:
#     if role['gender'].lower() == "male":
#         name2gptspeaker[role['name']] = GPT_Speaker_male[0]
#         GPT_Speaker_male.pop(0)
#     else:
#         name2gptspeaker[role['name']] = GPT_Speaker_female[0]
#         GPT_Speaker_female.pop(0)


# ChatTTS: Assign a voice to each character
name2chatspeaker = {}
roles = read_json(actos_path)
for role in roles:
    name2chatspeaker[role['name']] = {}
    if role['gender'].lower() == "male":
        name2chatspeaker[role['name']]['id'] = Chat_Speaker_male[0]
        name2chatspeaker[role['name']]['gender'] = "male"
        Chat_Speaker_male.pop(0)
    else:
        name2chatspeaker[role['name']]['id'] = Chat_Speaker_female[0]
        name2chatspeaker[role['name']]['gender'] = "female"
        Chat_Speaker_female.pop(0)
        


script = read_json(Script_path)
lines = []
for scene in script:
    for event in scene['scene']:
        if "content" in event.keys():
            l = event["content"]
            if contains_digit(l):
                l = translate_digit(l)
            lines.append({"speaker": event["speaker"], "content": prompt_format(l, invalid_characters_map)+"[uv_break]"})


Flag = "ChatTTS" # GPT or ChatTTS

params_infer_code =  {'prompt':'[speed_3]', 'temperature':0.3,'top_P':0.9, 'top_K':1}
params_refine_text = {'prompt':'[oral_2][laugh_4][break_6]'}
print(name2chatspeaker)

for line in tqdm(lines):
    # if Flag == "GPT":
    #     response = GPTTTS(line['content'], name2gptspeaker[line['speaker']])
    #     response.stream_to_file(cretae_new_path(Audio_path, "mp3"))
        
    if Flag == "ChatTTS":
        response = requests.post(url, json={"gender": name2chatspeaker[line['speaker']]['gender'], "text": line['content'], "id": name2chatspeaker[line['speaker']]['id'], "params_infer_code": params_infer_code, "params_refine_text": params_refine_text})
        # response = requests.post(url, json={"gender": line['gender'], "text": line['text'], "id": line['id'], "params_infer_code": params_infer_code, "params_refine_text": params_refine_text})
        if response.status_code == 200:
            content_disposition = response.headers.get("Content-Disposition")
            filename = re.findall("filename=\"(.+)\"", content_disposition)
            filename = filename[0]
            with open(os.path.join(Audio_path, filename), "wb") as f:
                f.write(response.content)
        else:
            print(f"Failed to create item. Status code: {response.status_code}")