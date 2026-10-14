"""
ML Model Training Script.
Trains Logistic Regression, Random Forest, and Naive Bayes on phishing dataset.
Saves models and vectorizer as .pkl files.

Usage:
    python backend/ml/train.py
    python backend/ml/train.py --dataset path/to/dataset.csv
"""

import os
import sys
import time
import pickle
import logging
import argparse
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import MultinomialNB
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, classification_report, confusion_matrix,
)
from sklearn.pipeline import Pipeline

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
DATASET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dataset")


# ── Dataset Generation (fallback if no CSV provided) ──────────────────────────

PHISHING_SAMPLES = [
    "URGENT: Your account has been suspended. Click here to verify your identity immediately or lose access.",
    "Congratulations! You've won a $1000 Amazon gift card. Click the link to claim your prize now!",
    "Dear customer, your PayPal account requires immediate verification. Login at http://paypal-secure.xyz/verify",
    "Your bank account has been compromised. Please confirm your details immediately to restore access.",
    "WARNING: Unusual activity detected on your account. Click here to secure your account now.",
    "You have a pending payment of $850. Confirm your credit card details to receive the transfer.",
    "IRS NOTICE: You owe back taxes. Failure to respond within 24 hours will result in legal action.",
    "Your Apple ID has been locked. Verify your information at http://apple-id-verify.tk/login",
    "FINAL NOTICE: Your subscription expires today. Update payment now to avoid service interruption.",
    "Claim your lottery winnings! You've been selected as a winner. Send your SSN to claim prize.",
    "Dear user, your account will be deleted unless you verify your email immediately. Click here.",
    "Security Alert: Someone tried to login to your account from Russia. Click to verify it was you.",
    "Your Netflix payment failed. Update your billing information to continue watching.",
    "Microsoft detected a virus on your computer. Call 1-800-MICROSOFT immediately.",
    "You have 1 new voicemail. Click to listen: http://voicemail-secure.ml/listen",
    "Your package is on hold due to unpaid customs duty. Pay now to release your shipment.",
    "Exclusive offer for you! Get 90% off on all products. Limited time offer. Click now!",
    "Your email storage is full. Click here to upgrade or lose your emails forever.",
    "Important: Update your personal information or your account will be permanently suspended.",
    "Phishing test email: please verify your credentials at http://bit.ly/phish-test",
    "FREE iPhone 15 Pro! Just fill in your details to claim your prize. Offer expires soon!",
    "Your card ending in 4242 was charged $299. If this wasn't you, click here immediately.",
    "You owe money to the IRS. Arrest warrant issued. Call 1-888-555-TAX immediately.",
    "WINNER: You've been randomly selected for $5000 cash prize. Verify your details now.",
    "Your account has unusual sign-in activity. Click to verify your identity or account will close.",
    "Hello, I am a Nigerian prince and I need your help to transfer $50 million USD.",
    "Urgent security update required. Your password has been compromised. Change it now at our portal.",
    "Your delivery failed because of an incorrect address. Click the link to reschedule delivery.",
    "We noticed you tried to login from a new device. Confirm this is you or click to block.",
    "Your credit score dropped 50 points. Click here to see why and fix it for free.",
]

SAFE_SAMPLES = [
    "Hi team, please find attached the meeting agenda for tomorrow's quarterly review at 10 AM.",
    "Your order #12345 has been shipped! Expected delivery is Tuesday, May 21. Track here.",
    "Just a friendly reminder about the team lunch on Friday at noon. Let me know if you can make it.",
    "Thank you for your recent purchase. Your receipt is attached for your records.",
    "Monthly newsletter: Top 5 productivity tips for remote workers. Unsubscribe anytime.",
    "Your subscription renewal is coming up on June 1. No action needed unless you want to cancel.",
    "Meeting notes from yesterday's standup are now available in the shared Drive folder.",
    "Hi, I wanted to follow up on our conversation last week about the project timeline.",
    "Your GitHub pull request has been reviewed and approved. Ready to merge when you are.",
    "The quarterly financial report is now available for review in the company intranet.",
    "Happy birthday! Wishing you a wonderful day filled with joy and celebration.",
    "Reminder: Your library books are due on May 25. Please return or renew them online.",
    "New comment on your blog post: 'Great article! Very informative and well-written.'",
    "Your Zoom meeting starts in 15 minutes. Join link: zoom.us/j/123456789",
    "Team update: The office will be closed on Monday for the public holiday. Enjoy!",
    "Your annual performance review has been scheduled for May 30 at 2 PM with your manager.",
    "Welcome to our platform! Here are some tips to get started with your new account.",
    "Your flight booking confirmation: PNR AB1234, Mumbai to Delhi, May 25. Have a good trip!",
    "The software update you requested has been completed. All systems are running normally.",
    "Your Amazon order has been delivered to your doorstep. Hope you enjoy your purchase!",
    "Project Alpha status update: All milestones are on track for the June 15 deadline.",
    "New episode of your favorite podcast is now available. Listen on Spotify or Apple Podcasts.",
    "Your insurance renewal paperwork is ready for your signature at your convenience.",
    "We appreciate your feedback on our service. Your response helps us improve.",
    "Dinner reservation confirmed at 7:30 PM for 4 guests at The Italian Kitchen.",
    "Your gym membership renewal is due next month. Visit the front desk to renew.",
    "Conference registration confirmed: TechConf 2024, San Francisco, July 15-17.",
    "The code review for feature branch 'user-auth-v2' is complete. See comments in GitLab.",
    "Invoice #INV-2024-0892 is attached. Payment due by end of month. Thank you.",
    "Good morning! Here is your daily summary of the top news stories in technology.",
]


def generate_dataset() -> pd.DataFrame:
    """Generate a balanced phishing vs. safe email dataset."""
    logger.info("[Dataset] Generating synthetic training dataset...")
    
    # Expand with variations
    phishing_extended = []
    safe_extended = []
    
    # Base samples × 3 with minor variations
    for sample in PHISHING_SAMPLES:
        phishing_extended.append(sample)
        phishing_extended.append(sample + " This is urgent and time-sensitive!")
        phishing_extended.append("IMPORTANT: " + sample)
    
    for sample in SAFE_SAMPLES:
        safe_extended.append(sample)
        safe_extended.append(sample + " Please let me know if you have any questions.")
        safe_extended.append("FYI: " + sample)

    phishing_df = pd.DataFrame({
        "text": phishing_extended,
        "label": [1] * len(phishing_extended),  # 1 = phishing
    })
    safe_df = pd.DataFrame({
        "text": safe_extended,
        "label": [0] * len(safe_extended),  # 0 = safe
    })

    df = pd.concat([phishing_df, safe_df], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    logger.info(f"[Dataset] Generated {len(df)} samples ({len(phishing_df)} phishing, {len(safe_df)} safe)")
    return df


def load_dataset(csv_path: str) -> pd.DataFrame:
    """Load dataset from CSV file. Expects 'text' and 'label' columns."""
    logger.info(f"[Dataset] Loading from: {csv_path}")
    df = pd.read_csv(csv_path)
    
    # Handle common Kaggle column names
    col_map = {}
    for col in df.columns:
        cl = col.lower().strip()
        if cl in ["text", "email", "email_text", "body", "content", "message"]:
            col_map[col] = "text"
        elif cl in ["label", "class", "category", "is_phishing", "spam"]:
            col_map[col] = "label"
    
    df = df.rename(columns=col_map)
    
    if "text" not in df.columns or "label" not in df.columns:
        raise ValueError(f"Dataset must have 'text' and 'label' columns. Found: {list(df.columns)}")
    
    # Normalize labels to 0/1
    if df["label"].dtype == object:
        label_lower = df["label"].str.lower()
        df["label"] = label_lower.map({"phishing": 1, "spam": 1, "safe": 0, "ham": 0, "legitimate": 0}).fillna(0).astype(int)
    
    df = df.dropna(subset=["text", "label"])
    logger.info(f"[Dataset] Loaded {len(df)} samples.")
    return df


def train_models(df: pd.DataFrame) -> dict:
    """Train all models and return evaluation metrics."""
    from services.nlp_processor import NLPProcessor
    nlp = NLPProcessor()

    logger.info("[Training] Preprocessing text with NLP pipeline...")
    df["processed"] = df["text"].apply(lambda x: nlp.get_features_for_model(str(x)))

    X = df["processed"].values
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    logger.info(f"[Training] Train: {len(X_train)}, Test: {len(X_test)}")

    # ── TF-IDF Vectorizer ──────────────────────────────────────────────────────
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # Save vectorizer
    os.makedirs(MODELS_DIR, exist_ok=True)
    vec_path = os.path.join(MODELS_DIR, "tfidf_vectorizer.pkl")
    with open(vec_path, "wb") as f:
        pickle.dump(vectorizer, f)
    logger.info(f"[Training] Vectorizer saved → {vec_path}")

    # ── Models to train ────────────────────────────────────────────────────────
    model_configs = {
        "logistic_regression": LogisticRegression(
            C=1.0, max_iter=1000, random_state=42, class_weight="balanced"
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=100, random_state=42, class_weight="balanced", n_jobs=-1
        ),
        "naive_bayes": MultinomialNB(alpha=0.1),
    }

    metrics = {}

    for model_name, model in model_configs.items():
        logger.info(f"[Training] Training {model_name}...")
        start = time.time()
        model.fit(X_train_vec, y_train)
        duration = time.time() - start

        y_pred = model.predict(X_test_vec)

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        metrics[model_name] = {
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "training_samples": len(X_train),
            "training_duration_sec": round(duration, 3),
        }

        logger.info(
            f"[{model_name}] Accuracy={acc:.4f} | Precision={prec:.4f} | "
            f"Recall={rec:.4f} | F1={f1:.4f} | Time={duration:.2f}s"
        )

        # Detailed report
        print(f"\n{'='*50}")
        print(f"  {model_name.upper().replace('_', ' ')} Report")
        print(f"{'='*50}")
        print(classification_report(y_test, y_pred, target_names=["Safe", "Phishing"]))

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        print(f"Confusion Matrix:\n{cm}\n")

        # Save model
        model_path = os.path.join(MODELS_DIR, f"{model_name}.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        logger.info(f"[Training] Saved → {model_path}")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Train phishing detection ML models")
    parser.add_argument("--dataset", type=str, default=None, help="Path to CSV dataset")
    args = parser.parse_args()

    os.makedirs(MODELS_DIR, exist_ok=True)

    if args.dataset and os.path.exists(args.dataset):
        df = load_dataset(args.dataset)
    else:
        # Check if default dataset exists
        default_csv = os.path.join(DATASET_DIR, "phishing_dataset.csv")
        if os.path.exists(default_csv):
            df = load_dataset(default_csv)
        else:
            logger.info("[Training] No dataset found, generating synthetic data...")
            df = generate_dataset()
            # Save for future reference
            os.makedirs(DATASET_DIR, exist_ok=True)
            df.to_csv(default_csv, index=False)
            logger.info(f"[Training] Saved dataset → {default_csv}")

    metrics = train_models(df)

    print("\n" + "="*60)
    print("  TRAINING SUMMARY")
    print("="*60)
    for model_name, m in metrics.items():
        print(f"\n  {model_name.upper().replace('_', ' ')}")
        print(f"    Accuracy:  {m['accuracy']:.4f}")
        print(f"    Precision: {m['precision']:.4f}")
        print(f"    Recall:    {m['recall']:.4f}")
        print(f"    F1 Score:  {m['f1_score']:.4f}")
    print("\n[✓] All models trained and saved successfully!")
    print(f"[✓] Models directory: {MODELS_DIR}")


if __name__ == "__main__":
    main()
