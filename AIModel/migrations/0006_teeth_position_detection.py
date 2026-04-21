from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('AIModel', '0005_diagnosisresult_error_message_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='diagnosisresult',
            name='teeth_position',
            field=models.CharField(blank=True, choices=[('upper', 'Upper Teeth'), ('lower', 'Lower Teeth'), ('mixed', 'Mixed Upper and Lower'), ('unknown', 'Unknown')], default='unknown', max_length=20),
        ),
        migrations.AddField(
            model_name='diagnosisresult',
            name='teeth_position_confidence',
            field=models.FloatField(blank=True, default=0.0),
        ),
    ]
