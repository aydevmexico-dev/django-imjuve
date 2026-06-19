from django.db import migrations

ESTATAL_GROUP_NAME = "Administradores Estatales"

# Modelos que un Administrador Estatal puede gestionar (acotado por estado en el admin).
# Los hijos (requirements/images/promotionimage) se editan vía inlines del padre, pero
# Django valida permisos contra el modelo hijo, así que también se incluyen.
TARGET_MODELS = [
    ("programs", "program"),
    ("programs", "event"),
    ("programs", "requirements"),
    ("programs", "images"),
    ("promotions", "promotion"),
    ("promotions", "promotionimage"),
]
ACTIONS = ("add", "change", "delete", "view")


def create_estatal_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    group, _ = Group.objects.get_or_create(name=ESTATAL_GROUP_NAME)

    for app_label, model_name in TARGET_MODELS:
        verbose = apps.get_model(app_label, model_name)._meta.verbose_name
        # post_migrate (que crea content types y permisos) aún no se ha ejecutado en
        # esta corrida, así que los creamos de forma idempotente: post_migrate los
        # reutiliza por (content_type, codename) y no genera duplicados.
        content_type, _ = ContentType.objects.get_or_create(
            app_label=app_label, model=model_name
        )
        for action in ACTIONS:
            permission, _ = Permission.objects.get_or_create(
                content_type=content_type,
                codename=f"{action}_{model_name}",
                defaults={"name": f"Can {action} {verbose}"},
            )
            group.permissions.add(permission)


def remove_estatal_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=ESTATAL_GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("programs", "0002_event_headquarters_event_organizing_institution_and_more"),
        ("promotions", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_estatal_group, remove_estatal_group),
    ]
