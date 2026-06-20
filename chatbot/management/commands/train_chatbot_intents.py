from django.core.management.base import BaseCommand
from chatbot.services.intent_classifier import train_intent_model


class Command(BaseCommand):
    help = 'Train Colo Ghuri hybrid chatbot intent classification model'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Training chatbot intent model...'))

        metrics = train_intent_model()

        self.stdout.write(self.style.SUCCESS('Chatbot intent model trained successfully.'))
        self.stdout.write(f"Training examples: {metrics['total_training_examples']}")
        self.stdout.write(f"Total intents: {metrics['total_intents']}")
        self.stdout.write(f"Model saved at: {metrics['model_path']}")