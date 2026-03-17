from django.db import migrations

def delete_calm_choices(apps, schema_editor):
    TherapyGame = apps.get_model('games', 'TherapyGame')
    TherapyGame.objects.filter(slug='calm-choices').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('games', '0004_therapygame_embed_type_therapygame_h5p_file_path_and_more'),
    ]

    operations = [
        migrations.RunPython(delete_calm_choices),
    ]
