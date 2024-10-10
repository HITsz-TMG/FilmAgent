import os
import openai
from openai import OpenAI


api_key = "xxxxxxxxxxxxxx"
organization = "xxxxxxxxxxxxxx"

def GPTCall(prompt):
    counter = 0
    result = "api调用失败"
    while counter < 3:
        try:
            openai.api_key = api_key
            openai.organization = organization
            client = OpenAI(api_key = api_key, organization = organization)
            completion = client.chat.completions.create(
                model = "gpt-4o",
                # model = "gpt-3.5-turbo",
                # model="gpt-4-1106-preview",
                messages=[
                    {"role": "user", "content": prompt},
                ]
            )
            result = completion.choices[0].message.content
            print(f"%%%%%%%%%%%%%%%%%%%%%%%%\n{result}\n%%%%%%%%%%%%%%%%%%%%%%%")
            break
        
        except Exception as e:
            print(e)
            counter += 1
            
    return result


def GPTTTS(text, role):
    
    openai.api_key = api_key
    openai.organization = organization
    client = OpenAI(api_key = api_key, organization = organization)
    response = client.audio.speech.create(
        model = "tts-1",
        voice = role,
        input = text,
        response_format = "mp3"
    )
    
    return response