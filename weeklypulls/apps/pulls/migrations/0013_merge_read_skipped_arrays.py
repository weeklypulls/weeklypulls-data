# Generated manually - merge read and skipped arrays

from django.db import migrations


def merge_read_skipped_arrays(apps, schema_editor):
    """
    Merge the read and skipped arrays into a single read array.
    This combines all issue IDs that were either read or skipped into the read field.
    """
    Pull = apps.get_model('pulls', 'Pull')
    
    updated_count = 0
    for pull in Pull.objects.all():
        # Get current arrays, defaulting to empty lists if None
        read_issues = pull.read or []
        skipped_issues = pull.skipped or []
        
        # Combine both arrays and remove duplicates
        combined_issues = list(set(read_issues + skipped_issues))
        combined_issues.sort()  # Keep them sorted for consistency
        
        # Update the read field with combined data
        pull.read = combined_issues
        pull.save(update_fields=['read'])
        updated_count += 1
        
        if updated_count % 100 == 0:
            print(f"Updated {updated_count} Pull records...")
    
    print(f"Merged read/skipped arrays for {updated_count} Pull records")


def reverse_merge_read_skipped_arrays(apps, schema_editor):
    """
    Reverse migration - this is not perfectly reversible since we lose
    the distinction between read and skipped issues.
    We'll clear the skipped array and leave everything in read.
    """
    Pull = apps.get_model('pulls', 'Pull')
    
    updated_count = 0
    for pull in Pull.objects.all():
        pull.skipped = []
        pull.save(update_fields=['skipped'])
        updated_count += 1
        
        if updated_count % 100 == 0:
            print(f"Cleared skipped arrays for {updated_count} Pull records...")
    
    print(f"Cleared skipped arrays for {updated_count} Pull records")


class Migration(migrations.Migration):

    dependencies = [
        ('pulls', '0012_convert_marvel_to_comicvine_ids'),
    ]

    operations = [
        migrations.RunPython(
            merge_read_skipped_arrays,
            reverse_merge_read_skipped_arrays,
        ),
    ]
