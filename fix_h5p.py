import os
import re
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autibloom.settings')
django.setup()

from games.models import TherapyGame

# 1. Update Game
game = TherapyGame.objects.filter(slug='emotion-match').first()
if game:
    game.embed_type = 'LOCAL'
    game.local_embed_path = 'games/h5p/emotion-match/index.html'
    game.save()
    print("Updated Emotion Match to LOCAL")

# 2. Fix index.html paths
html_path = r'C:\Users\ghimi\OneDrive\Desktop\AutibloomPlatform\games\static\games\h5p\emotion-match\index.html'
if os.path.exists(html_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace absolute windows paths ending with assets\ or assets/
    content = re.sub(r'C:\\[^\"]*assets\\', 'assets/', content)
    content = re.sub(r'C:\/[^\"]*assets\/', 'assets/', content)
    # Replace root level /assets/ with relative assets/
    content = re.sub(r'"\/assets\/', '"assets/', content)
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched index.html asset paths")
else:
    print("index.html not found!")
