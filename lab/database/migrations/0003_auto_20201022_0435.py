# Generated by Django 3.0.3 on 2020-10-22 04:35

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0002_auto_20201022_0431'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Earning',
            new_name='Earnings',
        ),
        migrations.AlterModelOptions(
            name='earnings',
            options={'verbose_name_plural': 'earnings'},
        ),
        migrations.AlterModelOptions(
            name='index',
            options={'verbose_name_plural': 'indices'},
        ),
        migrations.AlterModelOptions(
            name='vol',
            options={'verbose_name_plural': 'vol'},
        ),
    ]
