# -*- coding: utf-8 -*-
import torch
from PIL import Image
from transformers import (Qwen2_5_VLForConditionalGeneration, AutoProcessor,
                          BitsAndBytesConfig)
from peft import PeftModel

MODEL_PATH = "/root/autodl-tmp/gui-agent/models/models/Qwen--Qwen2.5-VL-7B-Instruct/snapshots/master"
ADAPTER_PATH = "/root/autodl-tmp/gui-agent/models/lora-adapter-real"
IMG = "/root/autodl-tmp/gui-agent/data/realdata/img_0.png"
TASK = "打开记事本并输入你好世界"

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)

def ask(model, processor):
    messages = [{"role": "user", "content": [
        {"type": "image", "image": IMG},
        {"type": "text", "text": f"任务:{TASK}\n历史:[]\n输出本步动作"}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=text, images=[Image.open(IMG).convert("RGB")],
                       return_tensors="pt").to(model.device)
    out = model.generate(**inputs, max_new_tokens=64, do_sample=False)
    new_tokens = out[0][inputs["input_ids"].shape[1]:]
    return processor.decode(new_tokens, skip_special_tokens=True).strip()

base = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    MODEL_PATH, torch_dtype=torch.bfloat16, quantization_config=bnb, device_map="auto")
proc = AutoProcessor.from_pretrained(MODEL_PATH)
print("===== 基座（无 LoRA）输出 =====")
print(ask(base, proc))

lora = PeftModel.from_pretrained(base, ADAPTER_PATH)
print("\n===== LoRA 微调后输出 =====")
print(ask(lora, proc))
