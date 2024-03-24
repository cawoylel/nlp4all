import gc
import torch
import numpy as np
from tqdm import tqdm
from torch.utils.data import DataLoader
from transformers.models.whisper.english_normalizer import BasicTextNormalizer

def evaluate(processor, dataset, data_collator, language, task, metric, model):
    eval_dataloader = DataLoader(dataset["test"], batch_size=8, collate_fn=data_collator)
    forced_decoder_ids = processor.get_decoder_prompt_ids(language=language, task=task)
    normalizer = BasicTextNormalizer()

    predictions = []
    references = []
    normalized_predictions = []
    normalized_references = []

    model.eval()
    for step, batch in enumerate(tqdm(eval_dataloader)):
        with torch.cuda.amp.autocast():
            with torch.no_grad():
                generated_tokens = (
                    model.generate(
                        input_features=batch["input_features"].to("cuda"),
                        forced_decoder_ids=forced_decoder_ids,
                        max_new_tokens=32,
                    )
                    .cpu()
                    .numpy()
                )
                labels = batch["labels"].cpu().numpy()
                labels = np.where(labels != -100, labels, processor.tokenizer.pad_token_id)
                decoded_preds = processor.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
                decoded_labels = processor.tokenizer.batch_decode(labels, skip_special_tokens=True)
                predictions.extend(decoded_preds)
                references.extend(decoded_labels)
                normalized_predictions.extend([normalizer(pred).strip() for pred in decoded_preds])
                normalized_references.extend([normalizer(label).strip() for label in decoded_labels])
            del generated_tokens, labels, batch
        gc.collect()
    wer = 100 * metric.compute(predictions=predictions, references=references)
    normalized_wer = 100 * metric.compute(predictions=normalized_predictions, references=normalized_references)
    eval_metrics = {"eval/wer": wer, "eval/normalized_wer": normalized_wer}

    print(f"{wer=} and {normalized_wer=}")
    print(eval_metrics)