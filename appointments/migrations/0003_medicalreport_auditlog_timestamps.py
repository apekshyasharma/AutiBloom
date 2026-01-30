from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import appointments.models


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0002_alter_appointment_preferred_time_window'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='confirmed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='appointment',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='MedicalReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(
                    upload_to=appointments.models.medical_report_upload_path,
                    validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf'])],
                )),
                ('original_filename', models.CharField(max_length=255)),
                ('content_type', models.CharField(default='application/pdf', max_length=120)),
                ('size_bytes', models.PositiveIntegerField(default=0)),
                ('sha256', models.CharField(blank=True, default='', max_length=64)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('appointment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='medical_reports',
                    to='appointments.appointment',
                )),
                ('uploaded_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='uploaded_medical_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-uploaded_at']},
        ),
        migrations.CreateModel(
            name='AppointmentAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[
                    ('BOOKED', 'Appointment booked'),
                    ('CONFIRMED', 'Appointment confirmed'),
                    ('COMPLETED', 'Case completed'),
                    ('CANCELLED', 'Appointment cancelled'),
                    ('REPORT_UPLOADED', 'Medical report uploaded'),
                    ('REPORT_ACCESSED', 'Medical report accessed'),
                    ('REPORT_ACCESS_DENIED', 'Medical report access denied'),
                    ('PLAN_ISSUED', 'Support plan issued'),
                ], max_length=32)),
                ('from_status', models.CharField(blank=True, default='', max_length=15)),
                ('to_status', models.CharField(blank=True, default='', max_length=15)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('appointment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_logs',
                    to='appointments.appointment',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
