import json
import os
import re
import Levenshtein
from LLMCaller import *

def read_json(input_path):
    with open(input_path, 'r', encoding='utf-8',errors='ignore') as f:
        r = toString(json.load(f))
        r = r.replace("�",".")
        return json.loads(r)


def write_json(output_path, output_data):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False)


def read_prompt(input_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        return f.read()
    
    
def log_prompt(prompt_log_path, input):
    if not isinstance(input, str):
        input = toString(input)
    with open(prompt_log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"{input}\n")
        log_file.write("#######################################################\n")


def cretae_new_path(path, filetype):
    if not os.path.exists(path):
        os.makedirs(path)
    files = os.listdir(path)
    if len(files) == 0:
        return os.path.join(path, f'0.{filetype}')
    else:
        max = 0
        for file in files:
            max = max if max>=int(os.path.splitext(file)[0]) else int(os.path.splitext(file)[0])
        return os.path.join(path, str(max+1) + f'.{filetype}')
    

def find_latest_file(path):
    files = os.listdir(path)
    max = 0
    f = ""
    for file in files:
        if max < int(os.path.splitext(file)[0]):
            max = int(os.path.splitext(file)[0])
            f = file

    return os.path.join(path, f)


def toString(input):
    return json.dumps(input, ensure_ascii=False, separators=(",", ":"))          
       
        
def prompt_format(prompt, params):
    text = prompt
    for key, value in params.items():
        if isinstance(value, (dict, list)):
            value = toString(value)
        if isinstance(value, (int, float)):
            value = str(value)
        text = text.replace(key, value)
    return text
    
    
def GPTResponse2JSON(response):
    json_string = response
    prompt = f"Modify the following string so that it can be correctly parsed by the json.loads() method:\n{json_string}\n\nYou should just return the modified string."
    if "```json" in json_string:
        json_string = json_string.replace("```","")
        json_string = json_string.replace("json","")
        json_string = json_string.strip()
    try:
        result = json.loads(json_string)
    except:
        result = json.loads(clean_text(GPTCall(prompt)))

    return result


def clean_text(text):
    # Only keep json content
    pattern = r"```json(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        text =  match.group(1)
    
    # Remove some unexpected characters    
    punctuation_map = {
        "，": ",",
        "。": ".",
        "！": "!",
        "？": "?",
        "：": ":",
        "；": ";",
        "“": "\"",
        "”": "\"",
        "‘": "\'",
        "’": "\'",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "——": "-",
        "…": "...",
        "–": "-",
        "—": "-",
        "�": "."
    }
    pattern = r'[^a-zA-Z0-9\s\.,!?;:\'"\-({})\[\]]'
    for chinese, english in punctuation_map.items():
        text = text.replace(chinese, english)
    text = re.sub(pattern, '', text)
    text = text.strip()
    
    return text


def get_number(text):
    pattern = r'[^0-9]'
    text = re.sub(pattern, '', text)
    return int(text)


def contains_digit(string):
    return bool(re.search(r'\d', string))


def translate_digit(string):
    prompt = f"Convert the numbers in the following sentence into correct English expressions:\n\n{string}\n\nYour answer should only contain the following JSON content:\n" + '{"Converted-sentence": "..."}'
    result = GPTResponse2JSON(GPTCall(prompt))
    return list(result.values())[0]


def calculate_similarity(str1, str2):
    distance = Levenshtein.distance(str1.lower(), str2.lower())
    max_len = max(len(str1), len(str2))
    similarity = 1 - distance / max_len
    return similarity


def return_most_similar(string, string_list):
    max_similarity = 0
    tgt = 0
    for id,item in enumerate(string_list):
        current_similarity = calculate_similarity(string, item)
        if current_similarity > max_similarity:
            max_similarity = current_similarity
            tgt = id
    
    return string_list[tgt]


def GetValueFromDictArray(dictarray, key1, key2, value1):
    for item in dictarray:
        if item[key1] == value1:
            return item[key2]
