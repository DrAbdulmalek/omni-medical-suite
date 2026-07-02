# src/ner/fine_tune_jais_ner.py
"""Fine-tune Jais for NER using PEFT LoRA. Requires GPU 24GB+."""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType
from datasets import load_dataset, Dataset
import logging

logger = logging.getLogger(__name__)

class JaisNERFineTuner:
    def __init__(self, model_name="core42/jais-13b-chat"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, device_map="auto", torch_dtype=torch.bfloat16,
            load_in_8bit=True, trust_remote_code=True)
        lora_config = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj","v_proj"],
            lora_dropout=0.05, bias="none", task_type=TaskType.CAUSAL_LM)
        self.model = get_peft_model(self.model, lora_config)

    def prepare_dataset(self, hf_dataset_name="DrAbdulmalek/arabic-medical-ocr-corrections"):
        df = load_dataset(hf_dataset_name, split="train").to_pandas()
        def create_prompt(ex):
            text = ex.get("correct_text","") or ex.get("incorrect_ocr_output","")
            return {"prompt": f"استخرج الكيانات:\n{text}\nكيانات:",
                    "completion": "دواء: -\nمرض: -\nجرعة: -"}
        dataset = Dataset.from_pandas(df)
        return dataset.map(create_prompt)

    def train(self, dataset, output_dir="outputs/jais_ner_finetuned", epochs=3):
        args = TrainingArguments(output_dir=output_dir, num_train_epochs=epochs,
            per_device_train_batch_size=2, gradient_accumulation_steps=8,
            learning_rate=2e-4, fp16=True, save_strategy="epoch",
            logging_steps=10, optim="adamw_8bit", report_to="none")
        trainer = Trainer(model=self.model, args=args, train_dataset=dataset, tokenizer=self.tokenizer)
        logger.info("Starting Jais NER fine-tuning...")
        trainer.train(); trainer.save_model(output_dir)
        return trainer