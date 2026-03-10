import re
import base64
import torch
from typing import Tuple
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
from .prompt import GROUNDING


class UI_TARS():
    def __init__(self, model_path: str="ByteDance-Seed/UI-TARS-1.5-7B"):
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,   # 計算時用 bf16
            bnb_4bit_use_double_quant=True,          # double quant
            bnb_4bit_quant_type="nf4"                # NF4 (QLoRA標準)
        )
        self.processor = AutoProcessor.from_pretrained(model_path, use_fast=True)
        self.model = AutoModelForImageTextToText.from_pretrained(model_path, device_map="auto", dtype=torch.bfloat16, quantization_config=quant_config)

    def inference(self, img_path: str, transcription: str) -> Tuple[int, int]:
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "url": f"data:image/png;base64,{b64}"},
                    {"type": "text", "text": GROUNDING.format(transcription=transcription)}
                ]
            },
        ]
        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device, dtype=torch.bfloat16)

        outputs = self.model.generate(
            **inputs, 
            do_sample=False, 
            max_new_tokens=256,
            pad_token_id=151645, # Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
        )
        output = self.processor.decode(outputs[0][inputs["input_ids"].shape[-1]:])

        # print(output)

        # action = parse_action(output.split("Action: ")[-1].replace("<|im_end|>", ""))
        # print(action)

        x, y = map(int, re.search(r'\((\d+),(\d+)\)', output).groups())
        return x, y
