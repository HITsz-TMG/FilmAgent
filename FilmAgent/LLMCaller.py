import openai
from openai import OpenAI


client_gpt = OpenAI(api_key = "<OpenAI API Key>")
client_deepseek = OpenAI(api_key = "<DeepSeek API Key>", base_url="https://api.deepseek.com")



def LLMCall(prompt, model):
    counter = 0
    result = "api调用失败"
    if "gpt" in model:
        client = client_gpt
    if "deepseek" in model:
        client = client_deepseek
    while counter < 3:
        try:
            completion = client.chat.completions.create(
                model = model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )
            result = completion.choices[0].message.content
            print(f"%%%%%%%%%%%%%%%%%%%%%%%%\n{result}\n%%%%%%%%%%%%%%%%%%%%%%%")
            break
        
        except Exception as e:
            print(e)
            counter += 1
            
    return result




def GPTTTS(text, role):
    client = client_gpt
    response = client.audio.speech.create(
        model = "tts-1",
        voice = role,
        input = text,
        response_format = "mp3"
    )
    
    return response
