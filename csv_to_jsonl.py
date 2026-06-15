#!/usr/bin/env python3
"""Convert an English->Telugu CSV into chat-formatted JSONL for LoRA finetuning.

Usage:
  python csv_to_jsonl.py data.csv --en english --te telugu --out train.jsonl
  # optionally split a validation set:
  python csv_to_jsonl.py data.csv --en english --te telugu --val 0.05

Output rows look like (works for both Unsloth and MLX-LM):
  {"messages": [
     {"role": "user", "content": "Translate ... :\n<english>"},
     {"role": "assistant", "content": "<telugu>"}
  ]}
"""
import argparse, csv, json, random

INSTRUCTION = "Translate the following English sentence to Telugu:\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--en", required=True, help="English column name")
    ap.add_argument("--te", required=True, help="Telugu column name")
    ap.add_argument("--out", default="train.jsonl")
    ap.add_argument("--val", type=float, default=0.0,
                    help="fraction held out into valid.jsonl (e.g. 0.05)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = []
    with open(args.csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            en = (r.get(args.en) or "").strip()
            te = (r.get(args.te) or "").strip()
            if not en or not te:
                continue
            rows.append({"messages": [
                {"role": "user", "content": INSTRUCTION + en},
                {"role": "assistant", "content": te},
            ]})

    random.Random(args.seed).shuffle(rows)
    n_val = int(len(rows) * args.val)
    val, train = rows[:n_val], rows[n_val:]

    def dump(path, items):
        with open(path, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")

    dump(args.out, train)
    print(f"wrote {len(train)} rows -> {args.out}")
    if n_val:
        dump("valid.jsonl", val)
        print(f"wrote {len(val)} rows -> valid.jsonl")


if __name__ == "__main__":
    main()
