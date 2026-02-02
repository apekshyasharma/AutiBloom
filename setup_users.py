import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "autibloom.settings")
django.setup()

from accounts.models import User
from wellbeing.models import ChildProfile, CaregiverChild

def create_users():
    # Admin
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        print("Created superuser 'admin'")
    else:
        print("Superuser 'admin' already exists")

    # Caregiver
    if not User.objects.filter(username='caregiver').exists():
        user = User.objects.create_user('caregiver', 'caregiver@example.com', 'caregiverpass', role=User.Role.CAREGIVER)
        print("Created caregiver 'caregiver'")
    else:
        print("Caregiver 'caregiver' already exists")

    # Clinician
    if not User.objects.filter(username='clinician').exists():
        user = User.objects.create_user('clinician', 'clinician@example.com', 'clinicianpass', role=User.Role.CLINICIAN)
        user.clinician_verified = True
        user.save()
        print("Created clinician 'clinician'")
    else:
        print("Clinician 'clinician' already exists")

    # Child for Caregiver
    cg = User.objects.get(username='caregiver')
    if not ChildProfile.objects.filter(name='TestChild').exists():
        child = ChildProfile.objects.create(name='TestChild', date_of_birth='2020-01-01', sex='m', jaundice='no', family_asd='no')
        CaregiverChild.objects.create(caregiver=cg, child=child)
        print("Created child 'TestChild' for caregiver")
    else:
        print("Child 'TestChild' already exists")

if __name__ == '__main__':
    create_users()
