from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
import uvicorn
import torch
import soundfile
import ChatTTS
import json
import os

app = FastAPI()
ROOT = "/Path to/TTS"

torch._dynamo.config.cache_size_limit = 64
torch._dynamo.config.suppress_errors = True
torch.set_float32_matmul_precision('high')

chat = ChatTTS.Chat()
# compile=True works well, but is slower
chat.load_models(source='custom', custom_path=os.path.join(ROOT, "model/ChatTTS"), compile=False)


spk = {"male": [], "female": []}
male_path = os.path.join(ROOT, "spk/male")
for file in os.listdir(male_path):
    t = torch.load(os.path.join(male_path, file))
    spk['male'].append(t)
female_path = os.path.join(ROOT, "spk/female")
for file in os.listdir(female_path):
    t = torch.load(os.path.join(female_path, file))
    spk['female'].append(t)
    
    
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



@app.post("/")
async def AudioGenerate(request: Request):
    params = await request.json()
    speaker = spk[params['gender']][params['id']]

    params_refine_text = params['params_refine_text']
    params_infer_code = params['params_infer_code']
    params_infer_code['spk_emb'] = speaker
    
    print("text: ", params['text'])
    wavs = chat.infer(params['text'],
                #   do_text_normalization=True,
                  skip_refine_text=True,
                  params_refine_text=params_refine_text,
                  params_infer_code=params_infer_code)
    
    file_path = cretae_new_path(os.path.join(ROOT, "Audio"), "wav")
    soundfile.write(file_path, wavs[0][0], 24000)

    return FileResponse(path=file_path, filename=os.path.basename(file_path), media_type='audio/wav')


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8080)
