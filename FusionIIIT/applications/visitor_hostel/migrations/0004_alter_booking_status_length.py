from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('visitor_hostel', '0003_booking_cancellation_workflow'),
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
                    ('CheckedIn', 'Checked-In'),
                    ('CheckedOut', 'Checked-Out'),
                    ('Cancelled', 'Cancelled'),
                    ('Rejected', 'Rejected'),
                    ('Expired', 'Expired'),
                ],
                default='Pending',
                max_length=30,
            ),
        ),
    ]
