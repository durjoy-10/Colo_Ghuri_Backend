from django.core.management.base import BaseCommand

from chatbot.services.intent_classifier import (
    DATASET_PATH,
    METRICS_PATH,
    MODEL_PATH,
    train_intent_model,
)


class Command(BaseCommand):
    help = "Train Colo Ghuri chatbot ML intent classifier from chatbot/data/intents.json"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Training chatbot intent classifier..."))
        self.stdout.write(f"Dataset: {DATASET_PATH}")

        metrics = train_intent_model()

        self.stdout.write(self.style.SUCCESS("Chatbot intent classifier trained successfully."))
        self.stdout.write(f"Model saved: {MODEL_PATH}")
        self.stdout.write(f"Metrics saved: {METRICS_PATH}")
        self.stdout.write(f"Total intents: {metrics.get('total_intents')}")
        self.stdout.write(f"Total training examples: {metrics.get('total_training_examples')}")