import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autibloom.settings')
django.setup()

from games.models import TherapyGame

mock_urls = {
    'emotion-match': 'https://h5p.org/h5p/embed/1386341',
    'routine-builder': 'https://h5p.org/h5p/embed/1149729'
}

for slug, url in mock_urls.items():
    TherapyGame.objects.filter(slug=slug).update(embed_url=url)
    print(f"Updated {slug} with {url}")
