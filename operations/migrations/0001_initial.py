# Generated for Render deployment

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('guides', '0002_guide_has_set_password_guide_invitation_sent_at_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('verify', 'Verify'), ('booking', 'Booking'), ('payment', 'Payment'), ('email', 'Email'), ('system', 'System')], default='system', max_length=30)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('target_model', models.CharField(blank=True, max_length=100)),
                ('target_id', models.CharField(blank=True, max_length=100)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'activity_logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='GuideAvailability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('status', models.CharField(choices=[('available', 'Available'), ('unavailable', 'Unavailable'), ('booked', 'Booked')], default='available', max_length=20)),
                ('reason', models.CharField(blank=True, max_length=250)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_availability_slots', to=settings.AUTH_USER_MODEL)),
                ('guide_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availability_slots', to='guides.guidegroup')),
            ],
            options={
                'db_table': 'guide_availability',
                'ordering': ['start_date', 'end_date'],
            },
        ),
        migrations.CreateModel(
            name='ContactMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_role', models.CharField(blank=True, max_length=30)),
                ('name', models.CharField(max_length=120)),
                ('email', models.EmailField(max_length=254)),
                ('subject', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('new', 'New'), ('read', 'Read'), ('replied', 'Replied'), ('archived', 'Archived')], default='new', max_length=20)),
                ('admin_reply', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contact_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'contact_messages',
                'ordering': ['-created_at'],
            },
        ),
    ]
