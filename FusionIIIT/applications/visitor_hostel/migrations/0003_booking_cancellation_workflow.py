from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('visitor_hostel', '0002_auto_20260316_0144'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bookingdetail',
            name='status',
            field=models.CharField(choices=[('Pending', 'Pending'), ('Forwarded', 'Forwarded'), ('Confirmed', 'Confirmed'), ('CancellationRequested', 'Cancellation Requested'), ('CheckedIn', 'Checked-In'), ('CheckedOut', 'Checked-Out'), ('Cancelled', 'Cancelled'), ('Rejected', 'Rejected'), ('Expired', 'Expired')], default='Pending', max_length=20),
        ),
        migrations.AddField(
            model_name='bookingdetail',
            name='cancellation_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bookingdetail',
            name='cancellation_approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cancellation_approved_bookings', to='globals.extrainfo'),
        ),
        migrations.AddField(
            model_name='bookingdetail',
            name='cancellation_charge',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='bookingdetail',
            name='cancellation_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='bookingdetail',
            name='cancellation_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bookingdetail',
            name='cancellation_requested_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cancellation_requested_bookings', to='globals.extrainfo'),
        ),
    ]
