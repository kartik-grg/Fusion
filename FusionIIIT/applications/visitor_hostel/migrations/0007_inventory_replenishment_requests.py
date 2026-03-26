from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('globals', '0001_initial'),
        ('visitor_hostel', '0006_add_no_show_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='InventoryReplenishmentRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_requested', models.IntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('reason', models.CharField(blank=True, max_length=300)),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending', max_length=20)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_remark', models.CharField(blank=True, max_length=300)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='replenishment_requests', to='visitor_hostel.inventory')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_replenishment_requests', to='globals.extrainfo')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_replenishment_reviews', to='globals.extrainfo')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
