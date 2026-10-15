"""Download a pinned XLM-R snapshot and record the weight checksum; no scoring."""
import argparse, hashlib, json
from pathlib import Path
from huggingface_hub import snapshot_download
MODEL='FacebookAI/xlm-roberta-base'
REVISION='e73636d4f797dec63c3081bb6ed5c7b0bb3f2089'
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError('Choose a fresh model directory')
    snapshot_download(MODEL,revision=REVISION,local_dir=a.output,allow_patterns=['config.json','sentencepiece.bpe.model','tokenizer.json','tokenizer_config.json','special_tokens_map.json','model.safetensors'])
    weights=a.output/'model.safetensors';h=hashlib.sha256()
    with weights.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    (a.output/'source.json').write_text(json.dumps({'repo':MODEL,'revision':REVISION,'weights_sha256':h.hexdigest()},indent=2)+'\n')
if __name__=='__main__':main()
