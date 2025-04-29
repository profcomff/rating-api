import logging
from typing import Optional

import aiohttp

from rating_api.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


async def award_first_comment_achievement(user_id: int) -> None:
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

    try:
        async with aiohttp.ClientSession() as session:
            # Check if user already has this achievement
            
            async with session.get(
                api_url + f"achievement/user/{user_id}",
                headers={"Accept": "application/json"},
            ) as response:
                user_achievements = await response.json()
                for achievement in user_achievements.get("achievement", []):
                    if achievement.get("id") == achievement_id:
                        return

            achievement_url = f"{api_url}achievement/achievement/" f"{achievement_id}/reciever/{user_id}"

            session.post(
                achievement_url,
                headers={"Accept": "application/json", "Authorization": token},
            )
    except Exception as e:
        return 
