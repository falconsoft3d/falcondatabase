"""Rebuild the activity history of existing projects from the dates already stored.

Rows are grouped per table and day (one event per day with its row count), and
are attributed to the project owner because the real author isn't known.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    ActivityEvent = apps.get_model("projects", "ActivityEvent")
    StoredFile = apps.get_model("storage", "StoredFile")
    connection = schema_editor.connection
    events = []

    for project in Project.objects.all():
        if ActivityEvent.objects.filter(project=project).exists():
            continue
        owner_id = project.owner_id
        events.append(ActivityEvent(project=project, kind="project_created", user_id=owner_id,
                                    created_at=project.created_at))
        for table in project.tables.all():
            events.append(ActivityEvent(project=project, kind="table_created", user_id=owner_id,
                                        target=table.name, created_at=table.created_at))
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f'SELECT min(created_at), count(*) FROM "proj_{project.ref}"."{table.name}" '
                        "GROUP BY (created_at AT TIME ZONE 'UTC')::date"
                    )
                    for first, count in cursor.fetchall():
                        events.append(ActivityEvent(project=project, kind="rows_inserted", user_id=owner_id,
                                                    target=table.name, count=count, created_at=first))
            except Exception:
                continue  # a table without the usual columns is simply skipped
        for bucket in project.buckets.all():
            events.append(ActivityEvent(project=project, kind="bucket_created", user_id=owner_id,
                                        target=bucket.name, created_at=bucket.created_at))
        files = {}
        for stored in StoredFile.objects.filter(bucket__project=project).select_related("bucket"):
            key = (stored.bucket.name, stored.created_at.date())
            first, count = files.get(key, (stored.created_at, 0))
            files[key] = (min(first, stored.created_at), count + 1)
        for (bucket_name, _day), (first, count) in files.items():
            events.append(ActivityEvent(project=project, kind="file_uploaded", user_id=owner_id,
                                        target=bucket_name, count=count, created_at=first))
        for app_user in project.users.all():
            events.append(ActivityEvent(project=project, kind="app_user_signed_up", actor=app_user.email,
                                        created_at=app_user.created_at))
    ActivityEvent.objects.bulk_create(events, batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0007_members_activity"),
        ("storage", "0001_initial"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
