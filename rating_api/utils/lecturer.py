from rating_api.schemas.models import LecturerGet
from rating_api.settings import get_settings
from rating_api.utils.ngram import similarity


settings = get_settings()


def find_similar_lecturers(all_lecturers: list[LecturerGet], name: str) -> list[LecturerGet]:
    """
    Определяеь преподавателей с похожими именами и возвращает в порядке убывания по схожести
    """
    lecturers_similarity: list[(float, LecturerGet)] = []
    for lecturer in all_lecturers:
        similarity_scores: dict[str, float] = {}
        all_words_matched = True
        for word in name.strip().split():
            if (
                similarity_scores.get('last_name') is None
                and (temp_sim := similarity(lecturer.last_name[: len(word)], word)) >= settings.ACCEPTABLE_SIMILARITY
            ):
                similarity_scores["last_name"] = temp_sim
            elif similarity_scores.get("first_name") is None and (
                (temp_sim := similarity(lecturer.first_name[: len(word)], word)) >= settings.ACCEPTABLE_SIMILARITY
                or ('.' in lecturer.first_name and word[0] == lecturer.first_name[0])
            ):
                similarity_scores["first_name"] = temp_sim
            elif similarity_scores.get("middle_name") is None and (
                (temp_sim := similarity(lecturer.middle_name[: len(word)], word)) >= settings.ACCEPTABLE_SIMILARITY
                or ('.' in lecturer.middle_name and word[0] == lecturer.middle_name[0])
            ):
                similarity_scores["middle_name"] = temp_sim
            else:
                all_words_matched = False
                break
        if all_words_matched:
            avg_similarity = (
                sum(similarity_scores.values()) / len(similarity_scores)
                if similarity_scores
                else settings.ACCEPTABLE_SIMILARITY
            )
            lecturers_similarity.append((avg_similarity, lecturer))

    sorted_lecturers = [lecturer for _, lecturer in sorted(lecturers_similarity, key=lambda x: x[0], reverse=True)]
    return sorted_lecturers
