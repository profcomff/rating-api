import logging
from typing import Optional

import aiohttp

from rating_api.settings import get_settings


settings = get_settings()


async def award_first_comment_achievement(user_id: int):
    # Skip in dev environment
    if settings.APP_ENV not in ["prod", "test"]:
        return

    if settings.APP_ENV == "prod":
        api_url = settings.PROD_API_URL
        achievement_id = settings.FIRST_COMMENT_ACHIEVEMENT_ID_PROD
    else:
        api_url = settings.TEST_API_URL
        achievement_id = settings.FIRST_COMMENT_ACHIEVEMENT_ID_TEST
    token = settings.ACHIEVEMENT_GIVE_TOKEN

    async with aiohttp.ClientSession() as session:
        give_achievement = True
        async with session.get(
            api_url + f"achievement/user/{user_id}",
            headers={"Accept": "application/json"},
        ) as response:
            if response.status == 200:
                user_achievements = await response.json()
                for achievement in user_achievements.get("achievement", []):
                    if achievement.get("id") == achievement_id:
                        give_achievement = False
                        break
            else:
                give_achievement = False
        if give_achievement:
            session.post(
                api_url + f"achievement/achievement/{achievement_id}/reciever/{user_id}",
                headers={"Accept": "application/json", "Authorization": token},
            )
