# -*- coding: utf-8 -*-
import io, base64, torch, uvicorn
from PIL import Image
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import (Qwen2_5_VLForConditionalGeneration, AutoProcessor,
                          BitsAndBytesConfig)
from peft import PeftModel

MODEL_PATH = "/root/autodl-tmp/gui-agent/models/models/Qwen--Qwen2.5-VL-7B-Instruct/snapshots/master"
ADAPTER_PATH = "/root/autodl-tmp/gui-agent/models/lora-adapter-real"

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    MODEL_PATH, torch_dtype=torch.bfloat16, quantization_config=bnb, device_map="auto")
processor = AutoProcessor.from_pretrained(MODEL_PATH)
model = PeftModel.from_pretrained(model, ADAPTER_PATH)
model.eval()

app = FastAPI()

class ChatReq(BaseModel):
    image_b64: str = ""
    ocr_text: str = ""
    task: str = ""
    history: list = []

@app.post("/chat")
def chat(req: ChatReq):
    content = []
    image = None
    if req.image_b64:
        image = Image.open(io.BytesIO(base64.b64decode(req.image_b64))).convert("RGB")
        content.append({"type": "image", "image": image})
    text = f"任务:{req.task}\n历史:{req.history}\n输出本步动作"
    content.append({"type": "text", "text": text})
    messages = [{"role": "user", "content": content}]
    prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=prompt, images=[image] if image else None,
                       return_tensors="pt").to(model.device)
    out = model.generate(**inputs, max_new_tokens=64, do_sample=False)
    reply = processor.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    return {"reply": reply}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=6006)
