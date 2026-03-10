import base64
import torch
import json_repair
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
from .ui_tars.prompt import DEMCOMPOSE, GROUPING


class QwenVL():
    def __init__(self, model_path: str="Qwen/Qwen3-VL-8B-Instruct"):
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,   # 計算時用 bf16
            bnb_4bit_use_double_quant=True,          # double quant
            bnb_4bit_quant_type="nf4"                # NF4 (QLoRA標準)
        )
        self.processor = AutoProcessor.from_pretrained(model_path)
        self.model = AutoModelForImageTextToText.from_pretrained(model_path, device_map="auto", quantization_config=quant_config)
    
    def inference(self, messages: dict) -> str:
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
            temperature=None,
            top_p=None, top_k=None,
            max_new_tokens=1024)
        return self.processor.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
    
    def grouping(self, img_path: str, transcription: str) -> str:
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "url": f"data:image/png;base64,{b64}"},
                    {"type": "text", "text": DEMCOMPOSE.format(transcription=transcription)}
                ]
            },
        ]
        analysis = self.inference(messages)

        messages += [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": analysis}
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": GROUPING}
                ]
            },
        ]
        group = self.inference(messages)

        return analysis, json_repair.loads(group)
 