from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('visitor_hostel', '0005_add_overstay_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bookingdetail',
            name='status',
            field=models.CharField(
                choices=[
                    ('Pending', 'Pending'),
                    ('Forwarded', 'Forwarded'),
                    ('Confirmed', 'Confirmed'),
                    ('CancellationRequested', 'Cancellation Requested'),
                    ('CheckedIn', 'Checked In'),
                    ('CheckedOut', 'Checked Out'),
                    ('NoShow', 'No Show'),
                    ('Cancelled', 'Cancelled'),
                    ('Rejected', 'Rejected'),
                    ('Expired', 'Expired'),
                ],
                default='Pending',
                max_length=30,
            ),
        ),
    ]
