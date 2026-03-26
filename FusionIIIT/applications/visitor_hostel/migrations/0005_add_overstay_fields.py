from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('visitor_hostel', '0004_alter_booking_status_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='bill',
            name='overstay_hours',
            field=models.IntegerField(
                default=0,
                help_text='Number of hours guest stayed beyond checkout time',
                validators=[django.core.validators.MinValueValidator(0)]
            ),
        ),
        migrations.AddField(
            model_name='bill',
            name='overstay_charges',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Extra charges applicable for overstay period',
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)]
            ),
        ),
    ]
