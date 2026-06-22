import json
import re
from pathlib import Path

import joblib
from django.conf import settings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


CHATBOT_DIR = Path(settings.BASE_DIR) / 'chatbot'
DATASET_PATH = CHATBOT_DIR / 'data' / 'intents.json'
MODEL_DIR = CHATBOT_DIR / 'ml_models'
MODEL_PATH = MODEL_DIR / 'intent_model.joblib'
METRICS_PATH = MODEL_DIR / 'intent_metrics.json'


PRICE_VALUES = [500, 1000, 2000, 3000, 5000, 8000, 10000, 15000, 20000]


def normalize_text(text):
    text = str(text or '').strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text


def generate_extra_training_examples():
    examples = []

    for amount in PRICE_VALUES:
        under_patterns = [
            f'tour under {amount}',
            f'tours under {amount}',
            f'tour below {amount}',
            f'tour less than {amount}',
            f'{amount} takar kom tour',
            f'{amount} takar niche tour',
            f'{amount} er moddhe tour',
            f'amar budget {amount}',
            f'budget {amount} er moddhe tour chai',
            f'{amount} টাকার কম tour',
            f'{amount} টাকার নিচে tour',
            f'{amount} বাজেটের tour',
        ]

        over_patterns = [
            f'tour over {amount}',
            f'tours over {amount}',
            f'tour above {amount}',
            f'tour more than {amount}',
            f'{amount} takar upor tour',
            f'{amount} takar beshi tour',
            f'{amount} er upor tour',
            f'{amount} er beshi package',
            f'{amount} টাকার বেশি tour',
            f'{amount} টাকার উপর tour',
        ]

        for pattern in under_patterns:
            examples.append((pattern, 'tour_price_under'))

        for pattern in over_patterns:
            examples.append((pattern, 'tour_price_over'))

    for low in [1000, 3000, 5000, 8000]:
        for high in [8000, 10000, 15000, 20000]:
            if high > low:
                between_patterns = [
                    f'tour between {low} and {high}',
                    f'tours between {low} and {high}',
                    f'{low} to {high} tour',
                    f'{low} theke {high} tour',
                    f'{low} ar {high} er moddhe tour',
                    f'{low}-{high} package',
                    f'{low} থেকে {high} টাকার tour',
                    f'{low} থেকে {high} budget package',
                ]

                for pattern in between_patterns:
                    examples.append((pattern, 'tour_price_between'))

    status_examples = [
        ('my pending booking', 'traveller_booking_pending'),
        ('pending booking dekhao', 'traveller_booking_pending'),
        ('amar pending bookings', 'traveller_booking_pending'),
        ('pending tour booking', 'traveller_booking_pending'),
        ('my confirmed booking', 'traveller_booking_confirmed'),
        ('confirmed booking dekhao', 'traveller_booking_confirmed'),
        ('amar confirmed bookings', 'traveller_booking_confirmed'),
        ('confirmed tour booking', 'traveller_booking_confirmed'),
        ('my completed booking', 'traveller_booking_completed'),
        ('completed booking dekhao', 'traveller_booking_completed'),
        ('past tour booking', 'traveller_booking_completed'),
        ('guide pending bookings', 'guide_pending_bookings'),
        ('guide confirmed bookings', 'guide_confirmed_bookings'),
        ('guide recent bookings', 'guide_recent_bookings'),
    ]

    examples.extend(status_examples)

    return examples


def load_intent_dataset(dataset_path=DATASET_PATH):
    with open(dataset_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    texts = []
    labels = []

    for intent_item in data.get('intents', []):
        intent_name = intent_item.get('intent')
        patterns = intent_item.get('patterns', [])

        for pattern in patterns:
            if pattern and intent_name:
                texts.append(normalize_text(pattern))
                labels.append(intent_name)

    for pattern, intent_name in generate_extra_training_examples():
        texts.append(normalize_text(pattern))
        labels.append(intent_name)

    if not texts:
        raise ValueError('No training patterns found in chatbot/data/intents.json')

    return texts, labels


def train_intent_model(dataset_path=DATASET_PATH, model_path=MODEL_PATH, metrics_path=METRICS_PATH):
    texts, labels = load_intent_dataset(dataset_path)

    model = Pipeline([
        (
            'tfidf',
            TfidfVectorizer(
                lowercase=True,
                analyzer='char_wb',
                ngram_range=(2, 4),
                min_df=1,
            ),
        ),
        (
            'classifier',
            LogisticRegression(
                max_iter=1500,
                class_weight='balanced',
                random_state=42,
                solver='saga',
                tol=1e-3,
            ),
        ),
    ])

    model.fit(texts, labels)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    metrics = {
        'total_training_examples': len(texts),
        'total_intents': len(set(labels)),
        'model_path': str(model_path),
        'intents': sorted(list(set(labels))),
    }

    with open(metrics_path, 'w', encoding='utf-8') as file:
        json.dump(metrics, file, indent=2, ensure_ascii=False)

    return metrics


class IntentClassifier:
    def __init__(self, threshold=0.28):
        self.threshold = threshold
        self.model = None
        self.load_or_train()

    def should_retrain(self):
        if not MODEL_PATH.exists():
            return True

        if not DATASET_PATH.exists():
            return False

        return DATASET_PATH.stat().st_mtime > MODEL_PATH.stat().st_mtime

    def load_or_train(self):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        if self.should_retrain():
            train_intent_model()

        self.model = joblib.load(MODEL_PATH)

    def predict(self, text):
        text = normalize_text(text)

        if not text:
            return {
                'intent': 'fallback_general',
                'confidence': 0.0,
                'is_confident': False,
            }

        if self.model is None:
            self.load_or_train()

        probabilities = self.model.predict_proba([text])[0]
        classes = self.model.named_steps['classifier'].classes_

        best_index = probabilities.argmax()
        intent = classes[best_index]
        confidence = float(probabilities[best_index])

        return {
            'intent': intent,
            'confidence': round(confidence, 4),
            'is_confident': confidence >= self.threshold,
        }
