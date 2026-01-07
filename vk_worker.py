import vk_api
import os
import asyncio

def send_to_vk_groups(token, group_ids, message_text, photo_path):
    if not token:
        return "Ключ вк не подключен!! Обратись к администратору @Ivanka58"

    try:
        vk_session = vk_api.VkApi(token=token)
        vk = vk_session.get_api()
        upload = vk_api.VkUpload(vk_session)

        # Загрузка фото
        photo_upload = upload.photo_wall(photo_path)[0]
        attachment = f"photo{photo_upload['owner_id']}_{photo_upload['id']}"

        results = []
        for gid in group_ids:
            try:
                # Отправка в предложку
                vk.wall.post(owner_id=gid, message=message_text, attachments=attachment)
                results.append(f"Группа {gid}: Отправлено ✅")
            except Exception:
                results.append(f"Группа {gid}: Ошибка, группа закрыта, обратись к администратору @Ivanka58")
        
        return "\n".join(results)

    except Exception as e:
        return f"Критическая ошибка ВК: {e}. Обратись к @Ivanka58"
