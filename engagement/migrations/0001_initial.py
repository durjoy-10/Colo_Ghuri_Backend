# Generated for Render deployment

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('destinations', '0001_initial'),
        ('tours', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('general', 'General'), ('booking', 'Booking'), ('review', 'Review'), ('wishlist', 'Wishlist'), ('guide', 'Guide'), ('admin', 'Admin'), ('system', 'System')], default='general', max_length=30)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('link', models.CharField(blank=True, max_length=300)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WishlistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_type', models.CharField(choices=[('destination', 'Destination'), ('tour', 'Tour')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('destination', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='wishlisted_by', to='destinations.destination')),
                ('tour', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='wishlisted_by', to='tours.tour')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wishlist_items', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'wishlist_items',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DestinationReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('comment', models.TextField(blank=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='review_images/destinations/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('destination', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='destinations.destination')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='destination_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'destination_reviews',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'destination')},
            },
        ),
        migrations.CreateModel(
            name='TourReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('comment', models.TextField(blank=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='review_images/tours/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tour', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='tours.tour')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tour_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'tour_reviews',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'tour')},
            },
        ),
    ]
