"""
Dataset Preprocessing Script for Phishing Email Detection.

This script downloads/loads phishing email datasets and preprocesses them
into a clean CSV format ready for ML training.

Supported datasets:
  1. Synthetic dataset (auto-generated) — default
  2. Custom CSV with 'text' + 'label' columns

Usage:
    python dataset/preprocess.py
    python dataset/preprocess.py --input raw_emails.csv --output phishing_dataset.csv
"""

import os
import re
import argparse
import logging

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Text Cleaning ──────────────────────────────────────────────────────────────

def clean_email_text(text: str) -> str:
    """Basic text cleaning for email content."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", text)               # Strip HTML
    text = re.sub(r"http\S+|www\.\S+", " URL ", text)  # Replace URLs
    text = re.sub(r"\S+@\S+\.\S+", " EMAIL ", text)    # Replace emails
    text = re.sub(r"[^\w\s!?.,]", " ", text)            # Remove special chars
    text = re.sub(r"\s+", " ", text).strip()            # Normalize whitespace
    return text


def normalize_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize various label formats to binary 0/1."""
    label_col = None
    for col in df.columns:
        if col.lower() in ["label", "class", "category", "is_phishing", "spam", "target"]:
            label_col = col
            break

    if label_col is None:
        raise ValueError(f"Cannot find label column. Columns: {list(df.columns)}")

    if df[label_col].dtype == object:
        mapping = {
            "phishing": 1, "spam": 1, "malicious": 1, "1": 1, "yes": 1, "true": 1,
            "safe": 0, "ham": 0, "legitimate": 0, "benign": 0, "0": 0, "no": 0, "false": 0,
        }
        df["label"] = df[label_col].astype(str).str.lower().map(mapping)
    else:
        df["label"] = df[label_col].astype(int)

    df = df.dropna(subset=["label"])
    df["label"] = df["label"].astype(int)
    return df


def find_text_column(df: pd.DataFrame) -> str:
    """Find the email text column."""
    for col in df.columns:
        if col.lower() in ["text", "email", "body", "content", "message", "email_text"]:
            return col
    raise ValueError(f"Cannot find text column. Columns: {list(df.columns)}")


def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Full preprocessing pipeline on a raw dataframe."""
    logger.info(f"[Preprocess] Input: {len(df)} rows, columns: {list(df.columns)}")

    # Normalize labels
    df = normalize_labels(df)

    # Find and clean text
    text_col = find_text_column(df)
    df["text"] = df[text_col].apply(clean_email_text)

    # Remove empty
    df = df[df["text"].str.len() > 10]

    # Deduplicate
    before = len(df)
    df = df.drop_duplicates(subset=["text"])
    logger.info(f"[Preprocess] Removed {before - len(df)} duplicates")

    # Keep only needed columns
    df = df[["text", "label"]].reset_index(drop=True)

    # Log distribution
    counts = df["label"].value_counts()
    total  = len(df)
    logger.info(f"[Preprocess] Distribution: {counts.get(1,0)} phishing ({counts.get(1,0)/total*100:.1f}%), {counts.get(0,0)} safe ({counts.get(0,0)/total*100:.1f}%)")
    logger.info(f"[Preprocess] Final: {total} samples")
    return df


def generate_sample_dataset(n_phishing: int = 300, n_safe: int = 300) -> pd.DataFrame:
    """Generate a synthetic dataset for demonstration/testing."""
    from sys import path as syspath
    syspath.insert(0, os.path.dirname(OUTPUT_DIR))

    # Import phishing/safe samples from training script
    try:
        from backend.ml.train import PHISHING_SAMPLES, SAFE_SAMPLES
    except ImportError:
        PHISHING_SAMPLES = [
            "URGENT: Your account is suspended. Click here to verify.",
            "You won a $1000 prize! Claim at http://prize.tk now!",
            "Your PayPal account needs verification immediately.",
            "Security alert: Unusual login detected. Confirm identity.",
            "IRS: Respond in 24 hours or face legal action.",
        ] * 20
        SAFE_SAMPLES = [
            "Meeting tomorrow at 10am. Please bring the report.",
            "Your order has shipped! Track at ups.com",
            "Thanks for attending the team meeting yesterday.",
            "Please find the Q3 financial report attached.",
            "New comment on your GitHub pull request.",
        ] * 20

    rng = np.random.default_rng(42)
    ph_idx  = rng.choice(len(PHISHING_SAMPLES), size=n_phishing, replace=True)
    safe_idx = rng.choice(len(SAFE_SAMPLES), size=n_safe, replace=True)

    phishing_texts = [PHISHING_SAMPLES[i] for i in ph_idx]
    safe_texts     = [SAFE_SAMPLES[i] for i in safe_idx]

    df = pd.DataFrame({
        "text":  phishing_texts + safe_texts,
        "label": [1]*n_phishing + [0]*n_safe,
    })
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    logger.info(f"[Dataset] Generated {len(df)} synthetic samples")
    return df


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Preprocess phishing email dataset")
    parser.add_argument("--input",  type=str, default=None, help="Input CSV path")
    parser.add_argument("--output", type=str, default=os.path.join(OUTPUT_DIR, "phishing_dataset.csv"), help="Output CSV path")
    args = parser.parse_args()

    if args.input and os.path.exists(args.input):
        logger.info(f"[Preprocess] Loading: {args.input}")
        raw = pd.read_csv(args.input)
        df  = preprocess_dataframe(raw)
    else:
        logger.info("[Preprocess] No input provided — generating synthetic dataset")
        df = generate_sample_dataset()

    df.to_csv(args.output, index=False)
    logger.info(f"[Preprocess] ✓ Saved to: {args.output}")
    print(f"\n✓ Dataset saved: {args.output}")
    print(f"  Total samples: {len(df)}")
    print(f"  Phishing:      {df['label'].sum()}")
    print(f"  Safe:          {(df['label']==0).sum()}")


if __name__ == "__main__":
    main()
