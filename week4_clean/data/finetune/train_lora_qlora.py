# -*- coding: utf-8 -*-
import os, json, argparse, torch
from PIL import Image
from torch.utils.data import Dataset as TorchDataset
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model

ap = argparse.ArgumentParser()
ap.add_argument("--epochs", type=int, default=30)
ap.add_argument("--out-dir", default="/root/autodl-tmp/gui-agent/models/lora-adapter-real")
ap.add_argument("--max-pixels", type=int, default=768 * 768)
args = ap.parse_args()

MODEL_PATH = "/root/autodl-tmp/gui-agent/models/models/Qwen--Qwen2.5-VL-7B-Instruct/snapshots/master"
DATA_PATH  = "/root/autodl-tmp/gui-agent/data/realdata/data.jsonl"

model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    MODEL_PATH, torch_dtype=torch.bfloat16,
    quantization_config={"load_in_4bit": True, "bnb_4bit_compute_dtype": torch.bfloat16},
    device_map="auto")
processor = AutoProcessor.from_pretrained(MODEL_PATH)
model = get_peft_model(model, LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM"))
model.print_trainable_parameters()


class VisionDataset(TorchDataset):
    def __init__(self):
        self.items = []
        data_dir = os.path.dirname(DATA_PATH)
        for line in open(DATA_PATH, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            img = os.path.join(data_dir, os.path.basename(r["image"].replace("\\", "/")))
            assert os.path.exists(img), f"缺图: {img}"
            prompt = f"任务:{r['task']}\n历史:{r['history']}\n输出本步动作"
            self.items.append({"image_path": img, "text": prompt, "action": r["action"]})

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        return self.items[idx]


ds = VisionDataset()
print("样本数:", len(ds))


def collate(batch):
    messages = [[
        {"role": "user", "content": [
            {"type": "image", "image": b["image_path"]},
            {"type": "text", "text": b["text"]}]},
        {"role": "assistant", "content": [{"type": "text", "text": b["action"]}]}
    ] for b in batch]
    texts = [processor.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
             for m in messages]
    images = [Image.open(b["image_path"]).convert("RGB") for b in batch]
    out = processor(text=texts, images=images, padding=True,
                    return_tensors="pt", max_pixels=args.max_pixels)
    out["labels"] = out["input_ids"].clone()
    return out


targs = TrainingArguments(
    output_dir=args.out_dir, num_train_epochs=args.epochs,
    per_device_train_batch_size=1, gradient_accumulation_steps=4,
    learning_rate=2e-4, logging_steps=2, save_strategy="epoch",
    bf16=True, fp16=False, optim="adamw_torch",
    remove_unused_columns=False, dataloader_num_workers=0)
trainer = Trainer(model=model, args=targs, train_dataset=ds, data_collator=collate)
trainer.train()
model.save_pretrained(args.out_dir)
processor.save_pretrained(args.out_dir)
print("LoRA 已保存:", args.out_dir)
